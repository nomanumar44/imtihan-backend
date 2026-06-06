"""
scrape_testpoint.py -- Scrape MCQs from testpointpk.com
Uses Playwright (real Chromium browser) to bypass bot protection.

Two modes:
  past-papers    -- Scrape past-paper MCQs (creates PastPaper records)
  important-mcqs -- Scrape important MCQ category pages (direct MCQs, no PastPaper)

For important-mcqs, correct answers are detected from:
    <li class="correct">...</li> inside <ol type="A">
All 4 options (A/B/C/D) are saved.

Usage:
    python manage.py scrape_testpoint --mode past-papers --exam ppsc --max-papers 5
    python manage.py scrape_testpoint --mode important-mcqs --subject islamiat
    python manage.py scrape_testpoint --mode important-mcqs --engine curl --debug
    python manage.py scrape_testpoint --mode important-mcqs --max-pages 3
"""

import re
import time
import subprocess
from bs4 import BeautifulSoup
from bs4.element import Tag
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from core.models import Exam, Subject, MCQ, PastPaper, ActivityLog
from core.utils import scraper_control

# -- Catalogue of index pages, mapped to exam slug -----------------------------
EXAM_INDEX_PAGES = {
    'ppsc': 'https://testpointpk.com/past-papers-mcqs/ppsc-5-years-past-papers-subject-wise-(solved-with-details)',
    'fpsc': 'https://testpointpk.com/past-papers-mcqs/fpsc-5-years-past-papers-subject-wise-(solved-with-details)',
}

# -- Important MCQs category pages (subject slug -> URL) ------------------------
IMPORTANT_MCQS_PAGES = {
    'islamiat':          'https://testpointpk.com/important-mcqs/islamic-studies-mcqs',
    'pakistan-studies':  'https://testpointpk.com/important-mcqs/pak-study',
    'computer-science':  'https://testpointpk.com/important-mcqs/computer',
    'english':           'https://testpointpk.com/important-mcqs/english',
    'general-knowledge': 'https://testpointpk.com/important-mcqs/general-knowledge',
    'everyday-science':  'https://testpointpk.com/important-mcqs/general-science',
    'pedagogy':          'https://testpointpk.com/important-mcqs/pedagogy',
    'mathematics':       'https://testpointpk.com/important-mcqs/maths-mcqs',
    'urdu':              'https://testpointpk.com/important-mcqs/urdu-mcqs',
}

# -- Subject keyword -> DB subject slug mapping --------------------------------
SUBJECT_MAP = {
    'general knowledge':   'general-knowledge',
    'general science':     'everyday-science',
    'everyday science':    'everyday-science',
    'pakistan study':      'pakistan-studies',
    'pakistan studies':    'pakistan-studies',
    'pak study':           'pakistan-studies',
    'islamic study':       'islamiat',
    'islamic studies':     'islamiat',
    'islamiat':            'islamiat',
    'computer':            'computer-science',
    'english':             'english',
    'urdu':                'urdu',
    'mathematics':         'mathematics',
    'maths':               'mathematics',
    'basic mathematics':   'mathematics',
    'current affairs':     'current-affairs',
    'geography':           'geography',
    'pedagogy':            'pedagogy',
    'law':                 'law',
}

BASE_URL = 'https://testpointpk.com'
CURL_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# -- HTML fetchers -------------------------------------------------------------

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
    """Fallback: fetch via system curl."""
    import sys
    curl_bin = 'curl.exe' if sys.platform == 'win32' else 'curl'
    try:
        r = subprocess.run(
            [curl_bin, '-s', '--max-time', str(timeout), '-A', CURL_UA,
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


def _find_question_for_ol(ol: Tag) -> str:
    """
    Robustly find the question text for a given <ol type="A"> element.

    Two formats exist on the site:
      Past papers:   <h5><a>Question?</a></h5>  (inside sibling/ancestor div)
      Important MCQs: <a class="theme-color">Question?</a> (inside same block)

    We try 7 levels of search for both formats before giving up.
    """
    q_text = ''

    parent = ol.parent
    grandparent = parent.parent if parent else None
    great = grandparent.parent if grandparent else None

    def _extract_q(tag: Tag) -> str:
        """Extract question text from a tag that might contain h5 or theme-color link."""
        # Prefer <a class="theme-color"> (important-mcqs format)
        link = tag.find('a', class_='theme-color')
        if link:
            return link.get_text(strip=True)
        # Fallback to <h5><a>...</a></h5> (past-papers format)
        h5 = tag.find('h5')
        if h5:
            a_el = h5.find('a')
            return (a_el or h5).get_text(strip=True)
        return ''

    # 1. Inside ol's parent
    if parent:
        q_text = _extract_q(parent)

    # 2. Inside grandparent
    if not q_text and grandparent:
        q_text = _extract_q(grandparent)

    # 3. Inside great-grandparent
    if not q_text and great:
        q_text = _extract_q(great)

    # 4. Previous siblings of ol itself
    if not q_text:
        for sib in ol.previous_siblings:
            if not isinstance(sib, Tag):
                continue
            q_text = _extract_q(sib)
            if q_text:
                break

    # 5. Previous siblings of ol's parent
    if not q_text and parent:
        for sib in parent.previous_siblings:
            if not isinstance(sib, Tag):
                continue
            q_text = _extract_q(sib)
            if q_text:
                break

    # 6. Previous siblings of grandparent
    if not q_text and grandparent:
        for sib in grandparent.previous_siblings:
            if not isinstance(sib, Tag):
                continue
            q_text = _extract_q(sib)
            if q_text:
                break

    # 7. Global find_previous (h5 only -- covers past-papers fallback)
    if not q_text:
        h5 = ol.find_previous('h5')
        if h5:
            a_el = h5.find('a')
            q_text = (a_el or h5).get_text(strip=True)

    return q_text.strip()


def _scrape_paper_page(url: str, engine: str = 'playwright', debug: bool = False) -> list[dict]:
    """
    Scrape one page from testpointpk.com.

    Key facts confirmed from debug output:
      - correct/incorrect classes ARE in raw HTML (no JS click needed)
      - <ol type="A"> parent is a plain <div> with no class/id
      - <h5> question lives in a sibling/ancestor div, not ol's direct parent
      - 'correct' in li_classes (list) avoids substring match on 'incorrect'
    """
    soup = _get(url, engine=engine)
    if not soup:
        return []

    results = []

    for ol in soup.find_all('ol', attrs={'type': 'A'}):

        # Find question text via multi-level search
        q_text = _find_question_for_ol(ol)

        if not q_text or len(q_text) < 5:
            if debug:
                print(f'  [SKIP] No question found near: {str(ol)[:80]}')
            continue

        # Skip navigation noise
        q_lower = q_text.lower()
        if any(w in q_lower for w in ['click here', 'past papers', 'home', 'subscribe', 'login']):
            continue

        # Extract options + detect correct answer
        # IMPORTANT: use list membership ('correct' in li_classes),
        # NOT substring ('correct' in class_string) -- the latter
        # falsely matches 'incorrect' since it contains 'correct'.
        all_options = []
        correct_idx = 0
        for li in ol.find_all('li'):
            li_classes = li.get('class', []) or []
            text = li.get_text(strip=True)
            if not text:
                continue
            all_options.append(text)
            is_correct = 'correct' in li_classes
            if not is_correct:
                is_correct = ('font-weight-bold' in li_classes and 'text-red' in li_classes)
            if is_correct:
                correct_idx = len(all_options) - 1

        if len(all_options) < 2:
            continue

        # Extract explanation
        explanation = ''
        block_div = ol.parent
        expl_div = block_div.find('div', class_='question-explanation') if block_div else None
        if not expl_div:
            expl_div = ol.find_next('div', class_='question-explanation')
        if expl_div:
            explanation = expl_div.get_text(separator=' ', strip=True)[:800]

        letter_map = ['A', 'B', 'C', 'D']
        correct_letter = letter_map[min(correct_idx, 3)]
        opts = (all_options + [''] * 4)[:4]

        if debug:
            safe_q = q_text[:65].encode('ascii', errors='replace').decode('ascii')
            print(f'  Q: {safe_q}')
            print(f'  Opts: {opts}  Correct: {correct_letter}')

        results.append({
            'question':    q_text.strip(),
            'option_a':    opts[0],
            'option_b':    opts[1],
            'option_c':    opts[2],
            'option_d':    opts[3],
            'correct':     correct_letter,
            'explanation': explanation,
        })

    return results


class Command(BaseCommand):
    help = 'Scrape MCQs from testpointpk.com -- past papers or important-mcqs categories'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, default='past-papers',
                            choices=['past-papers', 'important-mcqs'])
        parser.add_argument('--exam', type=str, default='all',
                            choices=['all', 'ppsc', 'fpsc'])
        parser.add_argument('--max-papers', type=int, default=0)
        parser.add_argument('--max-pages',  type=int, default=0)
        parser.add_argument('--subject',    type=str, default='')
        parser.add_argument('--engine',     type=str, default='playwright',
                            choices=['playwright', 'curl'])
        parser.add_argument('--debug',      action='store_true')

    def _safe(self, msg, style_func=None):
        clean = str(msg).encode('ascii', errors='ignore').decode('ascii')
        self.stdout.write(style_func(clean) if style_func else clean)

    def _ensure_subjects(self):
        extra_subjects = [
            ('Geography',        'geography'),
            ('Current Affairs',  'current-affairs'),
            ('Everyday Science', 'everyday-science'),
            ('Pedagogy',         'pedagogy'),
            ('Urdu',             'urdu'),
            ('Mathematics',      'mathematics'),
            ('Law',              'law'),
            ('Islamiat',         'islamiat'),
            ('Computer Science', 'computer-science'),
            ('English',          'english'),
            ('Pakistan Studies', 'pakistan-studies'),
            ('General Knowledge','general-knowledge'),
        ]
        for name, slug in extra_subjects:
            Subject.objects.get_or_create(slug=slug, defaults={'name': name})
        for name, slug, color in [('PPSC','ppsc','green'), ('FPSC','fpsc','blue')]:
            Exam.objects.get_or_create(slug=slug, defaults={'name': name, 'badge_color': color})

    def _scrape_important_mcqs(self, subject_slug, base_url, max_pages, exam_obj, subj_obj, debug):
        created = updated = 0
        page = 1

        while True:
            if scraper_control.should_stop():
                break

            url = base_url if page == 1 else f'{base_url}?page={page}'
            self._safe(f'  Page {page}: {url}', self.style.MIGRATE_LABEL)

            soup = _get(url, engine=self.engine)
            if not soup:
                self._safe(f'  [!] Could not fetch page {page}', self.style.WARNING)
                break

            mcqs = _scrape_paper_page(url, engine=self.engine, debug=debug)
            self._safe(
                f'  Scraped {len(mcqs)} MCQs from page {page}',
                self.style.SUCCESS if mcqs else self.style.WARNING,
            )

            for mcq_data in mcqs:
                try:
                    _, is_new = MCQ.objects.update_or_create(
                        question_text=mcq_data['question'],
                        defaults={
                            'option_a':       mcq_data['option_a'],
                            'option_b':       mcq_data['option_b'],
                            'option_c':       mcq_data['option_c'],
                            'option_d':       mcq_data.get('option_d', ''),
                            'correct_option': mcq_data['correct'],
                            'explanation':    mcq_data['explanation'],
                            'exam':           exam_obj,
                            'subject':        subj_obj,
                            'past_paper':     None,
                            'source_url':     url,
                            'status':         MCQ.Status.PUBLISHED,
                        },
                    )
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    self._safe(f'     [ERR] {e}', self.style.ERROR)

            if not mcqs:
                break
            if max_pages and page >= max_pages:
                self._safe(f'  Reached max-pages limit ({max_pages})', self.style.MIGRATE_LABEL)
                break

            # Pagination check
            next_link = soup.find('a', attrs={'href': True}, string=re.compile(r'next', re.I))
            if not next_link:
                pagination = soup.find('ul', class_=re.compile(r'pagination'))
                if pagination:
                    current = pagination.find('li', class_=re.compile(r'active|current'))
                    if current:
                        next_li = current.find_next_sibling('li')
                        if not next_li or 'disabled' in ' '.join(next_li.get('class', [])):
                            break
                    else:
                        break
                else:
                    break

            page += 1
            time.sleep(1.5)

        return created, updated

    def handle(self, *args, **options):
        self.debug  = options['debug']
        self.engine = options['engine']
        mode        = options['mode']
        exam_filter = options['exam']
        max_papers  = options['max_papers']
        max_pages   = options['max_pages']
        subject_kw  = options['subject'].lower()

        self._safe(
            '\n========================================\n'
            f'  TestPointPK -- {mode.replace("-", " ").title()} Scraper\n'
            '========================================',
            self.style.MIGRATE_HEADING,
        )

        self._ensure_subjects()
        total_created = total_updated = 0

        # -- IMPORTANT-MCQS MODE -----------------------------------------------
        if mode == 'important-mcqs':
            subjects_to_scrape = {}
            if subject_kw:
                for slug, url in IMPORTANT_MCQS_PAGES.items():
                    if subject_kw in slug or subject_kw in url.lower():
                        subjects_to_scrape[slug] = url
                if not subjects_to_scrape:
                    self._safe(f'[!] No important-mcqs subject matches "{subject_kw}"', self.style.ERROR)
                    return
            else:
                subjects_to_scrape = IMPORTANT_MCQS_PAGES.copy()

            try:
                exam_obj = Exam.objects.get(slug='ppsc')
            except Exam.DoesNotExist:
                exam_obj, _ = Exam.objects.get_or_create(
                    slug='ppsc', defaults={'name': 'PPSC', 'badge_color': 'green'})

            for subj_slug, url in subjects_to_scrape.items():
                if scraper_control.should_stop():
                    break
                try:
                    subj_obj = Subject.objects.get(slug=subj_slug)
                except Subject.DoesNotExist:
                    self._safe(f'[!] Subject "{subj_slug}" not found -- skipping.', self.style.WARNING)
                    continue

                self._safe(f'\n[{subj_slug.upper()}] {subj_obj.name}', self.style.MIGRATE_HEADING)
                c, u = self._scrape_important_mcqs(subj_slug, url, max_pages, exam_obj, subj_obj, self.debug)
                total_created += c
                total_updated += u

        # -- PAST-PAPERS MODE --------------------------------------------------
        else:
            exams_to_run = (
                list(EXAM_INDEX_PAGES.items())
                if exam_filter == 'all'
                else [(exam_filter, EXAM_INDEX_PAGES[exam_filter])]
            )

            for exam_slug, index_url in exams_to_run:
                if scraper_control.should_stop():
                    self._safe('[STOP] Stop requested.', self.style.WARNING)
                    break

                self._safe(f'\n[{exam_slug.upper()}] Fetching index: {index_url}', self.style.MIGRATE_HEADING)
                index_soup = _get(index_url, engine=self.engine)
                if not index_soup:
                    self._safe(f'  [!] Could not fetch index for {exam_slug}.', self.style.WARNING)
                    continue

                papers = _extract_paper_links(index_soup)
                self._safe(f'  Found {len(papers)} paper links.', self.style.MIGRATE_LABEL)

                if subject_kw:
                    papers = [p for p in papers if subject_kw in p['title'].lower()]
                    self._safe(f'  After filter "{subject_kw}": {len(papers)} papers.', self.style.MIGRATE_LABEL)
                if max_papers:
                    papers = papers[:max_papers]
                    self._safe(f'  Limited to first {max_papers} papers.', self.style.MIGRATE_LABEL)

                try:
                    exam_obj = Exam.objects.get(slug=exam_slug)
                except Exam.DoesNotExist:
                    self._safe(f'  [!] Exam "{exam_slug}" not found -- skipping.', self.style.WARNING)
                    continue

                for paper in papers:
                    if scraper_control.should_stop():
                        break

                    self._safe(f'  -> [{paper["subject_slug"]}] {paper["title"][:70]}', self.style.MIGRATE_LABEL)

                    try:
                        subj_obj = Subject.objects.get(slug=paper['subject_slug'])
                    except Subject.DoesNotExist:
                        subj_obj = Subject.objects.get(slug='general-knowledge')

                    year    = _extract_year(paper['title'])
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
                                    'option_d':       mcq_data.get('option_d', ''),
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

        self._safe(f'\n[Done] Created: {total_created}  Updated: {total_updated}', self.style.SUCCESS)

        if total_created > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'TestPointPK scraper imported {total_created} new MCQs',
                    color='#1D9E75',
                )
            except Exception:
                pass