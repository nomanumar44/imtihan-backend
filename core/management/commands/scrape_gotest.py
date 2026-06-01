"""
scrape_gotest.py — Scrape MCQs from gotest.com.pk

Uses Playwright (real browser) to handle JavaScript-rendered WatuPro quizzes.
The site uses a WordPress quiz plugin that renders questions via JS/AJAX,
so we must wait for the quiz DOM to fully render before extraction.

Structure:
  Hardcoded subject URLs  →  Subject tests page (links)  →  Test detail page (WatuPro quiz)

Usage:
    python manage.py scrape_gotest
    python manage.py scrape_gotest --subject english --debug
    python manage.py scrape_gotest --max-tests 5
    python manage.py scrape_gotest --dump-html  (saves raw HTML to /tmp for inspection)
"""

import os
import re
import time
import traceback
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from core.models import Exam, Subject, MCQ, ActivityLog
from core.utils import scraper_control

# Module-level error holder for debug output
_last_error = None

BASE_URL = 'https://gotest.com.pk'

# Hardcoded subject list — the index page links have inconsistent URL patterns
SUBJECTS = [
    {'name': 'English Quiz',      'slug': 'english',          'url': f'{BASE_URL}/general-english-online-test-preparation/'},
    {'name': 'Urdu Quiz',         'slug': 'urdu',             'url': f'{BASE_URL}/urdu-mcqs-test-online-preparation/'},
    {'name': 'Math Quiz',         'slug': 'mathematics',      'url': f'{BASE_URL}/mathematics-online-tests-preparation/'},
    {'name': 'Islamic Quiz',      'slug': 'islamiat',         'url': f'{BASE_URL}/islamic-studies-test-online-preparation/'},
    {'name': 'Biology Quiz',      'slug': 'biology',          'url': f'{BASE_URL}/biology-online-test-preparation/'},
    {'name': 'Chemistry Quiz',    'slug': 'chemistry',        'url': f'{BASE_URL}/chemistry-test-online-preparation/'},
    {'name': 'Physics Quiz',      'slug': 'physics',          'url': f'{BASE_URL}/physics-tests-online-preparation/'},
    {'name': 'Computer Quiz',     'slug': 'computer-science', 'url': f'{BASE_URL}/basic-computer-test-online/'},
    {'name': 'Everyday Science',  'slug': 'everyday-science', 'url': f'{BASE_URL}/everyday-science-test-online-preparation/'},
    {'name': 'Pak Studies',       'slug': 'pakistan-studies', 'url': f'{BASE_URL}/pak-studies-mcqs/'},
]

CURL_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

# WatuPro selectors — tried in order, first match wins
# FIX: added '#watupro_quiz' (underscore) which gotest.com.pk actually uses
WATUPRO_SELECTORS = [
    '#watupro_quiz',
    '#watupro-quiz',
    '.watupro-question',
    '.watupro_question',
    '.watu-question',
    '.watu_question',
    '.question',
    'div[id^="question-"]',
    'div[id^="watu"]',
]

# Known ad/tracker domains — links to/from these are skipped
AD_DOMAINS = {
    'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
    'adnxs.com', 'ads.yahoo.com', 'outbrain.com', 'taboola.com',
    'amazon-adsystem.com', 'moatads.com', 'advertising.com',
    'adsrvr.org', 'rubiconproject.com', 'pubmatic.com', 'openx.net',
    'quantserve.com', 'scorecardresearch.com', 'zedo.com',
    'media.net', 'criteo.com', 'adform.net', 'bidswitch.net',
    'adroll.com', 'smartadserver.com', 'yieldmo.com',
}

# Class/id patterns that indicate ad container elements
AD_CONTAINER_PATTERNS = re.compile(
    r'\b(ad[s_-]?|advert|advertisement|sponsor|promo|banner|adsense|'
    r'ad-zone|ad-slot|ad-block|ad-wrap|dfp-|gpt-ad|commerci)\b',
    re.I
)

# Off-topic link patterns — hard reject even if they contain "test"
SKIP_URL_PATTERNS = [
    'personality', 'interview', 'iq-test', 'check-iq',
    'current-affairs', 'pak-gk', 'general-knowledge',
    'contact', 'about', 'privacy', 'terms', 'sitemap',
    'login', 'register', 'facebook.com', 'twitter.com',
    'youtube.com', 'instagram.com', 'whatsapp', 'telegram',
    # Entry test universities — these bleed into subject pages via sidebar
    'ecat', 'mdcat', 'pieas', 'buitems', 'nfc-iet', 'uet-taxila',
    'paf-kiet', 'ist-islamabad', 'ntu-faisalabad', 'uog-entry',
    'cae-entry', 'entry-test',
]


# ---------------------------------------------------------------------------
# Playwright fetch
# ---------------------------------------------------------------------------

def _fetch_with_playwright(url: str, wait_for_quiz: bool = False,
                           timeout: int = 60, dump_html: bool = False) -> str | None:
    """
    Fetch page using Playwright.

    FIX 1: We now scroll the page to trigger lazy-loaded quiz JS, then wait
    explicitly for a known quiz selector instead of relying on networkidle alone.
    networkidle fires too early on GoTest — the quiz AJAX loads after it.
    """
    global _last_error
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=CURL_UA,
                viewport={'width': 1280, 'height': 900},
            )
            page = ctx.new_page()

            # Use 'domcontentloaded' instead of 'networkidle' so we don't
            # time out on pages with never-ending ad/tracker pings
            page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)

            if wait_for_quiz:
                # Scroll to bottom to trigger lazy-load / AJAX quiz fetch
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(1)
                page.evaluate('window.scrollTo(0, 0)')

                # Wait explicitly for the quiz container or question elements
                quiz_found = False
                for selector in WATUPRO_SELECTORS:
                    try:
                        page.wait_for_selector(selector, timeout=15000)
                        quiz_found = True
                        break
                    except PWTimeout:
                        continue
                    except Exception:
                        continue

                if not quiz_found:
                    # Last resort: give it extra time for any slow JS
                    time.sleep(8)
                else:
                    # Give remaining questions a moment to finish rendering
                    time.sleep(3)
            else:
                # For listing pages, domcontentloaded + short wait is enough
                time.sleep(2)

            html = page.content()
            browser.close()

            if dump_html and html:
                _dump_html(url, html)

            return html
    except Exception as e:
        _last_error = f'{type(e).__name__}: {e}'
        return None


def _dump_html(url: str, html: str) -> None:
    """Save raw HTML to /tmp for offline inspection."""
    slug = re.sub(r'[^a-z0-9]+', '_', urlparse(url).path.lower()).strip('_')
    path = f'/tmp/gotest_{slug[:60]}.html'
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'      [DUMP] HTML saved → {path}')
    except Exception as e:
        print(f'      [DUMP ERROR] {e}')


def _fetch_with_requests(url: str, timeout: int = 20) -> str | None:
    """Fetch page using requests (no JS — fallback only)."""
    global _last_error
    try:
        import requests
        resp = requests.get(url, headers={'User-Agent': CURL_UA}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        _last_error = f'{type(e).__name__}: {e}'
        return None


def _fetch_curl(url: str, timeout: int = 20) -> str | None:
    """Fallback: fetch via curl (no JS rendering)."""
    import subprocess
    try:
        r = subprocess.run(
            ['curl', '-s', '--max-time', str(timeout), '-A', CURL_UA,
             '-H', 'Accept: text/html,*/*', '-L', url],
            capture_output=True, timeout=timeout + 5
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout.decode('utf-8', errors='replace')
    except Exception:
        # Try curl.exe on Windows
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


def _get_soup(url: str, wait_for_quiz: bool = False,
              dump_html: bool = False) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup. Playwright first, then fallbacks."""
    html = _fetch_with_playwright(url, wait_for_quiz=wait_for_quiz, dump_html=dump_html)
    if not html:
        html = _fetch_with_requests(url)
        if not html:
            html = _fetch_curl(url)
    return BeautifulSoup(html, 'html.parser') if html else None


# ---------------------------------------------------------------------------
# MCQ extraction
# ---------------------------------------------------------------------------

def _find_question_blocks(soup: BeautifulSoup, debug_out=None) -> list:
    """
    Locate all question container elements in the parsed page.

    FIX 2: Strategy 3 previously used recursive=False which only checked
    direct children. GoTest nests questions inside wrapper divs inside
    the quiz container. Now we search all descendants.
    """

    # Strategy 1a: explicit watu-question class (outer wrapper gotest uses)
    questions = soup.find_all('div', class_=re.compile(r'^watu-question$', re.I))

    # Strategy 1b: watupro-question-id or watupro-question class
    if not questions:
        questions = soup.find_all(
            'div', class_=re.compile(r'watupro-question(?:-id)?', re.I)
        )

    # Strategy 2: divs with id like "question-1", "question-2"
    if not questions:
        questions = soup.find_all('div', id=re.compile(r'^question-?\d+', re.I))

    # Strategy 3: find the quiz container, then search ALL descendants
    # (not just direct children — gotest nests questions one level deeper)
    if not questions:
        quiz_container = (
            soup.find('div', id=re.compile(r'watupro_quiz|watupro-quiz', re.I)) or
            soup.find('div', id=re.compile(r'^watu', re.I)) or
            soup.find('div', class_=re.compile(r'watupro|watu_quiz', re.I))
        )
        if quiz_container:
            # Search descendants, not just direct children
            questions = quiz_container.find_all(
                'div', class_=re.compile(r'question|watu', re.I)
            )
            # Fallback: try all direct children that have sub-structure
            if not questions:
                candidates = quiz_container.find_all('div', recursive=True)
                # Keep only divs that contain radio inputs (answer choices)
                questions = [d for d in candidates if d.find('input', {'type': 'radio'})]

    # Strategy 4: any div containing at least 3 radio inputs
    if not questions:
        all_divs = soup.find_all('div')
        questions = []
        seen = set()
        for d in all_divs:
            radios = d.find_all('input', {'type': 'radio'})
            if len(radios) >= 3:
                pid = id(d.parent)
                if pid not in seen:
                    questions.append(d)
                    seen.add(pid)

    # Strategy 5: look for answer container divs and use their parent
    if not questions:
        answer_wraps = soup.find_all('div', class_=re.compile(r'^(answer|option)', re.I))
        seen_parents = set()
        questions = []
        for aw in answer_wraps:
            parent = aw.parent
            if parent and id(parent) not in seen_parents:
                questions.append(parent)
                seen_parents.add(id(parent))

    if debug_out:
        debug_out(f'      Found {len(questions)} question containers')

    return questions


def _extract_questions(soup: BeautifulSoup, debug_out=None) -> list:
    """Extract MCQs from a WatuPro-rendered page. Returns list of dicts."""
    results = []
    questions = _find_question_blocks(soup, debug_out=debug_out)

    for q_block in questions:
        try:
            # ---- Question text ----
            q_text = None

            q_content_div = q_block.find(
                'div', class_=re.compile(r'question-content|q-content', re.I)
            )
            if q_content_div:
                num_span = q_content_div.find(
                    'span', class_=re.compile(r'watupro_num|num', re.I)
                )
                if num_span:
                    num_span.decompose()
                q_text = q_content_div.get_text(strip=True)

            if not q_text:
                q_elem = q_block.find(
                    ['p', 'h3', 'h4', 'span', 'div'],
                    class_=re.compile(r'question|q-text|ques', re.I)
                )
                if q_elem:
                    q_text = q_elem.get_text(strip=True)

            if not q_text:
                first_p = q_block.find('p')
                if first_p:
                    q_text = first_p.get_text(strip=True)

            if not q_text or len(q_text) < 10:
                continue

            # Strip leading numbering like "Q1.", "1.", "Question 1:"
            q_text = re.sub(
                r'^(Q\.?\s*\d+[\.\):\s]*|Question\s*\d+[\.\):\s]*|\d+[\.\)\s]*)',
                '', q_text
            ).strip()
            if not q_text or len(q_text) < 10:
                continue

            # ---- Answer options ----
            options = []
            correct_idx = None

            # Method A: watupro-question-choice divs
            choice_divs = q_block.find_all(
                'div', class_=re.compile(r'watupro-question-choice|question-choice', re.I)
            )
            if len(choice_divs) >= 3:
                for i, cd in enumerate(choice_divs[:4]):
                    lbl = cd.find('label')
                    opt_text = lbl.get_text(strip=True) if lbl else cd.get_text(strip=True)
                    opt_text = re.sub(r'^[A-Da-d][\.\)]\s*', '', opt_text).strip()
                    if opt_text:
                        options.append(opt_text)
                    inp = cd.find('input', {'type': 'radio'})
                    if inp and inp.get('data-correct') in ['1', 'true', 'yes']:
                        correct_idx = i
                    cd_classes = ' '.join(cd.get('class', []))
                    if 'correct' in cd_classes.lower():
                        correct_idx = i

            # Method B: radio inputs with labels
            if len(options) < 3:
                options = []
                labels = q_block.find_all('label', class_=re.compile(r'answer', re.I))
                if not labels or len(labels) < 3:
                    labels = q_block.find_all('label')
                if len(labels) >= 3:
                    for i, lbl in enumerate(labels[:4]):
                        opt_text = lbl.get_text(strip=True)
                        opt_text = re.sub(r'^[A-Da-d][\.\)]\s*', '', opt_text).strip()
                        if opt_text:
                            options.append(opt_text)
                        inp = lbl.find('input')
                        if not inp:
                            inp = lbl.find_previous_sibling('input', {'type': 'radio'})
                        if inp and inp.get('data-correct') in ['1', 'true', 'yes']:
                            correct_idx = i

            # Method C: <li class="answer"> elements
            if len(options) < 3:
                options = []
                answer_lis = q_block.find_all('li', class_=re.compile(r'answer', re.I))
                if len(answer_lis) >= 3:
                    for i, li in enumerate(answer_lis[:4]):
                        opt_text = li.get_text(strip=True)
                        opt_text = re.sub(r'^[A-Da-d][\.\)]\s*', '', opt_text).strip()
                        if opt_text:
                            options.append(opt_text)
                        li_classes = li.get('class', [])
                        if isinstance(li_classes, str):
                            li_classes = [li_classes]
                        if any('correct' in c.lower() for c in li_classes):
                            correct_idx = i
                        elif li.find(class_=re.compile(r'correct', re.I)):
                            correct_idx = i

            # Method D: generic <li> elements
            if len(options) < 3:
                options = []
                all_lis = q_block.find_all('li')
                if len(all_lis) >= 3:
                    for i, li in enumerate(all_lis[:4]):
                        opt_text = li.get_text(strip=True)
                        opt_text = re.sub(r'^[A-Da-d][\.\)]\s*', '', opt_text).strip()
                        if opt_text:
                            options.append(opt_text)

            if len(options) < 3:
                continue

            # ---- Correct answer detection ----
            if correct_idx is None:
                correct_attr = q_block.get('data-correct', q_block.get('data-answer', ''))
                if correct_attr:
                    try:
                        correct_idx = int(correct_attr) - 1
                    except (ValueError, TypeError):
                        if correct_attr.upper() in 'ABCD':
                            correct_idx = ord(correct_attr.upper()) - 65

            if correct_idx is None:
                hidden = q_block.find(
                    'input', {'type': 'hidden', 'name': re.compile(r'correct|answer', re.I)}
                )
                if hidden and hidden.get('value'):
                    val = hidden['value']
                    try:
                        correct_idx = int(val) - 1
                    except (ValueError, TypeError):
                        if val.upper() in 'ABCD':
                            correct_idx = ord(val.upper()) - 65

            if correct_idx is not None and (correct_idx < 0 or correct_idx >= len(options)):
                correct_idx = None

            results.append({
                'question': q_text[:500],
                'options': options,
                'correct_idx': correct_idx,
            })

        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Scrape MCQs from gotest.com.pk (WatuPro quiz plugin)'

    def add_arguments(self, parser):
        parser.add_argument('--subject',   type=str,  default='', help='Subject slug/keyword filter')
        parser.add_argument('--max-tests', type=int,  default=0,  help='Max tests per subject (0=all)')
        parser.add_argument('--debug',     action='store_true',   help='Verbose debug output')
        parser.add_argument('--dry-run',   action='store_true',   help='Extract but do not save to DB')
        parser.add_argument('--dump-html', action='store_true',   help='Save raw HTML to /tmp for inspection')

    def _safe_write(self, msg, style=None):
        """Write to stdout with safe ASCII fallback for Windows consoles."""
        try:
            if style:
                self.stdout.write(style(msg))
            else:
                self.stdout.write(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'replace').decode()
            if style:
                self.stdout.write(style(safe_msg))
            else:
                self.stdout.write(safe_msg)

    def handle(self, *args, **options):
        subject_kw = options['subject'].lower()
        max_tests  = options['max_tests']
        debug      = options['debug']
        dry_run    = options['dry_run']
        dump_html  = options['dump_html']

        self._safe_write(f'[*] GoTest.com.pk Scraper — {len(SUBJECTS)} subjects configured')
        if subject_kw:
            self._safe_write(f'    Filter: "{subject_kw}"')
        if max_tests:
            self._safe_write(f'    Max tests per subject: {max_tests}')
        if dump_html:
            self._safe_write('    HTML dump enabled → /tmp/gotest_*.html')
        self._safe_write('')

        total_tests = 0
        total_mcqs  = 0

        for subj_info in SUBJECTS:
            if scraper_control.should_stop():
                self._safe_write('[STOP] Stop requested. Saved GoTest MCQs collected so far.')
                break

            name = subj_info['name']
            slug = subj_info['slug']
            url  = subj_info['url']

            if subject_kw and subject_kw not in name.lower() and subject_kw not in slug:
                continue

            self._safe_write(f'[SUBJ] {name} ({slug})')
            self._safe_write(f'   URL: {url}')

            subj_soup = _get_soup(url, wait_for_quiz=False, dump_html=dump_html)
            if not subj_soup:
                self._safe_write('   [!] Failed to fetch subject page', self.style.WARNING)
                continue

            subj_path = urlparse(url).path.rstrip('/')

            # Main content area only — avoid pulling links from sidebars/headers
            content_area = (
                subj_soup.find('main') or
                subj_soup.find('article') or
                subj_soup.find('div', class_=re.compile(
                    r'entry-content|post-content|content-area|main-content', re.I)) or
                subj_soup.find('div', id=re.compile(r'content|main|primary', re.I)) or
                subj_soup
            )

            all_links = content_area.find_all('a', href=True)

            # Build subject keyword set for hard relevance check
            subj_keywords = {p for p in subj_path.strip('/').split('-') if len(p) > 3}
            subj_keywords.update(slug.replace('-', ' ').split())

            test_links = []
            seen_urls  = set()

            for a in all_links:
                href = a.get('href', '').strip()
                text = a.get_text(strip=True)

                if not href or not text or len(text) < 3:
                    continue

                # Normalise to absolute URL
                if href.startswith('/'):
                    href = BASE_URL + href
                elif not href.startswith('http'):
                    continue

                # Drop non-http schemes
                if href.startswith(('javascript:', 'data:', 'mailto:', '#')):
                    continue

                # ---- FILTER 1: Must be on gotest.com.pk ----
                parsed = urlparse(href)
                if 'gotest.com.pk' not in parsed.netloc:
                    continue

                href_path = parsed.path.rstrip('/')
                if href_path == subj_path or href_path in ('', '/', '/subjects-wise-test-online'):
                    continue

                # ---- FILTER 2: Ad domain blocklist ----
                link_domain = parsed.netloc.lstrip('www.')
                if any(link_domain == ad or link_domain.endswith('.' + ad) for ad in AD_DOMAINS):
                    if debug:
                        self._safe_write(f'      [SKIP-AD-DOMAIN] {href}')
                    continue

                # ---- FILTER 3: Skip links inside ad/promo/sidebar containers ----
                skip_link = False
                for parent in a.parents:
                    if not parent.name:
                        continue
                    p_cls = ' '.join(parent.get('class', []))
                    p_id  = parent.get('id', '')
                    if AD_CONTAINER_PATTERNS.search(p_cls) or AD_CONTAINER_PATTERNS.search(p_id):
                        if debug:
                            self._safe_write(f'      [SKIP-AD-WRAP] {href}')
                        skip_link = True
                        break
                    p_cls_list = [c.lower() for c in parent.get('class', [])]
                    if any(
                        c in ('sidebar', 'widget', 'footer', 'nav', 'menu', 'header',
                               'widget-area', 'sidebar-content', 'footer-widgets')
                        or c.startswith('widget_') or c.startswith('nav-') or c.startswith('menu-')
                        for c in p_cls_list
                    ):
                        skip_link = True
                        break
                if skip_link:
                    continue

                # ---- FILTER 4: Off-topic URL/text pattern blocklist ----
                combined_lower = (href + ' ' + text).lower()
                if any(sp in combined_lower for sp in SKIP_URL_PATTERNS):
                    if debug:
                        self._safe_write(f'      [SKIP-PATTERN] {text[:60]} | {href}')
                    continue

                # ---- FILTER 5: Must contain a quiz/test keyword ----
                if not any(kw in combined_lower for kw in ['test', 'mcqs', 'quiz', 'mcq']):
                    continue

                # ---- FILTER 6: Hard subject relevance (was a soft sort before) ----
                href_lower = href.lower()
                text_lower = text.lower()
                is_relevant = any(kw in href_lower or kw in text_lower for kw in subj_keywords)
                if not is_relevant:
                    subj_name_words = {w.lower() for w in name.split() if len(w) > 3}
                    is_relevant = any(w in text_lower for w in subj_name_words)
                if not is_relevant:
                    if debug:
                        self._safe_write(f'      [SKIP-IRRELEVANT] {text[:60]} | {href}')
                    continue

                # ---- Deduplicate ----
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                test_links.append({'url': href, 'name': text})

            self._safe_write(f'   Found {len(test_links)} test links')

            subj_test_count = 0
            subj_mcq_count  = 0

            for test_info in test_links:
                if scraper_control.should_stop():
                    self._safe_write('[STOP] Stop requested. Saved GoTest MCQs collected so far.')
                    break

                if max_tests and subj_test_count >= max_tests:
                    break

                test_url  = test_info['url']
                test_name = test_info['name']
                subj_test_count += 1
                total_tests     += 1
                self._safe_write(f'   [TEST {subj_test_count}] {test_name}')

                test_soup = _get_soup(test_url, wait_for_quiz=True, dump_html=dump_html)
                if not test_soup:
                    err = f'      [!] Failed to fetch'
                    if _last_error:
                        err += f' — {_last_error}'
                    self._safe_write(err, self.style.WARNING)
                    continue

                if debug:
                    quiz_div = (
                        test_soup.find('div', id=re.compile(r'watupro|watu', re.I)) or
                        test_soup.find('div', class_=re.compile(r'watupro|watu', re.I))
                    )
                    if quiz_div:
                        self._safe_write(
                            f'      [DEBUG] Quiz container: '
                            f'id={quiz_div.get("id","?")} class={quiz_div.get("class","?")}'
                        )
                        # Show first 400 chars of the quiz container's raw HTML
                        self._safe_write(
                            f'      [DEBUG] Container HTML snippet:\n'
                            f'      {str(quiz_div)[:400]}'
                        )
                    else:
                        self._safe_write('      [DEBUG] No watupro container found')
                        body = test_soup.find('body')
                        if body:
                            self._safe_write(
                                f'      [DEBUG] Body text (first 300):\n'
                                f'      {body.get_text()[:300]}'
                            )

                debug_fn = (lambda msg: self._safe_write(msg)) if debug else None
                mcqs = _extract_questions(test_soup, debug_out=debug_fn)

                if not mcqs:
                    self._safe_write('      [!] No MCQs extracted')
                    continue

                self._safe_write(f'      [OK] Extracted {len(mcqs)} MCQs')

                if dry_run:
                    for m in mcqs[:3]:
                        q_p = m['question'][:80].encode('ascii', 'replace').decode()
                        a_p = m['options'][0][:40].encode('ascii', 'replace').decode()
                        b_p = (m['options'][1][:40].encode('ascii', 'replace').decode()
                               if len(m['options']) > 1 else '')
                        self._safe_write(f'         Q: {q_p}')
                        self._safe_write(f'         A: {a_p}  B: {b_p}')
                    total_mcqs += len(mcqs)
                    continue

                # Save to DB
                exam_obj, _ = Exam.objects.get_or_create(
                    slug='ppsc',
                    defaults={'name': 'PPSC', 'badge_color': 'green'}
                )
                subject_obj, _ = Subject.objects.get_or_create(
                    slug=slug,
                    defaults={'name': name}
                )

                for m in mcqs:
                    opts = m['options']
                    correct_option = (
                        chr(65 + m['correct_idx']) if m['correct_idx'] is not None else ''
                    )
                    _, created = MCQ.objects.get_or_create(
                        question_text=m['question'],
                        exam=exam_obj,
                        subject=subject_obj,
                        defaults={
                            'option_a':      opts[0] if len(opts) > 0 else '',
                            'option_b':      opts[1] if len(opts) > 1 else '',
                            'option_c':      opts[2] if len(opts) > 2 else '',
                            'option_d':      opts[3] if len(opts) > 3 else '',
                            'correct_option': correct_option,
                            'source_url':    test_url,
                            'status':        'draft',
                        }
                    )
                    if created:
                        subj_mcq_count += 1
                        total_mcqs     += 1

            self._safe_write(f'   => {subj_mcq_count} new MCQs from {subj_test_count} tests\n')

        # Log activity
        if total_mcqs > 0 and not dry_run:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'GoTest scraper imported {total_mcqs} MCQs from {total_tests} tests',
                    color='#10B981'
                )
            except Exception:
                pass

        self._safe_write(
            f'\n[DONE] {"[DRY RUN] " if dry_run else ""}'
            f'Scraped {total_mcqs} MCQs from {total_tests} tests',
            self.style.SUCCESS
        )
