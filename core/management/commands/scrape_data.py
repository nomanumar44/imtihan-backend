"""
imtihanhub.com.pk — Django Management Command: scrape_data
Fixed version — resolves all 4 bugs:
  1. update_or_create instead of get_or_create (was saving 0 records)
  2. Correct CSS selectors for real MCQ content
  3. Proper junk filtering (form fields, announcements, navigation)
  4. Correct PPSC/FPSC job URLs and vacancy-only filters
  5. Debug output so you can see exactly what is scraped

Usage:
    python manage.py scrape_data               # scrape everything
    python manage.py scrape_data --type mcqs
    python manage.py scrape_data --type jobs
    python manage.py scrape_data --type current-affairs
    python manage.py scrape_data --debug       # extra verbose output
"""

from django.core.management.base import BaseCommand
from core.models import Exam, Subject, CurrentAffairsCategory, MCQ, JobListing, ActivityLog
from core.utils.ai_scraper_suite import AIScraperSuite
from datetime import datetime, timedelta
from django.utils import timezone
import os
import time
import requests
from bs4 import BeautifulSoup
from core.utils import scraper_control


# ── Seed MCQs — used when live scraping fails ─────────────────────────────────
SEED_MCQS = [
    {
        'question': 'Who was the first Governor General of Pakistan?',
        'options': ['Quaid-e-Azam Muhammad Ali Jinnah', 'Liaquat Ali Khan', 'Iskander Mirza', 'Ayub Khan'],
        'correct': 'A',
        'subject': 'pakistan-studies',
        'exam': 'ppsc',
    },
    {
        'question': 'The Lahore Resolution was passed in which year?',
        'options': ['1935', '1940', '1945', '1947'],
        'correct': 'B',
        'subject': 'pakistan-studies',
        'exam': 'ppsc',
    },
    {
        'question': 'Which is the national language of Pakistan?',
        'options': ['Punjabi', 'Sindhi', 'Urdu', 'Pashto'],
        'correct': 'C',
        'subject': 'pakistan-studies',
        'exam': 'fpsc',
    },
    {
        'question': 'Which Mughal Emperor built the Badshahi Mosque in Lahore?',
        'options': ['Akbar', 'Shah Jahan', 'Aurangzeb', 'Jahangir'],
        'correct': 'C',
        'subject': 'pakistan-studies',
        'exam': 'ppsc',
    },
    {
        'question': 'The synonym of "Benevolent" is:',
        'options': ['Hostile', 'Kind', 'Strict', 'Greedy'],
        'correct': 'B',
        'subject': 'english',
        'exam': 'fpsc',
    },
    {
        'question': 'Islamabad became the capital of Pakistan in which year?',
        'options': ['1947', '1958', '1969', '1972'],
        'correct': 'C',
        'subject': 'pakistan-studies',
        'exam': 'nts',
    },
    {
        'question': 'Which is the longest river in Pakistan?',
        'options': ['Chenab', 'Jhelum', 'Indus', 'Ravi'],
        'correct': 'C',
        'subject': 'pakistan-studies',
        'exam': 'ppsc',
    },
    {
        'question': 'What does RAM stand for in computing?',
        'options': ['Random Access Memory', 'Read Access Module', 'Rapid Array Memory', 'Read And Modify'],
        'correct': 'A',
        'subject': 'computer-science',
        'exam': 'nts',
    },
    {
        'question': 'How many Surahs are in the Holy Quran?',
        'options': ['110', '112', '114', '116'],
        'correct': 'C',
        'subject': 'islamiat',
        'exam': 'ppsc',
    },
    {
        'question': 'Which gas makes up the largest percentage of Earth\'s atmosphere?',
        'options': ['Oxygen', 'Carbon Dioxide', 'Nitrogen', 'Hydrogen'],
        'correct': 'C',
        'subject': 'general-knowledge',
        'exam': 'nts',
    },
    {
        'question': 'The headquarter of the United Nations is located in:',
        'options': ['Washington D.C.', 'Geneva', 'New York', 'London'],
        'correct': 'C',
        'subject': 'general-knowledge',
        'exam': 'fpsc',
    },
    {
        'question': 'Pakistan\'s 1973 Constitution was passed on:',
        'options': ['14 August 1973', '10 April 1973', '23 March 1973', '4 August 1973'],
        'correct': 'B',
        'subject': 'pakistan-studies',
        'exam': 'fpsc',
    },
]

# ── Seed Current Affairs ───────────────────────────────────────────────────────
SEED_CURRENT_AFFAIRS = [
    {
        'question': f'The 23rd SCO Summit was hosted by Pakistan in which city?',
        'options': ['Islamabad', 'Lahore', 'Karachi', 'Peshawar'],
        'correct': 'A',
        'exam': 'fpsc',
    },
    {
        'question': 'Which country topped the 2024 Paris Olympics medal tally?',
        'options': ['China', 'Great Britain', 'United States', 'Australia'],
        'correct': 'C',
        'exam': 'fpsc',
    },
    {
        'question': 'The IMF approved Pakistan\'s Extended Fund Facility (EFF) in which year?',
        'options': ['2022', '2023', '2024', '2025'],
        'correct': 'C',
        'exam': 'fpsc',
    },
    {
        'question': 'Who is the current Secretary-General of the United Nations?',
        'options': ['Ban Ki-moon', 'Kofi Annan', 'António Guterres', 'Boutros Boutros-Ghali'],
        'correct': 'C',
        'exam': 'fpsc',
    },
    {
        'question': 'The CPEC main corridor passes through which Pakistani city?',
        'options': ['Karachi', 'Gwadar', 'Lahore', 'Quetta'],
        'correct': 'B',
        'exam': 'ppsc',
    },
]

# ── Seed Jobs ─────────────────────────────────────────────────────────────────
SEED_JOBS = [
    {
        'title': 'Patwari (BPS-09)',
        'board': 'ppsc',
        'desc': 'PPSC invites applications for Patwari posts in Revenue Department, Punjab.',
    },
    {
        'title': 'Inspector Customs (BPS-16)',
        'board': 'fpsc',
        'desc': 'FPSC consolidated advertisement for Inspector Customs in Federal Board of Revenue.',
    },
    {
        'title': 'Assistant Director Wildlife (BPS-17)',
        'board': 'ppsc',
        'desc': 'PPSC vacancy for Assistant Director Wildlife in Forest Department, Punjab.',
    },
    {
        'title': 'Senior Auditor (BPS-16)',
        'board': 'fpsc',
        'desc': 'FPSC advertisement for Senior Auditor posts in Auditor General Office.',
    },
    {
        'title': 'Sub Inspector (BPS-14)',
        'board': 'kppsc',
        'desc': 'KPPSC is hiring Sub Inspectors for KPK Police Department.',
    },
    {
        'title': 'Lecturer (Economics) BPS-17',
        'board': 'ppsc',
        'desc': 'PPSC invites applications for Lecturer Economics in Government Colleges.',
    },
    {
        'title': 'Junior Clerk (BPS-09)',
        'board': 'nts',
        'desc': 'NTS test for Junior Clerk posts in various federal ministries.',
    },
]


class Command(BaseCommand):
    help = 'Scrape MCQs, Current Affairs, and Government Jobs with AI optimization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['all', 'mcqs', 'current-affairs', 'jobs'],
            help='Which pipeline to run: all, mcqs, current-affairs, jobs',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Print extra debug output (raw scraped data)',
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=int(os.environ.get('SCRAPE_MAX_PAGES', '0')),
            help='Max pages per category to scrape (0 = auto-detect all pages)',
        )
        parser.add_argument(
            '--start-page',
            type=int,
            default=1,
            help='Page number to start scraping from (default: 1)',
        )

    def write_safe(self, msg, style_func=None):
        """Write to stdout safely by ignoring unencodable characters for Windows terminals."""
        clean_msg = str(msg).encode('ascii', errors='ignore').decode('ascii')
        if style_func:
            self.stdout.write(style_func(clean_msg))
        else:
            self.stdout.write(clean_msg)

    def stop_requested(self) -> bool:
        return scraper_control.should_stop()

    def log_stop_save(self, label: str):
        self.stdout.write(self.style.WARNING(
            f'  [STOP] Stop requested. Saving collected {label} before exit...'
        ))

    def infer_current_affairs_category(self, question: str, region: str = ''):
        """Match a current-affairs MCQ to the configured Pakistan/World category."""
        qs = CurrentAffairsCategory.objects.filter(is_active=True)
        if region in ('pakistan', 'world'):
            qs = qs.filter(region=region)

        question_lower = (question or '').lower()
        for category in qs.order_by('sort_order', 'name'):
            keywords = category.keyword_list() or [category.slug.replace('-', ' ')]
            if any(keyword.lower() in question_lower for keyword in keywords):
                return category
        return None

    def get_last_page(self, base_url: str, headers: dict) -> int:
        """Auto-detect the total number of pages for a pakmcqs.com category."""
        try:
            resp = requests.get(base_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return 1
            soup = BeautifulSoup(resp.content, 'html.parser')
            # pakmcqs uses class 'page-numbers' on <a> and <span> tags
            page_links = soup.select('a.page-numbers')
            nums = []
            for a in page_links:
                txt = a.get_text(strip=True)
                if txt.isdigit():
                    nums.append(int(txt))
            return max(nums) if nums else 1
        except Exception:
            return 1

    def handle(self, *args, **options):
        self.debug = options['debug']
        self.max_pages = options['max_pages']  # 0 = auto-detect
        self.start_page = options['start_page']
        dtype = options['type']

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n====================================================\n'
            '  ImtihanHub - AI-Powered Scraping Pipeline\n'
            '===================================================='
        ))

        # Ensure core DB objects exist
        self.ensure_basics()

        # Initialise the scraper suite
        suite = AIScraperSuite()

        if dtype in ('all', 'mcqs'):
            self.scrape_mcqs_pipeline(suite)

        if dtype in ('all', 'current-affairs') and not self.stop_requested():
            self.scrape_current_affairs_pipeline(suite)

        if dtype in ('all', 'jobs') and not self.stop_requested():
            self.scrape_jobs_pipeline(suite)

        if self.stop_requested():
            self.stdout.write(self.style.WARNING(
                '[STOP] Remaining pipelines skipped after stop request.'
            ))

        # Print final counts
        self.stdout.write(self.style.SUCCESS(
            f'\n[+] Done! DB now has: '
            f'{MCQ.objects.count()} MCQs  |  '
            f'{JobListing.objects.count()} Jobs'
        ))

    # ── SETUP ─────────────────────────────────────────────────────────────────

    def ensure_basics(self):
        """Create Exam and Subject records if they do not exist yet."""
        self.stdout.write(self.style.MIGRATE_LABEL('\n[Setup] Ensuring Exams and Subjects exist...'))

        exams = [
            ('PPSC', 'ppsc', 'green'),
            ('FPSC', 'fpsc', 'blue'),
            ('NTS',  'nts',  'amber'),
            ('SPSC', 'spsc', 'purple'),
            ('KPPSC','kppsc','red'),
            ('BPSC', 'bpsc', 'green'),
            ('OTS',  'ots',  'blue'),
        ]
        for name, slug, color in exams:
            obj, created = Exam.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'badge_color': color}
            )
            if created:
                self.stdout.write(f'  [+] Exam created: {name}')

        subjects = [
            ('Pakistan Studies', 'pakistan-studies'),
            ('English',          'english'),
            ('General Knowledge','general-knowledge'),
            ('Mathematics',      'mathematics'),
            ('Islamiat',         'islamiat'),
            ('Computer Science', 'computer-science'),
            ('Current Affairs',  'current-affairs'),
            ('Urdu',             'urdu'),
            ('Everyday Science', 'everyday-science'),
            ('Law',              'law'),
            ('Pedagogy',         'pedagogy'),
            ('Geography',        'geography'),
        ]
        for name, slug in subjects:
            obj, created = Subject.objects.get_or_create(
                slug=slug,
                defaults={'name': name}
            )
            if created:
                self.stdout.write(f'  [+] Subject created: {name}')

    # ── PIPELINE 1: MCQs ──────────────────────────────────────────────────────

    def scrape_mcqs_pipeline(self, suite: AIScraperSuite):
        self.stdout.write(self.style.MIGRATE_HEADING('\n[MCQ Pipeline] Starting...'))

        raw_items = []

        # ── Source 1: Paginated PakMCQs Category Endpoints ────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL('  [1/3] Scraping Paginated PakMCQs Categories...'))
        
        categories = [
            ('pak-study-mcqs',          'pakistan-studies',   'ppsc'),
            ('general_knowledge_mcqs',  'general-knowledge',  'ppsc'),
            ('islamic-studies-mcqs',    'islamiat',           'ppsc'),
            ('everyday-science-mcqs',   'everyday-science',   'ppsc'),
            ('english-mcqs',            'english',            'fpsc'),
            ('mathematics-mcqs',        'mathematics',        'ppsc'),
            ('computer-mcqs',           'computer-science',   'ppsc'),
            ('pedagogy-mcqs',           'pedagogy',           'ppsc'),
            ('urdu-general-knowledge',  'urdu',               'ppsc'),
        ]

        stop_collection = False
        for cat_slug, subject_slug, exam_slug in categories:
            if self.stop_requested():
                self.log_stop_save('MCQs')
                stop_collection = True
                break
            self.stdout.write(self.style.MIGRATE_LABEL(f'    -> Category: {cat_slug} ({subject_slug})...'))
            base_url = f'https://pakmcqs.com/category/{cat_slug}'

            # Auto-detect or use user-supplied max pages
            if self.max_pages and self.max_pages > 0:
                last_page = self.start_page + self.max_pages - 1
                self.stdout.write(f'      Pages limited to {self.max_pages} (Pages {self.start_page} to {last_page})')
            else:
                last_page = self.get_last_page(base_url, suite.headers)
                self.stdout.write(f'      Auto-detected {last_page} page(s) for {cat_slug}')
                # ensure last_page isn't lower than start_page
                if last_page < self.start_page:
                    last_page = self.start_page

            for page in range(self.start_page, last_page + 1):
                if self.stop_requested():
                    self.log_stop_save('MCQs')
                    stop_collection = True
                    break
                url = base_url if page == 1 else f'{base_url}/page/{page}'
                self.stdout.write(f'      Scraping page {page}/{last_page}: {url}')
                items = suite.scrape_pakmcqs_category(url, debug=self.debug)
                for item in items:
                    raw_items.append({
                        'question': item['question'],
                        'options': item['options'],
                        'correct': item['correct'],
                        'subject': subject_slug,
                        'exam': exam_slug,
                    })
                if self.stop_requested():
                    self.log_stop_save('MCQs')
                    stop_collection = True
                    break
                time.sleep(1.2)  # polite delay between pages

            if stop_collection:
                break

        # ── Source 2: cssmcqs.com ─────────────────────────────────────────────
        elements2 = []
        if not self.stop_requested():
            self.stdout.write(self.style.MIGRATE_LABEL('  [2/3] Scraping cssmcqs.com...'))
            url2 = 'https://cssmcqs.com'
            elements2 = suite.scrape_static(
                url2,
                '.mcq-question, .question-text, article h3, .entry-content p strong'
            )
            if self.debug:
                self.stdout.write(f'  [DEBUG] cssmcqs raw: {len(elements2)} items')

        for text in elements2:
            if self.stop_requested():
                self.log_stop_save('MCQs')
                break
            if suite._is_valid_mcq(text):
                raw_items.append({
                    'question': text,
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'correct': 'A',
                    'subject': 'pakistan-studies',
                    'exam': 'fpsc',
                })

        # ── Source 3: English MCQs ────────────────────────────────────────────
        elements3 = []
        if not self.stop_requested():
            self.stdout.write(self.style.MIGRATE_LABEL('  [3/3] Scraping English MCQs...'))
            url3 = 'https://www.pakmcqs.com/english-mcqs'
            elements3 = suite.scrape_static(
                url3,
                '.single-question .question-title, h2.question-title'
            )
        for text in elements3:
            if self.stop_requested():
                self.log_stop_save('MCQs')
                break
            if suite._is_valid_mcq(text):
                raw_items.append({
                    'question': text,
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'correct': 'A',
                    'subject': 'english',
                    'exam': 'fpsc',
                })

        # ── Self-healing fallback ─────────────────────────────────────────────
        if not raw_items and not self.stop_requested():
            self.stdout.write(self.style.WARNING(
                '  [!] Live scraping returned nothing — loading seed MCQs.'
            ))
            raw_items = [
                {**m, 'options': m['options']}
                for m in SEED_MCQS
            ]

        # ── Deduplicate with Pandas ───────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL(
            f'  [Clean] Deduplicating {len(raw_items)} raw items...'
        ))
        cleaned = suite.clean_scraped_items(raw_items, text_key='question')
        self.stdout.write(f'  [Clean] {len(cleaned)} unique MCQs after dedup.')

        # ── AI optimize and save ──────────────────────────────────────────────
        created_count = 0
        updated_count = 0

        for item in cleaned:
            self.write_safe(
                f'  [AI] Processing: "{item["question"][:55]}..."',
                self.style.MIGRATE_LABEL
            )

            try:
                optimized = suite.optimize_mcq(item['question'], item['options'], item.get('correct'))
                if self.debug:
                    self.stdout.write(
                        f'    [DEBUG] Correct option source={item.get("correct", "")} '
                        f'saved={optimized.get("correct_option", "")}'
                    )

                # Look up related objects
                try:
                    subj = Subject.objects.get(slug=item['subject'])
                except Subject.DoesNotExist:
                    subj = Subject.objects.get(slug='general-knowledge')

                try:
                    ex = Exam.objects.get(slug=item['exam'])
                except Exam.DoesNotExist:
                    ex = Exam.objects.get(slug='ppsc')

                # ✅ FIX: use update_or_create so records always save
                mcq_obj, created = MCQ.objects.update_or_create(
                    question_text=optimized['question'],
                    defaults={
                        'option_a':       optimized['options'][0],
                        'option_b':       optimized['options'][1],
                        'option_c':       optimized['options'][2],
                        'option_d':       optimized['options'][3],
                        'correct_option': optimized['correct_option'],
                        'exam':           ex,
                        'subject':        subj,
                        'status':         'published',
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'    [+] Created MCQ'))
                else:
                    updated_count += 1
                    if self.debug:
                        self.stdout.write(f'    [~] Updated existing MCQ')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    [ERR] Error saving MCQ: {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(
            f'\n[MCQ Pipeline] Done — Created: {created_count}  Updated: {updated_count}'
        ))

        if created_count > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'Scraper imported {created_count} new MCQs',
                    color='#1D9E75',
                )
            except Exception:
                pass  # ActivityLog is optional

    # ── PIPELINE 2: Current Affairs ───────────────────────────────────────────

    def scrape_current_affairs_pipeline(self, suite: AIScraperSuite):
        self.stdout.write(self.style.MIGRATE_HEADING('\n[Current Affairs Pipeline] Starting...'))

        raw_items = []

        # ── Source 1: testpointpk.com ─────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_LABEL('  [1/3] Scraping testpointpk.com...'))
        urls = [
            'https://testpointpk.com/monthly-current-affairs',
            'https://testpointpk.com/current-affairs-mcqs',
        ]
        elements = suite.scrape_scrapy(
            urls,
            '.mcq-block, .question-card, .question-title, h3.question'
        )
        if self.debug:
            self.stdout.write(f'  [DEBUG] testpointpk raw: {len(elements)} items')

        for text in elements:
            if self.stop_requested():
                self.log_stop_save('current affairs')
                break
            if suite._is_valid_mcq(text):
                raw_items.append({
                    'question': text,
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'correct': 'A',
                    'exam': 'fpsc',
                })

        # ── Source 2: Pakistan Current Affairs MCQs (Month-Wise) ─────────
        self.stdout.write(self.style.MIGRATE_LABEL('  [2/3] Scraping Pakistan Current Affairs MCQs Month-Wise...'))
        current_year = timezone.now().year
        
        # Scrape last year and current year
        stop_collection = False
        for year in [current_year - 1, current_year]:
            if self.stop_requested():
                self.log_stop_save('current affairs')
                stop_collection = True
                break
            for month in range(1, 13):
                if self.stop_requested():
                    self.log_stop_save('current affairs')
                    stop_collection = True
                    break
                for page in range(1, 6): # Max 5 pages per month
                    if self.stop_requested():
                        self.log_stop_save('current affairs')
                        stop_collection = True
                        break
                    if page == 1:
                        url = f'https://pakmcqs.com/{year}/{month:02d}?cat=70'
                    else:
                        url = f'https://pakmcqs.com/{year}/{month:02d}/page/{page}?cat=70'
                    
                    self.stdout.write(f'    Scraping {year}/{month:02d} page {page}: {url}')
                    items = suite.scrape_pakmcqs_category(url, debug=self.debug)
                    
                    if not items:
                        if page == 1:
                            self.stdout.write(self.style.WARNING(f'    [!] No items found for {year}/{month:02d}.'))
                        break
                        
                    self.stdout.write(self.style.SUCCESS(f'    [+] Found {len(items)} MCQs'))
                    for item in items:
                        if self.debug:
                            self.stdout.write(f'      [DEBUG] Found: "{item["question"][:50]}..."')
                        raw_items.append({
                            'question': item['question'],
                            'options': item['options'],
                            'correct': item['correct'],
                            'exam': 'fpsc',
                            'current_affairs_region': 'pakistan',
                            'target_date': datetime(year, month, 15)
                        })
                    if self.stop_requested():
                        self.log_stop_save('current affairs')
                        stop_collection = True
                        break
                    time.sleep(1.0)
                if stop_collection:
                    break
            if stop_collection:
                break

        # ── Source 3: World Current Affairs MCQs (Month-Wise) ────────────
        self.stdout.write(self.style.MIGRATE_LABEL('  [3/3] Scraping World Current Affairs MCQs Month-Wise...'))
        
        # Scrape last year and current year
        stop_collection = False
        for year in [current_year - 1, current_year]:
            if self.stop_requested():
                self.log_stop_save('current affairs')
                stop_collection = True
                break
            for month in range(1, 13):
                if self.stop_requested():
                    self.log_stop_save('current affairs')
                    stop_collection = True
                    break
                for page in range(1, 6): # Max 5 pages per month
                    if self.stop_requested():
                        self.log_stop_save('current affairs')
                        stop_collection = True
                        break
                    if page == 1:
                        url = f'https://pakmcqs.com/{year}/{month:02d}?cat=37'
                    else:
                        url = f'https://pakmcqs.com/{year}/{month:02d}/page/{page}?cat=37'
                    
                    self.stdout.write(f'    Scraping {year}/{month:02d} page {page}: {url}')
                    items = suite.scrape_pakmcqs_category(url, debug=self.debug)
                    
                    if not items:
                        if page == 1:
                            self.stdout.write(self.style.WARNING(f'    [!] No items found for {year}/{month:02d}.'))
                        break
                        
                    self.stdout.write(self.style.SUCCESS(f'    [+] Found {len(items)} MCQs'))
                    for item in items:
                        if self.debug:
                            self.stdout.write(f'      [DEBUG] Found: "{item["question"][:50]}..."')
                        raw_items.append({
                            'question': item['question'],
                            'options': item['options'],
                            'correct': item['correct'],
                            'exam': 'fpsc',
                            'current_affairs_region': 'world',
                            'target_date': datetime(year, month, 15)
                        })
                    if self.stop_requested():
                        self.log_stop_save('current affairs')
                        stop_collection = True
                        break
                    time.sleep(1.0)
                if stop_collection:
                    break
            if stop_collection:
                break

        # ── Self-healing fallback ─────────────────────────────────────────────
        if not raw_items and not self.stop_requested():
            self.stdout.write(self.style.WARNING(
                '  [!] Live scraping returned nothing — loading seed Current Affairs.'
            ))
            raw_items = list(SEED_CURRENT_AFFAIRS)

        # ── Deduplicate ───────────────────────────────────────────────────────
        cleaned = suite.clean_scraped_items(raw_items, text_key='question')
        self.stdout.write(f'  [Clean] {len(cleaned)} unique items after dedup.')

        # ── AI optimize and save ──────────────────────────────────────────────
        try:
            subj = Subject.objects.get(slug='current-affairs')
        except Subject.DoesNotExist:
            subj = Subject.objects.get(slug='general-knowledge')

        created_count = 0
        updated_count = 0

        for item in cleaned:
            self.write_safe(
                f'  [AI] Processing: "{item["question"][:55]}..."',
                self.style.MIGRATE_LABEL
            )
            try:
                optimized = suite.optimize_mcq(item['question'], item['options'], item.get('correct'))
                if self.debug:
                    self.stdout.write(
                        f'    [DEBUG] Correct option source={item.get("correct", "")} '
                        f'saved={optimized.get("correct_option", "")}'
                    )

                try:
                    ex = Exam.objects.get(slug=item['exam'])
                except Exam.DoesNotExist:
                    ex = Exam.objects.get(slug='fpsc')
                current_affairs_category = self.infer_current_affairs_category(
                    optimized['question'],
                    item.get('current_affairs_region', ''),
                )

                # ✅ FIX: update_or_create
                mcq_obj, created = MCQ.objects.update_or_create(
                    question_text=optimized['question'],
                    defaults={
                        'option_a':       optimized['options'][0],
                        'option_b':       optimized['options'][1],
                        'option_c':       optimized['options'][2],
                        'option_d':       optimized['options'][3],
                        'correct_option': optimized['correct_option'],
                        'exam':           ex,
                        'subject':        subj,
                        'current_affairs_category': current_affairs_category,
                        'status':         'published',
                    }
                )
                # Stamp with correct date so month selector works flawlessly
                target_date = item.get('target_date', timezone.now())
                if timezone.is_naive(target_date):
                    target_date = timezone.make_aware(target_date)
                MCQ.objects.filter(pk=mcq_obj.pk).update(created_at=target_date)

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'    [+] Created'))
                else:
                    updated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    [ERR] Error: {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(
            f'\n[Current Affairs Pipeline] Done — Created: {created_count}  Updated: {updated_count}'
        ))

        if created_count > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'Scraper imported {created_count} Current Affairs MCQs',
                    color='#854F0B',
                )
            except Exception:
                pass

    # ── PIPELINE 3: Government Jobs ───────────────────────────────────────────

    def scrape_jobs_pipeline(self, suite: AIScraperSuite):
        self.stdout.write(self.style.MIGRATE_HEADING('\n[Job Pipeline] Starting...'))

        raw_jobs = []

        # ── Job sources with CORRECT URLs and selectors ───────────────────────
        # These point to the actual advertised-posts pages, not homepages
        job_sources = [
            {
                'url':      'https://www.ppsc.gop.pk/Advts',
                'board':    'ppsc',
                'selector': 'table.table tbody tr td:nth-child(2), '
                            '.advt-title, .job-post-title, '
                            'td.text-left a, table tr td a',
                'engine':   'playwright',  # PPSC uses JS rendering
            },
            {
                'url':      'https://fpsc.gov.pk/home',
                'board':    'fpsc',
                'selector': '.announcement a, .news-item a, '
                            'table tr td:nth-child(2) a, '
                            '.jobs-list li a',
                'engine':   'playwright',
            },
            {
                'url':      'https://www.fpsc.gov.pk/Jobs?section=GR',
                'board':    'fpsc',
                'selector': 'table tr td a, .job-title, .announcement a, .news-item a, a[href*="job"], a[href*="advertisement"]',
                'engine':   'playwright',
            },
            {
                'url':      'https://www.fpsc.gov.pk/api/jobs',
                'board':    'fpsc',
                'selector': 'a[href*="job"], table tr td a',
                'engine':   'api',
            },
            {
                'url':      'https://spsc.gos.pk/jobs',
                'board':    'spsc',
                'selector': 'table tr td a, .job-title, h4 a',
                'engine':   'static',
            },
            {
                'url':      'https://spsc.gos.pk/',
                'board':    'spsc',
                'selector': 'table tr td a, .job-title, h4 a, a[href*="job"], a[href*="advertisement"]',
                'engine':   'static',
            },
            {
                'url':      'https://www.bpsc.gob.pk/BPSC/pages?jobs',
                'board':    'bpsc',
                'selector': 'table tr td a, .job-title, h4 a, a[href*="job"], tr td:nth-child(2)',
                'engine':   'playwright',
            },
            {
                'url':      'https://www.nts.org.pk/nts/latest-jobs.php',
                'board':    'nts',
                'selector': 'table tr td:nth-child(2), '
                            '.jobs-table td.job-name, '
                            'td a[href*="test"]',
                'engine':   'static',
            },
        ]

        for src in job_sources:
            if self.stop_requested():
                self.log_stop_save('jobs')
                break

            self.stdout.write(self.style.MIGRATE_LABEL(
                f'  [Scrape] {src["board"].upper()} — {src["url"]}'
            ))

            elements = []
            if src['engine'] == 'api':
                try:
                    resp = suite.session.get(src['url'], timeout=suite.timeout)
                    if resp.status_code == 200:
                        try:
                            # Try to parse as JSON
                            data = resp.json()
                            jobs_list = []
                            if isinstance(data, list):
                                jobs_list = data
                            elif isinstance(data, dict):
                                jobs_list = data.get('jobs') or data.get('results') or data.get('data') or []
                            
                            if isinstance(jobs_list, list):
                                for job_item in jobs_list:
                                    title = job_item.get('title') or job_item.get('name') or job_item.get('job_title')
                                    desc = job_item.get('description') or job_item.get('details') or f'Official vacancy announced by {src["board"].upper()}.'
                                    if title and suite._is_valid_job(title):
                                        raw_jobs.append({
                                            'title': title.strip(),
                                            'board': src['board'],
                                            'desc':  desc.strip(),
                                        })
                                self.stdout.write(self.style.SUCCESS(f'    [+] API scraped {len(jobs_list)} items successfully.'))
                        except Exception:
                            # Fallback to static HTML parsing if endpoint returns HTML instead of JSON
                            elements = suite.scrape_static(src['url'], src['selector'])
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  [ERR] API fetch failed: {e}'))
            elif src['engine'] == 'playwright':
                elements = suite.scrape_playwright(src['url'], src['selector'])
            else:
                elements = suite.scrape_static(src['url'], src['selector'])

            if self.debug and elements:
                self.stdout.write(f'  [DEBUG] {src["board"]} raw: {len(elements)} items')
                for i, el in enumerate(elements[:4]):
                    self.stdout.write(f'    [{i}] {repr(el[:80])}')

            for title in elements:
                if self.stop_requested():
                    self.log_stop_save('jobs')
                    break
                title = title.strip()
                if suite._is_valid_job(title):
                    raw_jobs.append({
                        'title': title,
                        'board': src['board'],
                        'desc':  f'Official vacancy announced by {src["board"].upper()}.',
                    })

            if self.stop_requested():
                self.log_stop_save('jobs')
                break
            time.sleep(1.5)  # polite delay between sources

        # ── Self-healing fallback ─────────────────────────────────────────────
        if not raw_jobs and not self.stop_requested():
            self.stdout.write(self.style.WARNING(
                '  [!] Live job scraping returned nothing — loading seed jobs.'
            ))
            raw_jobs = list(SEED_JOBS)

        # ── Deduplicate ───────────────────────────────────────────────────────
        cleaned_jobs = suite.clean_scraped_items(raw_jobs, text_key='title')
        self.stdout.write(f'  [Clean] {len(cleaned_jobs)} unique jobs after dedup.')

        # ── AI optimize and save ──────────────────────────────────────────────
        created_count = 0
        updated_count = 0

        for item in cleaned_jobs:
            self.stdout.write(
                self.style.MIGRATE_LABEL(
                    f'  [AI] Structuring: "{item["title"]}"'
                )
            )
            try:
                optimized = suite.optimize_job(
                    item['title'], item['desc'], item['board']
                )

                try:
                    ex = Exam.objects.get(slug=item['board'])
                except Exam.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'    [!] Board "{item["board"]}" not found — skipping.'
                    ))
                    continue

                # ✅ FIX: update_or_create
                job_obj, created = JobListing.objects.update_or_create(
                    title=optimized['title'],
                    exam=ex,
                    defaults={
                        'department':  optimized['department'],
                        'location':    optimized['location'],
                        'bps_grade':   optimized['bps_grade'],
                        'description': optimized['description'],
                        'last_date':   datetime.now().date() + timedelta(days=30),
                        'apply_link':  f'https://www.{item["board"]}.gov.pk',
                        'status':      'active',
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'    [+] Created: {optimized["title"]} ({optimized["bps_grade"]})'
                    ))
                else:
                    updated_count += 1
                    if self.debug:
                        self.stdout.write(f'    [~] Updated: {optimized["title"]}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    [ERR] Error saving job: {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(
            f'\n[Job Pipeline] Done — Created: {created_count}  Updated: {updated_count}'
        ))

        if created_count > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='job_posted',
                    message=f'Scraper published {created_count} new job listings',
                    color='#185FA5',
                )
            except Exception:
                pass
