"""
scrape_testpoint.py — Scrape MCQs from testpointpk.com
Uses Playwright (real Chromium browser) to bypass bot protection.

Structure:
  Category listing page  →  paper list  →  MCQ detail page

Each paper page auto-creates a PastPaper record.
MCQs are linked to their PastPaper via FK.
3 options stored per MCQ (option_d blank).

Usage:
    python manage.py scrape_testpoint
    python manage.py scrape_testpoint --exam ppsc --max-papers 5
    python manage.py scrape_testpoint --subject english --debug
    python manage.py scrape_testpoint --engine requests   # fallback without browser
"""

import re
import time
import subprocess
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from core.models import Exam, Subject, MCQ, PastPaper, ActivityLog
from core.utils import scraper_control

# ── Catalogue of index pages, mapped to exam slug ─────────────────────────────
EXAM_INDEX_PAGES = {
    'ppsc': 'https://testpointpk.com/past-papers-mcqs/ppsc-5-years-past-papers-subject-wise-(solved-with-details)',
    'fpsc': 'https://testpointpk.com/past-papers-mcqs/fpsc-5-years-past-papers-subject-wise-(solved-with-details)',
}

# ── Subject keyword → DB subject slug mapping ─────────────────────────────────
SUBJECT_MAP = {
    'general knowledge':  'general-knowledge',
    'general science':    'everyday-science',
    'everyday science':   'everyday-science',
    'pakistan study':     'pakistan-studies',
    'pakistan studies':   'pakistan-studies',
    'islamic study':      'islamiat',
    'islamiat':           'islamiat',
    'computer':           'computer-science',
    'english':            'english',
    'urdu':               'urdu',
    'mathematics':        'mathematics',
    'basic mathematics':  'mathematics',
    'current affairs':    'current-affairs',
    'geography':          'geography',
    'pedagogy':           'pedagogy',
    'law':                'law',
}

BASE_URL = 'https://testpointpk.com'
CURL_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# ── HTML fetchers ──────────────────────────────────────────────────────────────

def _fetch_playwright(url: str, timeout: int = 30) -> str | None:
    """Fetch a page using Playwright (headless Chromium). Returns HTML string."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=CURL_UA,
                locale='en-US',
                viewport={'width': 1280, 'height': 800},
            )
            page = ctx.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None


def _fetch_curl(url: str, timeout: int = 20) -> str | None:
    """Fallback: fetch via system curl.exe."""
    try:
        r = subprocess.run(
            ['curl.exe', '-s', '--max-time', str(timeout), '-A', CURL_UA,
             '-H', 'Accept: text/html,*/*', '-L', url],
            capture_output=True, timeout=timeout + 5
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout.decode('utf-8', errors='replace')
    except Exception:
        pass
    return None


def _get(url: str, engine: str = 'playwright', timeout: int = 30) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup. engine: 'playwright' | 'curl'"""
    html = None
    if engine == 'playwright':
        html = _fetch_playwright(url, timeout)
        if not html:
            html = _fetch_curl(url, timeout)
    else:
        html = _fetch_curl(url, timeout)
    return BeautifulSoup(html, 'html.parser') if html else None


def _extract_year(text: str) -> int:
    """Extract a 4-digit year from a string, or return 0."""
    m = re.search(r'(20\d{2})', text)
    return int(m.group(1)) if m else 0


def _unique_slug(title: str) -> str:
    """Generate a unique PastPaper slug from title, appending pk suffix if needed."""
    from core.models import PastPaper as PP
    base = slugify(title)[:300] or 'paper'
    slug = base
    i = 1
    while PP.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def _infer_subject(text: str) -> str:
    """Return a DB subject slug by matching keywords in a paper title."""
    text_lower = text.lower()
    for keyword, slug in SUBJECT_MAP.items():
        if keyword in text_lower:
            return slug
    return 'general-knowledge'


def _extract_paper_links(index_soup: BeautifulSoup) -> list[dict]:
    """
    Parse the category index page and return a list of:
        {'url': '...', 'title': '...', 'subject_slug': '...'}
    Paper links follow the pattern /paper-mcqs/<id>/<slug>
    """
    papers = []
    seen = set()
    for a in index_soup.select('a[href*="/paper-mcqs/"]'):
        href = a.get('href', '').strip()
        if not href:
            continue
        if href.startswith('/'):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True)
        papers.append({
            'url': href,
            'title': title,
            'subject_slug': _infer_subject(title),
        })
    return papers


def _scrape_paper_page(url: str, engine: str = 'playwright', debug: bool = False) -> list[dict]:
    """
    Scrape one paper page from testpointpk.com.

    Real HTML structure (confirmed by inspection):
      Each MCQ is a bare <div> containing:
        <div class="container-fluid">
          <div class="row">
            <div class="col-..."><h5><a>Question text?</a></h5></div>
          </div>
        </div>
        <ol type="A">
          <li class="incorrect ...">Option A text</li>
          <li class="incorrect ...">Option B text</li>
          <li class="incorrect ...">Option C text</li>
          <li class="correct ...">Option D text</li>  ← correct answer
        </ol>
        <div class="container-fluid">
          ...
          <div class="question-explanation" style="display:none;">
            <h6>Explanation</h6>
            <ul><li>...</li></ul>
          </div>
        </div>

    We store 3 options (A, B, C) only — drop the 4th per spec — keeping the
    correct answer in whichever slot it falls.
    """
    soup = _get(url, engine=engine)
    if not soup:
        return []

    results = []

    # Find all <ol type="A"> — each is the options list for one MCQ
    for ol in soup.find_all('ol', attrs={'type': 'A'}):
        # Walk backwards to find the preceding <h5> question
        q_text = ''
        block_div = ol.parent  # the bare <div> wrapping this MCQ block

        # Search for h5 inside the preceding sibling container-fluid div
        prev = block_div.find('h5')
        if prev:
            a_el = prev.find('a')
            q_text = (a_el or prev).get_text(strip=True)

        # Fallback: look for h5 among previous siblings of the ol itself
        if not q_text:
            for sib in ol.previous_siblings:
                if not hasattr(sib, 'find'):
                    continue
                h5 = sib.find('h5')
                if h5:
                    a_el = h5.find('a')
                    q_text = (a_el or h5).get_text(strip=True)
                    break

        if not q_text or len(q_text) < 10:
            continue

        # Skip navigation/noise
        q_lower = q_text.lower()
        if any(w in q_lower for w in ['click here', 'past papers', 'home', 'subscribe', 'login']):
            continue

        # Extract all options and identify the correct one
        all_options = []
        correct_idx = 0
        for i, li in enumerate(ol.find_all('li')):
            li_class = ' '.join(li.get('class', []))
            text = li.get_text(strip=True)
            if text:
                all_options.append(text)
                if 'correct' in li_class:
                    correct_idx = len(all_options) - 1

        if len(all_options) < 2:
            continue

        # Extract explanation (hidden div inside next container-fluid sibling)
        explanation = ''
        expl_div = block_div.find('div', class_='question-explanation')
        if not expl_div:
            # Try next sibling divs
            next_el = ol.find_next('div', class_='question-explanation')
            if next_el:
                expl_div = next_el
        if expl_div:
            explanation = expl_div.get_text(separator=' ', strip=True)[:800]

        # Build 3-option list — keep the correct answer + 2 distractors.
        # Strategy: always include the correct answer plus the first two options
        # that are NOT the correct answer, giving varied correct positions (A/B/C).
        correct_opt_text = all_options[correct_idx]

        distractors = [o for o in all_options if o != correct_opt_text][:2]
        # Place correct answer randomly among the three slots using its original
        # index to ensure positional variety: idx 0→A, 1→B, 2+→C
        insert_pos = min(correct_idx, 2)
        three = distractors[:insert_pos] + [correct_opt_text] + distractors[insert_pos:]
        three = three[:3]
        while len(three) < 3:
            three.append('None of these')

        try:
            correct_letter = ['A', 'B', 'C'][three.index(correct_opt_text)]
        except ValueError:
            correct_letter = 'A'

        if debug:
            safe_q = q_text[:65].encode('ascii', errors='replace').decode('ascii')
            safe_o = str(three).encode('ascii', errors='replace').decode('ascii')
            print(f'  Q: {safe_q}')
            print(f'  Opts: {safe_o}  Correct: {correct_letter}')

        results.append({
            'question':    q_text.strip(),
            'option_a':    three[0],
            'option_b':    three[1] if len(three) > 1 else '',
            'option_c':    three[2] if len(three) > 2 else '',
            'correct':     correct_letter,
            'explanation': explanation,
        })

    return results


class Command(BaseCommand):
    help = 'Scrape subject-wise past paper MCQs from testpointpk.com (3 options per question)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exam',
            type=str,
            default='all',
            choices=['all', 'ppsc', 'fpsc'],
            help='Which exam to scrape: all, ppsc, fpsc',
        )
        parser.add_argument(
            '--max-papers',
            type=int,
            default=0,
            help='Max paper pages to scrape per exam (0 = all)',
        )
        parser.add_argument(
            '--subject',
            type=str,
            default='',
            help='Only scrape papers whose title contains this keyword (e.g. "english")',
        )
        parser.add_argument(
            '--engine',
            type=str,
            default='playwright',
            choices=['playwright', 'curl'],
            help='HTTP engine: playwright (default, real browser) or curl (fast fallback)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print extra debug output',
        )

    def _safe(self, msg, style_func=None):
        clean = str(msg).encode('ascii', errors='ignore').decode('ascii')
        self.stdout.write(style_func(clean) if style_func else clean)

    def _ensure_subjects(self):

        extra_subjects = [
            ('Geography',       'geography'),
            ('Current Affairs', 'current-affairs'),
            ('Everyday Science','everyday-science'),
            ('Pedagogy',        'pedagogy'),
            ('Urdu',            'urdu'),
            ('Mathematics',     'mathematics'),
            ('Law',             'law'),
            ('Islamiat',        'islamiat'),
            ('Computer Science','computer-science'),
            ('English',         'english'),
            ('Pakistan Studies','pakistan-studies'),
            ('General Knowledge','general-knowledge'),
        ]
        for name, slug in extra_subjects:
            Subject.objects.get_or_create(slug=slug, defaults={'name': name})

        extra_exams = [
            ('PPSC', 'ppsc', 'green'),
            ('FPSC', 'fpsc', 'blue'),
        ]
        for name, slug, color in extra_exams:
            Exam.objects.get_or_create(slug=slug, defaults={'name': name, 'badge_color': color})

    def handle(self, *args, **options):
        self.debug = options['debug']
        self.engine = options['engine']
        exam_filter = options['exam']
        max_papers = options['max_papers']
        subject_kw = options['subject'].lower()

        self._safe(
            '\n========================================\n'
            '  TestPointPK — Subject-Wise MCQ Scraper\n'
            '========================================',
            self.style.MIGRATE_HEADING,
        )

        self._ensure_subjects()

        exams_to_run = (
            list(EXAM_INDEX_PAGES.items())
            if exam_filter == 'all'
            else [(exam_filter, EXAM_INDEX_PAGES[exam_filter])]
        )

        total_created = 0
        total_updated = 0

        for exam_slug, index_url in exams_to_run:
            if scraper_control.should_stop():
                self._safe('[STOP] Stop requested. Saved TestPointPK data collected so far.', self.style.WARNING)
                break

            self._safe(f'\n[{exam_slug.upper()}] Fetching index: {index_url}', self.style.MIGRATE_HEADING)

            index_soup = _get(index_url, engine=self.engine)
            if not index_soup:
                self._safe(f'  [!] Could not fetch index page for {exam_slug}.', self.style.WARNING)
                continue

            papers = _extract_paper_links(index_soup)
            self._safe(f'  Found {len(papers)} paper links.', self.style.MIGRATE_LABEL)

            # Filter by subject keyword if supplied
            if subject_kw:
                papers = [p for p in papers if subject_kw in p['title'].lower()]
                self._safe(f'  After subject filter "{subject_kw}": {len(papers)} papers.', self.style.MIGRATE_LABEL)

            # Honour max-papers limit
            if max_papers and max_papers > 0:
                papers = papers[:max_papers]
                self._safe(f'  Limited to first {max_papers} papers.', self.style.MIGRATE_LABEL)

            try:
                exam_obj = Exam.objects.get(slug=exam_slug)
            except Exam.DoesNotExist:
                self._safe(f'  [!] Exam "{exam_slug}" not found in DB — skipping.', self.style.WARNING)
                continue

            for paper in papers:
                if scraper_control.should_stop():
                    self._safe('[STOP] Stop requested. Saved TestPointPK data collected so far.', self.style.WARNING)
                    break

                self._safe(
                    f'  -> [{paper["subject_slug"]}] {paper["title"][:70]}',
                    self.style.MIGRATE_LABEL,
                )

                try:
                    subj_obj = Subject.objects.get(slug=paper['subject_slug'])
                except Subject.DoesNotExist:
                    subj_obj = Subject.objects.get(slug='general-knowledge')

                # ── Auto-create PastPaper record ──────────────────────────────
                year = _extract_year(paper['title'])
                pp_slug = _unique_slug(paper['title'])
                past_paper_obj, pp_created = PastPaper.objects.update_or_create(
                    source_url=paper['url'],
                    defaults={
                        'title':   paper['title'] or 'Untitled',
                        'slug':    pp_slug,
                        'exam':    exam_obj,
                        'subject': subj_obj,
                        'year':    year,
                        'status':  PastPaper.Status.PUBLISHED,
                    }
                )
                self._safe(
                    f'     PastPaper {"created" if pp_created else "updated"}: {past_paper_obj.title[:50]}',
                    self.style.MIGRATE_LABEL,
                )

                mcqs = _scrape_paper_page(paper['url'], engine=self.engine, debug=self.debug)
                self._safe(f'     Scraped {len(mcqs)} MCQs', self.style.SUCCESS if mcqs else self.style.WARNING)

                for mcq_data in mcqs:
                    try:
                        _, created = MCQ.objects.update_or_create(
                            question_text=mcq_data['question'],
                            defaults={
                                'option_a':       mcq_data['option_a'],
                                'option_b':       mcq_data['option_b'],
                                'option_c':       mcq_data['option_c'],
                                'option_d':       '',
                                'correct_option': mcq_data['correct'],
                                'explanation':    mcq_data['explanation'],
                                'exam':           exam_obj,
                                'subject':        subj_obj,
                                'past_paper':     past_paper_obj,
                                'source_url':     paper['url'],
                                'status':         MCQ.Status.PUBLISHED,
                            },
                        )
                        if created:
                            total_created += 1
                        else:
                            total_updated += 1
                    except Exception as e:
                        self._safe(f'     [ERR] {e}', self.style.ERROR)

                time.sleep(1.5)

        self._safe(
            f'\n[Done] Created: {total_created}  Updated: {total_updated}',
            self.style.SUCCESS,
        )

        if total_created > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'TestPointPK scraper imported {total_created} new MCQs',
                    color='#1D9E75',
                )
            except Exception:
                pass
