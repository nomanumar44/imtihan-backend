"""
imtihanhub.com.pk — Unified AI-Powered Crawling and Optimization Suite
Fixed version — all 4 bugs resolved:
  1. Correct CSS selectors for MCQ and job sites
  2. Junk HTML filtering (form fields, nav links, announcements)
  3. Selenium ChromeDriver auto-management via webdriver-manager
  4. Playwright fallback for Windows compatibility
  5. Robust Gemini AI with local fallback

Install requirements:
    pip install requests beautifulsoup4 lxml pandas selenium
    pip install webdriver-manager playwright scrapy
    pip install google-generativeai python-dotenv
    playwright install chromium
"""

import os
import re
import time
import json
import requests
import cloudscraper
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ── Optional imports with graceful fallback ────────────────────────────────────
try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    pd = None
    PANDAS_OK = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    webdriver = None
    SELENIUM_OK = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False

try:
    import scrapy
    from scrapy.crawler import CrawlerProcess
    SCRAPY_OK = True
except ImportError:
    scrapy = None
    SCRAPY_OK = False

try:
    import google.generativeai as genai
    GENAI_OK = True
except ImportError:
    genai = None
    GENAI_OK = False


# ── Words that mean it is NOT a job vacancy ───────────────────────────────────
JOB_SKIP_WORDS = [
    'result', 'written result', 'final result', 'roll no', 'roll number',
    'schedule', 'date sheet', 'home', 'contact', 'about us', 'login',
    'register', 'apply online', 'privacy', 'sitemap', 'feedback',
    'announced on', 'declared on', 'merit list', 'waiting list',
    'syllabus', 'download', 'news', 'notice', 'press release',
]

# ── Words that strongly suggest it IS a job vacancy ───────────────────────────
JOB_KEEP_WORDS = [
    'bps', 'officer', 'assistant', 'inspector', 'director', 'clerk',
    'patwari', 'lecturer', 'teacher', 'naib', 'tehsildar', 'sub inspector',
    'constable', 'head master', 'principal', 'engineer', 'doctor',
    'accountant', 'auditor', 'superintendent', 'librarian', 'nurse',
    'vacancy', 'post', 'recruitment', 'hiring', 'jobs', 'career',
]

# ── Words that confirm it is a real MCQ question ──────────────────────────────
MCQ_SKIP_WORDS = [
    'city', 'qualification', 'login', 'register', 'email', 'password',
    'phone', 'address', 'submit', 'click here', 'subscribe', 'newsletter',
    'home', 'contact', 'about', 'privacy', 'terms', 'copyright',
    'search', 'menu', 'navigation', 'follow us', 'social',
]


class AIScraperSuite:
    def __init__(self):
        self.gemini_key = os.environ.get('GEMINI_API_KEY', '')
        self.ai_enabled = False
        self.timeout = int(os.environ.get('SCRAPER_TIMEOUT', '15'))

        # Standard browser headers
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        # Setup session with retries and anti-bot protection
        # Using cloudscraper to bypass Cloudflare/shared-hosting protections
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(self.headers)

        # Set up Gemini AI if key is present
        if GENAI_OK and self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.ai_enabled = True
                print('[AI Suite] Gemini AI enabled.')
            except Exception as e:
                print(f'[AI Suite] Gemini setup failed: {e}. Using local fallback.')
        else:
            print('[AI Suite] No Gemini key — using smart local fallback.')

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _is_valid_mcq(self, text: str) -> bool:
        """Return True if text looks like a real MCQ question."""
        if not text or len(text) < 15:
            return False
        text_lower = text.lower()
        if any(w in text_lower for w in MCQ_SKIP_WORDS):
            return False
        # Must contain a question mark OR read like a question
        has_question = '?' in text
        starts_like_question = text_lower.startswith((
            'who', 'what', 'when', 'where', 'which', 'how', 'why',
            'the ', 'a ', 'an ', 'in ', 'pakistan', 'capital',
        ))
        return has_question or starts_like_question

    def _is_valid_job(self, title: str) -> bool:
        """Return True if title looks like a real job vacancy."""
        if not title or len(title) < 8:
            return False
        title_lower = title.lower()
        if any(w in title_lower for w in JOB_SKIP_WORDS):
            return False
        # Extra check: filter out very long strings (likely paragraphs not titles)
        if len(title) > 200:
            return False
        return True

    def _polite_delay(self, seconds: float = 1.5):
        """Be polite — do not hammer servers."""
        time.sleep(seconds)

    def _debug_log(self, message: str):
        """Print scraper debug logs safely on Windows terminals."""
        print(str(message).encode('ascii', errors='ignore').decode('ascii'))

    def _normalize_option_text(self, text: str) -> str:
        """Normalize option text for matching bolded correct answers."""
        text = re.sub(r'^[A-Da-d][\.\)]\s*', '', str(text or '')).strip()
        return re.sub(r'\s+', ' ', text).casefold()

    def _extract_correct_from_strong(self, strong_elements: list, option_matches: list) -> str:
        """
        PakMCQs marks the correct answer by wrapping that option in <strong>,
        e.g. <strong>C. 89</strong>, without a "Correct Answer" label.
        """
        options_by_text = {
            self._normalize_option_text(opt_text): opt_letter.upper()
            for opt_letter, opt_text in option_matches
            if self._normalize_option_text(opt_text)
        }

        for strong_text in strong_elements:
            strong_clean = re.sub(r'\s+', ' ', strong_text or '').strip()
            strong_upper = strong_clean.upper()

            match_ans = re.search(r'\b(?:ANSWER|CORRECT)\s*(?:IS)?\s*:?\s*([A-D])\b', strong_upper)
            if match_ans:
                return match_ans.group(1)

            if strong_upper in ['A', 'B', 'C', 'D', 'A.', 'B.', 'C.', 'D.']:
                return strong_upper[0]

            match_option = re.match(r'^([A-D])[\.\)]\s*(.+)$', strong_clean, re.IGNORECASE)
            if match_option:
                option_text = self._normalize_option_text(match_option.group(2))
                if not options_by_text or option_text in options_by_text:
                    return match_option.group(1).upper()

            normalized_strong = self._normalize_option_text(strong_clean)
            if normalized_strong in options_by_text:
                return options_by_text[normalized_strong]

        return ''

    def scrape_pakmcqs_category(self, url: str, debug: bool = False) -> list:
        """
        Custom scraping engine designed specifically for pakmcqs.com category pages.
        Extracts raw questions, options, and pre-identifies the correct answer option!
        Handles inline options, linebreaks, and various <strong> tag placements.
        """
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                print(f'[PakMCQs Category] HTTP {resp.status_code} for {url}')
                return []

            soup = BeautifulSoup(resp.content, 'html.parser')
            articles = soup.select('article.l-post')
            
            results = []
            for art in articles:
                # 1. Extract Question Text
                q_el = art.select_one('.post-title a')
                if not q_el:
                    continue
                question = q_el.get_text(strip=True)

                # 2. Extract Options & Correct Option
                p_el = art.select_one('.content p, .entry-content p')
                if not p_el:
                    continue

                # Pre-identify correct answer from ALL strong tags inside the entire article container
                strong_elements = [s.get_text(strip=True) for s in art.select('strong') if s.get_text(strip=True)]

                # Normalize raw text to parse options cleanly
                raw_text = p_el.get_text(' ')
                
                # Match options like "A. Option text B. Option text..."
                matches = re.findall(r'\b([A-D])[\.\)]\s*(.*?)(?=\s*\b[A-D][\.\)]|$)', raw_text, re.IGNORECASE)
                
                options = []
                correct_opt_letter = 'A'  # fallback
                
                if matches:
                    correct_opt_letter = self._extract_correct_from_strong(strong_elements, matches) or correct_opt_letter
                                
                    # Fill options array
                    for _, opt_text in matches:
                        options.append(opt_text.strip())
                else:
                    # Fallback to line splitting if regex failed to find structured matches
                    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                    for line in lines:
                        line_lower = line.lower()
                        if line_lower.startswith(('a.', 'b.', 'c.', 'd.', 'a)', 'b)', 'c)', 'd)')):
                            clean_opt = re.sub(r'^[a-dA-D][\.\)]\s*', '', line).strip()
                            options.append(clean_opt)
                            
                            # Fallback check against strong elements
                            for strong_text in strong_elements:
                                if clean_opt in strong_text:
                                    correct_opt_letter = line[0].upper()

                # Clean question of trailing numbers/formatting
                question_clean = re.sub(r'^\s*(?:Q\.?\s*)?\d+[\s.\)]+', '', question).strip()

                if len(options) >= 2:
                    if debug:
                        if matches:
                            option_debug = ' | '.join(
                                f'{letter.upper()}={opt_text.strip()[:70]}'
                                for letter, opt_text in matches[:4]
                            )
                        else:
                            option_debug = ' | '.join(
                                f'{chr(65 + idx)}={opt[:70]}'
                                for idx, opt in enumerate(options[:4])
                            )
                        strong_debug = ' | '.join(strong_elements[:5]) or 'none'
                        self._debug_log(f'[PakMCQs DEBUG] Q: {question_clean[:120]}')
                        self._debug_log(f'  strong_tags: {strong_debug}')
                        self._debug_log(f'  options: {option_debug}')
                        self._debug_log(f'  detected_correct: {correct_opt_letter}')

                    results.append({
                        'question': question_clean,
                        'options': options,
                        'correct': correct_opt_letter
                    })

            print(f'[PakMCQs Category] Scraped {len(results)} structured MCQs from {url}')
            return results

        except Exception as e:
            print(f'[PakMCQs Category] Error: {e}')
        return []

    # ── ENGINE 1: Requests + BeautifulSoup (static pages) ─────────────────────

    def scrape_static(self, url: str, selector: str, attribute: str = None) -> list:
        """
        Scrape a static HTML page with requests + BeautifulSoup.
        Returns list of clean text strings.
        """
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                print(f'[Static] HTTP {resp.status_code} for {url}')
                return []

            soup = BeautifulSoup(resp.content, 'html.parser')
            elements = soup.select(selector)
            results = []
            for el in elements:
                val = el.get(attribute, '').strip() if attribute else el.get_text(separator=' ', strip=True)
                if val and len(val) > 3:
                    results.append(val)
            print(f'[Static] {len(results)} elements from {url}')
            return results

        except requests.exceptions.Timeout:
            print(f'[Static] Timeout after {self.timeout}s for {url}')
        except requests.exceptions.ConnectionError:
            print(f'[Static] Cannot connect to {url} — check your internet')
        except Exception as e:
            print(f'[Static] Error: {e}')
        return []

    # ── ENGINE 2: Playwright (best for JS pages on Windows) ───────────────────

    def scrape_playwright(self, url: str, selector: str, wait_for: str = None) -> list:
        """
        Scrape JS-rendered pages using Playwright (headless Chromium).
        Recommended over Selenium on Windows — more stable.
        """
        if not PLAYWRIGHT_OK:
            print('[Playwright] Not installed — falling back to static scraper.')
            return self.scrape_static(url, selector)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent=self.headers['User-Agent']
                )
                page.goto(url, timeout=self.timeout * 1000, wait_until='domcontentloaded')

                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=8000)
                    except Exception:
                        pass  # continue even if element not found
                else:
                    page.wait_for_timeout(2000)

                elements = page.query_selector_all(selector)
                results = []
                for el in elements:
                    text = el.inner_text().strip()
                    if text and len(text) > 3:
                        results.append(text)
                browser.close()
                print(f'[Playwright] {len(results)} elements from {url}')
                return results

        except Exception as e:
            print(f'[Playwright] Failed: {e} — falling back to static scraper.')
            return self.scrape_static(url, selector)

    # ── ENGINE 3: Selenium (fallback dynamic engine) ───────────────────────────

    def scrape_dynamic(self, url: str, selector: str) -> list:
        """
        Scrape JS-rendered pages.
        Tries Playwright first (better on Windows), then Selenium, then static.
        """
        # Try Playwright first — best on Windows
        if PLAYWRIGHT_OK:
            return self.scrape_playwright(url, selector)

        # Try Selenium second
        if not SELENIUM_OK:
            print('[Selenium] Not installed — falling back to static scraper.')
            return self.scrape_static(url, selector)

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f'user-agent={self.headers["User-Agent"]}')

        driver = None
        try:
            # webdriver-manager auto-downloads the correct ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(self.timeout)
            driver.get(url)
            time.sleep(2)  # let JS render

            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            results = [el.text.strip() for el in elements if el.text.strip()]
            print(f'[Selenium] {len(results)} elements from {url}')
            return results

        except Exception as e:
            print(f'[Selenium] Failed: {e} — falling back to static scraper.')
            return self.scrape_static(url, selector)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    # ── ENGINE 4: Scrapy concurrent crawler ───────────────────────────────────

    def scrape_scrapy(self, urls: list, selector: str) -> list:
        """
        Concurrent multi-URL crawl using Scrapy spiders.
        Falls back to a sequential static loop if Scrapy not installed.
        """
        if not SCRAPY_OK:
            print('[Scrapy] Not installed — running sequential static loop.')
            results = []
            for url in urls:
                results.extend(self.scrape_static(url, selector))
                self._polite_delay(1.0)
            return results

        scraped_results = []

        class ImtihanHubSpider(scrapy.Spider):
            name = 'imtihanhub_spider'
            start_urls = urls
            custom_settings = {
                'USER_AGENT': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 Chrome/120 Safari/537.36'
                ),
                'ROBOTSTXT_OBEY': False,
                'DOWNLOAD_DELAY': 1,
                'LOG_LEVEL': 'ERROR',
                'CLOSESPIDER_TIMEOUT': 30,
            }

            def parse(self, response):
                for item in response.css(selector).getall():
                    text = BeautifulSoup(item, 'html.parser').get_text(strip=True)
                    if text:
                        scraped_results.append(text)

        try:
            process = CrawlerProcess()
            process.crawl(ImtihanHubSpider)
            process.start()
            print(f'[Scrapy] {len(scraped_results)} elements scraped.')
            return scraped_results
        except Exception as e:
            print(f'[Scrapy] Failed: {e} — falling back to static loop.')
            results = []
            for url in urls:
                results.extend(self.scrape_static(url, selector))
                self._polite_delay(1.0)
            return results

    # ── DATA CLEANING + DEDUPLICATION ─────────────────────────────────────────

    def clean_scraped_items(self, items: list, text_key: str = 'question') -> list:
        """
        Clean, normalise, and deduplicate a list of dicts using Pandas.
        Falls back to pure Python if Pandas not available.
        """
        if not items:
            return []

        if not PANDAS_OK:
            # Pure Python deduplication
            seen = set()
            cleaned = []
            for item in items:
                text = str(item.get(text_key, '')).strip()
                key = re.sub(r'\s+', ' ', text.lower())[:100]
                if text and key not in seen:
                    seen.add(key)
                    item[text_key] = text
                    cleaned.append(item)
            return cleaned

        try:
            df = pd.DataFrame(items)

            # Strip all string columns
            for col in df.select_dtypes(include='object').columns:
                df[col] = df[col].astype(str).str.strip()

            # Remove exact duplicates on the key field
            if text_key in df.columns:
                df['_dedup_key'] = (
                    df[text_key].str.lower()
                    .str.replace(r'\s+', ' ', regex=True)
                    .str[:100]
                )
                df = df.drop_duplicates(subset=['_dedup_key'])
                df = df.drop(columns=['_dedup_key'])

            # Drop rows where the key field is empty or very short
            if text_key in df.columns:
                df = df[df[text_key].str.len() >= 10]

            return df.to_dict(orient='records')

        except Exception as e:
            print(f'[Pandas] Error: {e} — returning uncleaned items.')
            return items

    # ── AI OPTIMIZATION: MCQ ──────────────────────────────────────────────────

    def optimize_mcq(self, raw_question: str, options: list = None, correct_option: str = None) -> dict:
        """
        Clean, spellcheck, and format an MCQ using Gemini AI.
        Falls back to smart local rules if AI unavailable.
        """
        if not options or len(options) < 4:
            options = ['Option A', 'Option B', 'Option C', 'Option D']

        source_correct = str(correct_option or '').strip().upper()
        if source_correct not in {'A', 'B', 'C', 'D'}:
            source_correct = ''
        source_correct_hint = (
            f'The source HTML marks option {source_correct} as correct; preserve that correct_option.\n'
            if source_correct else ''
        )

        # ── Gemini AI path ────────────────────────────────────────────────────
        if self.ai_enabled:
            prompt = (
                'You are a professional Pakistani civil service exam coordinator.\n'
                'Fix the grammar, spelling, and formatting of this MCQ question.\n'
                'Identify the correct answer from the options based on real general knowledge.\n'
                f'{source_correct_hint}'
                'If options are placeholders like "Option A", write 4 realistic choices.\n'
                'Output ONLY a valid JSON object — no markdown, no extra text.\n'
                'JSON keys: "question" (string), "options" (list of 4 strings), '
                '"correct_option" (one of: "A", "B", "C", "D"), "explanation" (string).\n\n'
                f'Question: {raw_question}\n'
                f'Options: {options}'
            )
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                # Strip markdown code fences if present
                text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
                data = json.loads(text)
                if all(k in data for k in ('question', 'options', 'correct_option')):
                    if len(data['options']) == 4:
                        if source_correct:
                            data['correct_option'] = source_correct
                        return data
            except json.JSONDecodeError:
                print('[AI] Gemini returned invalid JSON — using local fallback.')
            except Exception as e:
                print(f'[AI] Gemini MCQ error: {e} — using local fallback.')

        # ── Smart local fallback ──────────────────────────────────────────────
        # Remove leading numbering e.g. "1.", "Q1.", "1)"
        clean_q = re.sub(r'^\s*(?:Q\.?\s*)?\d+[\s.\)]+', '', raw_question).strip()

        # Capitalise first letter
        if clean_q:
            clean_q = clean_q[0].upper() + clean_q[1:]

        # Ensure ends with question mark
        if clean_q and not clean_q.endswith('?'):
            clean_q += '?'

        # Clean each option — remove leading "A.", "a)", etc.
        clean_opts = []
        for opt in options:
            opt = re.sub(r'^[A-Da-d][\.\)]\s*', '', str(opt)).strip()
            clean_opts.append(opt if opt else 'N/A')

        # Pad to exactly 4 options
        while len(clean_opts) < 4:
            clean_opts.append('N/A')

        return {
            'question':       clean_q,
            'options':        clean_opts[:4],
            'correct_option': source_correct or 'A',   # will be reviewed by admin if no source answer
            'explanation':    'Please verify and add explanation in admin panel.',
        }

    # ── AI OPTIMIZATION: JOB ─────────────────────────────────────────────────

    def optimize_job(self, title: str, description: str, board: str) -> dict:
        """
        Clean and enrich a government job listing using Gemini AI.
        Falls back to smart local BPS detection rules.
        """
        # ── Gemini AI path ────────────────────────────────────────────────────
        if self.ai_enabled:
            prompt = (
                'You are a professional HR writer for Pakistani government job portals.\n'
                'Format and clean the following government job listing.\n'
                'Extract or infer: department, BPS grade, location.\n'
                'Write a short professional description (2-3 sentences).\n'
                'Output ONLY a valid JSON object — no markdown, no extra text.\n'
                'JSON keys: "title", "department", "bps_grade", "description", "location".\n\n'
                f'Title: {title}\n'
                f'Board: {board.upper()}\n'
                f'Raw Description: {description}'
            )
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
                data = json.loads(text)
                if all(k in data for k in ('title', 'department', 'bps_grade', 'description', 'location')):
                    return data
            except json.JSONDecodeError:
                print('[AI] Gemini returned invalid JSON for job — using local fallback.')
            except Exception as e:
                print(f'[AI] Gemini job error: {e} — using local fallback.')

        # ── Smart local BPS detection fallback ───────────────────────────────
        title_clean = title.strip()
        title_lower = title_clean.lower()

        # Try to extract BPS grade from title string
        bps_match = re.search(r'bps[- ]?(\d+)', title_lower)
        if bps_match:
            bps = f'BPS-{bps_match.group(1)}'
        elif any(w in title_lower for w in ['director general', 'secretary', 'chief']):
            bps = 'BPS-20'
        elif any(w in title_lower for w in ['director', 'superintendent', 'principal']):
            bps = 'BPS-18'
        elif any(w in title_lower for w in ['assistant director', 'lecturer', 'doctor']):
            bps = 'BPS-17'
        elif any(w in title_lower for w in ['assistant', 'inspector', 'accountant']):
            bps = 'BPS-16'
        elif any(w in title_lower for w in ['sub inspector', 'naib tehsildar']):
            bps = 'BPS-14'
        elif any(w in title_lower for w in ['clerk', 'junior', 'lower']):
            bps = 'BPS-11'
        elif any(w in title_lower for w in ['patwari', 'constable', 'naib qasid']):
            bps = 'BPS-09'
        else:
            bps = 'BPS-16'

        # Infer location from board
        location_map = {
            'ppsc': 'Punjab', 'fpsc': 'Federal', 'spsc': 'Sindh',
            'kppsc': 'KPK', 'bpsc': 'Balochistan', 'nts': 'Federal',
        }
        location = location_map.get(board.lower(), 'Pakistan')

        board_full_map = {
            'ppsc': 'Punjab Public Service Commission',
            'fpsc': 'Federal Public Service Commission',
            'spsc': 'Sindh Public Service Commission',
            'kppsc': 'KPK Public Service Commission',
            'bpsc': 'Balochistan Public Service Commission',
            'nts': 'National Testing Service',
        }
        board_full = board_full_map.get(board.lower(), board.upper())

        return {
            'title':       title_clean,
            'department':  f'{board.upper()} — Government of Pakistan',
            'bps_grade':   bps,
            'description': (
                f'Official vacancy announced by {board_full}. '
                f'Applications are invited from eligible candidates for the post of {title_clean}. '
                f'Please visit the official {board.upper()} website for eligibility criteria and application procedure.'
            ),
            'location':    location,
        }
