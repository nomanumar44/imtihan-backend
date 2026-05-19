"""
scrape_pastpapers.py — Scrape MCQs from pastpaperspdf.com

Uses Playwright (real browser) + WordPress REST API to discover posts,
then parses each post for Q./Answer: one-liner pairs.

Auto-creates PastPaper records and links MCQs to them.

Usage:
    python manage.py scrape_pastpapers
    python manage.py scrape_pastpapers --exam ppsc --max-posts 10
    python manage.py scrape_pastpapers --exam pms --subject gk --debug
    python manage.py scrape_pastpapers --engine curl   # fast fallback
"""

import re
import time
import json
import subprocess
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from core.models import Exam, Subject, MCQ, PastPaper, ActivityLog

CURL_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# ── WordPress REST API base ────────────────────────────────────────────────────
WP_API = 'https://pastpaperspdf.com/wp-json/wp/v2/posts'

# ── Exam search terms → DB slugs ──────────────────────────────────────────────
EXAM_CATEGORIES = {
    'ppsc': {
        'slug':   'ppsc',
        'name':   'PPSC',
        'color':  'green',
        'search': 'ppsc',
    },
    'fpsc': {
        'slug':   'fpsc',
        'name':   'FPSC',
        'color':  'blue',
        'search': 'fpsc',
    },
    'pms': {
        'slug':   'pms',
        'name':   'PMS',
        'color':  'purple',
        'search': 'pms',
    },
    'motorway': {
        'slug':   'motorway-police',
        'name':   'Motorway Police',
        'color':  'amber',
        'search': 'motorway police',
    },
}

# ── Subject keyword inference ──────────────────────────────────────────────────
SUBJECT_MAP = {
    'general knowledge':  'general-knowledge',
    'general science':    'everyday-science',
    'everyday science':   'everyday-science',
    'pakistan study':     'pakistan-studies',
    'pakistan studies':   'pakistan-studies',
    'islamic':            'islamiat',
    'islamiat':           'islamiat',
    'computer':           'computer-science',
    'english':            'english',
    'urdu':               'urdu',
    'mathematics':        'mathematics',
    'maths':              'mathematics',
    'math':               'mathematics',
    'current affairs':    'current-affairs',
    'geography':          'geography',
    'pedagogy':           'pedagogy',
    'law':                'law',
    'gk':                 'general-knowledge',
    'science':            'everyday-science',
}

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

# ── Generic distractor pools keyed by answer length/type ──────────────────────
# Used when the correct answer is a short fact and we need 2 plausible wrongs
GENERIC_DISTRACTORS = {
    'year':     ['1947', '1962', '1971', '1988', '2001', '2005', '2010', '2015', '2018', '2020'],
    'number':   ['5', '7', '10', '12', '15', '20', '25', '50', '100', '200'],
    'country':  ['India', 'China', 'USA', 'UK', 'Iran', 'Turkey', 'Russia', 'France', 'Germany', 'Saudi Arabia'],
    'city':     ['Lahore', 'Karachi', 'Islamabad', 'Peshawar', 'Quetta', 'Multan', 'Faisalabad', 'Rawalpindi'],
    'person':   ['Allama Iqbal', 'Liaquat Ali Khan', 'Ayub Khan', 'Zulfikar Ali Bhutto', 'Benazir Bhutto'],
    'default':  ['None of these', 'All of these', 'Cannot be determined'],
}


def _pick_distractors(correct: str, pool_key: str = 'default') -> list[str]:
    """Return 2 distractors from a pool that are different from the correct answer."""
    pool = GENERIC_DISTRACTORS.get(pool_key, GENERIC_DISTRACTORS['default'])
    filtered = [d for d in pool if d.lower() != correct.lower()]
    return filtered[:2]


def _guess_pool(correct: str) -> str:
    """Guess which distractor pool fits best based on the correct answer."""
    c = correct.strip().lower()
    if re.match(r'^\d{4}$', c):
        return 'year'
    if re.match(r'^\d+(\.\d+)?(%|cm|km|kg|m)?$', c):
        return 'number'
    country_hints = ['pakistan', 'india', 'china', 'usa', 'uk', 'iran', 'turkey',
                     'russia', 'france', 'germany', 'saudi', 'egypt', 'japan']
    if any(h in c for h in country_hints):
        return 'country'
    city_hints = ['lahore', 'karachi', 'islamabad', 'peshawar', 'quetta', 'kabul', 'delhi', 'london']
    if any(h in c for h in city_hints):
        return 'city'
    person_hints = ['ali', 'khan', 'bhutto', 'sharif', 'iqbal', 'jinnah', 'musharraf']
    if any(h in c for h in person_hints):
        return 'person'
    return 'default'


def _curl_text(url: str, timeout: int = 20) -> str | None:
    """Fetch a URL via system curl.exe and return response body text, or None."""
    try:
        result = subprocess.run(
            ['curl.exe', '-s', '--max-time', str(timeout),
             '-A', CURL_UA,
             '-H', 'Accept: text/html,application/json,*/*',
             '-H', 'Accept-Language: en-US,en;q=0.9',
             '-L', url],
            capture_output=True, timeout=timeout + 5
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode('utf-8', errors='replace')
    except Exception:
        pass
    return None


def _fetch_playwright(url: str, timeout: int = 30) -> str | None:
    """Fetch a page using Playwright (headless Chromium)."""
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


def _get(url: str, engine: str = 'playwright', timeout: int = 30) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup."""
    html = None
    if engine == 'playwright':
        html = _fetch_playwright(url, timeout)
        if not html:
            html = _curl_text(url, timeout)
    else:
        html = _curl_text(url, timeout)
    return BeautifulSoup(html, 'html.parser') if html else None


def _infer_subject(text: str) -> str:
    text_lower = text.lower()
    for keyword, slug in SUBJECT_MAP.items():
        if keyword in text_lower:
            return slug
    return 'general-knowledge'


def _fetch_posts_via_api(search_term: str, max_posts: int = 0) -> list[dict]:
    """
    Use the WordPress REST API to search for posts matching search_term.
    Paginates automatically. Returns list of {'url': ..., 'title': ...}
    """
    posts = []
    seen = set()
    page = 1
    per_page = 20

    while True:
        url = (
            f'{WP_API}?search={search_term}&per_page={per_page}'
            f'&page={page}&_fields=id,title,link'
        ).replace(' ', '%20')
        try:
            result = subprocess.run(
                ['curl.exe', '-s', '--max-time', '20',
                 '-A', CURL_UA,
                 '-H', 'Accept: application/json',
                 '-L', url],
                capture_output=True, timeout=25
            )
            if result.returncode != 0 or not result.stdout:
                break
            text = result.stdout.decode('utf-8', errors='replace').strip()
            if not text.startswith('['):
                break
            data = json.loads(text)
        except Exception:
            break

        if not data:
            break

        for post in data:
            url = post.get('link', '')
            title_raw = post.get('title', {})
            title = title_raw.get('rendered', '') if isinstance(title_raw, dict) else str(title_raw)
            title = re.sub(r'&#\d+;|&amp;|&quot;', '', title).strip()
            if url and url not in seen:
                seen.add(url)
                posts.append({'url': url, 'title': title})

        if len(data) < per_page:
            break
        if max_posts and len(posts) >= max_posts:
            break

        page += 1
        time.sleep(0.5)

    return posts


def _parse_qa_pairs(text: str) -> list[tuple[str, str]]:
    """
    Parse the Q./Answer: one-liner format used on pastpaperspdf.com.

    Handles both:
      Q. Question text?\nAnswer:\nAnswer text
      Q1: Question text?\nAnswer: Answer text
      Q1. Question text?\nAnswer:  Answer text (same line)
    """
    pairs = []
    lines = [l.strip() for l in text.split('\n')]
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect question line
        q_match = re.match(r'^Q\.?\s*\d*[:.]?\s*(.+\?)\s*$', line, re.IGNORECASE)
        if q_match:
            question = q_match.group(1).strip()
            # Look ahead for answer (next non-empty lines after "Answer:" marker)
            j = i + 1
            answer = ''
            while j < len(lines):
                candidate = lines[j].strip()
                if re.match(r'^[Aa]nswer\s*:', candidate):
                    # Answer may be on same line or next line
                    inline = re.sub(r'^[Aa]nswer\s*:\s*', '', candidate).strip()
                    if inline:
                        answer = inline
                    else:
                        # Answer is on the next non-empty line
                        j += 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        if j < len(lines):
                            answer = lines[j].strip()
                    break
                elif re.match(r'^Q\.?\s*\d*[:.]', candidate, re.IGNORECASE):
                    break
                j += 1

            if question and answer and len(answer) < 300:
                pairs.append((question, answer))
            i = j
        else:
            i += 1

    return pairs


def _build_mcq(question: str, correct: str, idx: int, debug: bool = False) -> dict:
    """
    Convert a Q/A pair into a 3-option MCQ dict.
    Correct answer position cycles A→B→C based on question index for variety.
    """
    pool_key = _guess_pool(correct)
    distractors = _pick_distractors(correct, pool_key)
    while len(distractors) < 2:
        distractors.append('None of these')

    # Cycle correct answer position: A(0) B(1) C(2) A(3) ...
    pos = idx % 3
    opts = distractors[:2]
    opts.insert(pos, correct)
    opts = opts[:3]
    while len(opts) < 3:
        opts.append('None of these')

    correct_letter = ['A', 'B', 'C'][opts.index(correct)]

    if debug:
        safe_q = question[:60].encode('ascii', errors='replace').decode('ascii')
        safe_c = correct.encode('ascii', errors='replace').decode('ascii')
        safe_o = str(opts).encode('ascii', errors='replace').decode('ascii')
        print(f'  Q: {safe_q}')
        print(f'  Correct: "{safe_c}" -> {correct_letter} | Opts: {safe_o}')

    return {
        'question':    question,
        'option_a':    opts[0],
        'option_b':    opts[1],
        'option_c':    opts[2],
        'correct':     correct_letter,
        'explanation': f'Correct answer: {correct}',
    }


def _extract_year(text: str) -> int:
    m = re.search(r'(20\d{2})', text)
    return int(m.group(1)) if m else 0


def _unique_pp_slug(title: str) -> str:
    base = slugify(title)[:300] or 'paper'
    slug = base
    i = 1
    while PastPaper.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def _scrape_post_mcqs(url: str, engine: str = 'playwright', debug: bool = False) -> list[dict]:
    """
    Scrape one pastpaperspdf.com post and return list of MCQ dicts.
    Parses Q./Answer: one-liner format into 3-option MCQs.
    """
    soup = _get(url, engine=engine)
    if not soup:
        return []

    content = soup.select_one('.entry-content, .post-content, article .content')
    if not content:
        return []

    full_text = content.get_text('\n')
    pairs = _parse_qa_pairs(full_text)

    results = []
    for i, (question, answer) in enumerate(pairs):
        mcq = _build_mcq(question, answer, i, debug=debug)
        results.append(mcq)

    return results


class Command(BaseCommand):
    help = 'Scrape MCQs from pastpaperspdf.com (PPSC, FPSC, PMS, Motorway Police) — 3 options per question'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exam',
            type=str,
            default='all',
            choices=['all'] + list(EXAM_CATEGORIES.keys()),
            help='Which exam to scrape',
        )
        parser.add_argument(
            '--max-posts',
            type=int,
            default=0,
            help='Max posts to process per exam (0 = all)',
        )
        parser.add_argument(
            '--subject',
            type=str,
            default='',
            help='Filter posts by title keyword (e.g. "english", "science")',
        )
        parser.add_argument(
            '--engine',
            type=str,
            default='playwright',
            choices=['playwright', 'curl'],
            help='HTTP engine: playwright (real browser) or curl (fast fallback)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print extra debug output',
        )

    def _safe(self, msg, style_func=None):
        clean = str(msg).encode('ascii', errors='ignore').decode('ascii')
        self.stdout.write(style_func(clean) if style_func else clean)

    def _ensure_db_objects(self):
        subjects = [
            ('General Knowledge', 'general-knowledge'),
            ('Pakistan Studies',  'pakistan-studies'),
            ('English',           'english'),
            ('Islamiat',          'islamiat'),
            ('Computer Science',  'computer-science'),
            ('Mathematics',       'mathematics'),
            ('Current Affairs',   'current-affairs'),
            ('Everyday Science',  'everyday-science'),
            ('Geography',         'geography'),
            ('Urdu',              'urdu'),
            ('Pedagogy',          'pedagogy'),
            ('Law',               'law'),
        ]
        for name, slug in subjects:
            Subject.objects.get_or_create(slug=slug, defaults={'name': name})

        for key, info in EXAM_CATEGORIES.items():
            Exam.objects.get_or_create(
                slug=info['slug'],
                defaults={'name': info['name'], 'badge_color': info['color']},
            )

    def handle(self, *args, **options):
        self.debug = options['debug']
        self.engine = options['engine']
        exam_filter = options['exam']
        max_posts = options['max_posts']
        subject_kw = options['subject'].lower()

        self._safe(
            '\n============================================\n'
            '  PastPapersPDF -- Exam MCQ Scraper\n'
            '  (PPSC / FPSC / PMS / Motorway Police)\n'
            '============================================',
            self.style.MIGRATE_HEADING,
        )

        self._ensure_db_objects()

        exams_to_run = (
            list(EXAM_CATEGORIES.items())
            if exam_filter == 'all'
            else [(exam_filter, EXAM_CATEGORIES[exam_filter])]
        )

        total_created = 0
        total_updated = 0

        for exam_key, exam_info in exams_to_run:
            self._safe(
                f'\n[{exam_info["name"]}] Searching WP API for: "{exam_info["search"]}"',
                self.style.MIGRATE_HEADING,
            )

            posts = _fetch_posts_via_api(exam_info['search'], max_posts=max_posts)
            self._safe(f'  Found {len(posts)} posts via API.', self.style.MIGRATE_LABEL)

            if subject_kw:
                posts = [p for p in posts if subject_kw in p['title'].lower()]
                self._safe(
                    f'  After subject filter "{subject_kw}": {len(posts)} posts.',
                    self.style.MIGRATE_LABEL,
                )

            if max_posts and max_posts > 0:
                posts = posts[:max_posts]

            try:
                exam_obj = Exam.objects.get(slug=exam_info['slug'])
            except Exam.DoesNotExist:
                self._safe(f'  [!] Exam "{exam_info["slug"]}" not in DB.', self.style.WARNING)
                continue

            for post in posts:
                subject_slug = _infer_subject(post['title'])
                self._safe(
                    f'  -> [{subject_slug}] {post["title"][:70]}',
                    self.style.MIGRATE_LABEL,
                )

                try:
                    subj_obj = Subject.objects.get(slug=subject_slug)
                except Subject.DoesNotExist:
                    subj_obj = Subject.objects.get(slug='general-knowledge')

                # ── Auto-create PastPaper record ──────────────────────────────
                year = _extract_year(post['title'])
                pp_slug = _unique_pp_slug(post['title'])
                past_paper_obj, pp_created = PastPaper.objects.update_or_create(
                    source_url=post['url'],
                    defaults={
                        'title':   post['title'] or 'Untitled',
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

                mcqs = _scrape_post_mcqs(post['url'], engine=self.engine, debug=self.debug)
                self._safe(
                    f'     Scraped {len(mcqs)} MCQs',
                    self.style.SUCCESS if mcqs else self.style.WARNING,
                )

                for mcq_data in mcqs:
                    if not mcq_data['question'] or not mcq_data['option_a']:
                        continue
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
                                'source_url':     post['url'],
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
                    message=f'PastPapersPDF scraper imported {total_created} new MCQs',
                    color='#1D4E9E',
                )
            except Exception:
                pass
