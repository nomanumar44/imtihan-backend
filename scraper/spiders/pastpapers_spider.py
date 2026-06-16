"""
pastpapers_spider.py — Scrapy spider for pastpaperspdf.com

Uses the WordPress REST API to discover posts, then parses each post
for Q./Answer: one-liner pairs, yielding MCQItem for DjangoPipeline.

Usage (from project root):
    scrapy crawl pastpapers -s EXAM=pms -s MAX_POSTS=20
    scrapy crawl pastpapers -s EXAM=ppsc -s SUBJECT_KW=gk
"""
import re
import json
import scrapy
from scraper.items import MCQItem

WP_API = 'https://pastpaperspdf.com/wp-json/wp/v2/posts'

EXAM_SEARCH = {
    'ppsc':     'ppsc',
    'fpsc':     'fpsc',
    'pms':      'pms',
    'motorway': 'motorway police',
}

SUBJECT_MAP = {
    'general knowledge': 'general-knowledge',
    'general science':   'everyday-science',
    'everyday science':  'everyday-science',
    'pakistan stud':     'pakistan-studies',
    'islamiat':          'islamiat',
    'computer':          'computer-science',
    'english':           'english',
    'urdu':              'urdu',
    'mathematics':       'mathematics',
    'current affairs':   'current-affairs',
    'geography':         'geography',
    'pedagogy':          'pedagogy',
    'gk':                'general-knowledge',
    'science':           'everyday-science',
}

GENERIC_DISTRACTORS = {
    'year':    ['1947', '1962', '1971', '1988', '2001', '2005', '2010', '2015'],
    'number':  ['5', '7', '10', '12', '15', '20', '25', '50'],
    'country': ['India', 'China', 'USA', 'UK', 'Iran', 'Turkey', 'Russia'],
    'city':    ['Lahore', 'Karachi', 'Islamabad', 'Peshawar', 'Quetta', 'Multan'],
    'person':  ['Allama Iqbal', 'Liaquat Ali Khan', 'Ayub Khan', 'Zulfikar Ali Bhutto'],
    'default': ['None of these', 'All of these', 'Cannot be determined'],
}


def _infer_subject(text):
    t = text.lower()
    for kw, slug in SUBJECT_MAP.items():
        if kw in t:
            return slug
    return 'general-knowledge'


def _extract_year(text):
    m = re.search(r'(20\d{2})', text)
    return int(m.group(1)) if m else 0


def _guess_pool(correct):
    c = correct.strip().lower()
    if re.match(r'^\d{4}$', c):
        return 'year'
    if re.match(r'^\d+(\.\d+)?(%|cm|km|kg|m)?$', c):
        return 'number'
    if any(h in c for h in ['pakistan', 'india', 'china', 'usa', 'uk', 'iran',
                             'turkey', 'russia', 'france', 'germany', 'saudi']):
        return 'country'
    if any(h in c for h in ['lahore', 'karachi', 'islamabad', 'peshawar',
                             'quetta', 'kabul', 'delhi', 'london']):
        return 'city'
    if any(h in c for h in ['ali', 'khan', 'bhutto', 'sharif', 'iqbal',
                             'jinnah', 'musharraf']):
        return 'person'
    return 'default'


def _pick_distractors(correct, pool_key='default'):
    pool = GENERIC_DISTRACTORS.get(pool_key, GENERIC_DISTRACTORS['default'])
    return [d for d in pool if d.lower() != correct.lower()][:2]


def _parse_qa_pairs(text):
    pairs = []
    lines = [l.strip() for l in text.split('\n')]
    i = 0
    while i < len(lines):
        line = lines[i]
        q_match = re.match(r'^Q\.?\s*\d*[:.]?\s*(.+\?)\s*$', line, re.IGNORECASE)
        if q_match:
            question = q_match.group(1).strip()
            j = i + 1
            answer = ''
            while j < len(lines):
                candidate = lines[j].strip()
                if re.match(r'^[Aa]nswer\s*:', candidate):
                    inline = re.sub(r'^[Aa]nswer\s*:\s*', '', candidate).strip()
                    if inline:
                        answer = inline
                    else:
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


def _build_mcq(question, correct, idx):
    pool_key = _guess_pool(correct)
    distractors = _pick_distractors(correct, pool_key)
    while len(distractors) < 2:
        distractors.append('None of these')
    pos = idx % 3
    opts = distractors[:2]
    opts.insert(pos, correct)
    opts = opts[:3]
    while len(opts) < 3:
        opts.append('None of these')
    correct_letter = ['A', 'B', 'C'][opts.index(correct)]
    return opts, correct_letter


class PastPapersSpider(scrapy.Spider):
    name = 'pastpapers'
    custom_settings = {
        'DOWNLOAD_DELAY': 1.5,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exam       = getattr(self, 'EXAM', 'all').lower()
        self.max_posts  = int(getattr(self, 'MAX_POSTS', 0))
        self.subject_kw = getattr(self, 'SUBJECT_KW', '').lower()
        self._post_count = 0

    def start_requests(self):
        exams = (
            list(EXAM_SEARCH.items())
            if self.exam == 'all'
            else [(self.exam, EXAM_SEARCH.get(self.exam, self.exam))]
        )
        for exam_slug, search_term in exams:
            url = (
                f'{WP_API}?search={search_term.replace(" ", "%20")}'
                f'&per_page=20&page=1&_fields=id,title,link'
            )
            yield scrapy.Request(
                url,
                callback=self.parse_api,
                meta={'exam_slug': exam_slug, 'page': 1},
                headers={'Accept': 'application/json'},
            )

    def parse_api(self, response):
        exam_slug = response.meta['exam_slug']
        page      = response.meta['page']

        try:
            data = json.loads(response.text)
        except Exception:
            return

        if not data:
            return

        for post in data:
            if self.max_posts and self._post_count >= self.max_posts:
                return
            url   = post.get('link', '')
            title_raw = post.get('title', {})
            title = (title_raw.get('rendered', '') if isinstance(title_raw, dict)
                     else str(title_raw))
            title = re.sub(r'&#\d+;|&amp;|&quot;|&#038;', '&', title).strip()

            if self.subject_kw and self.subject_kw not in title.lower():
                continue

            self._post_count += 1
            yield scrapy.Request(
                url,
                callback=self.parse_post,
                meta={
                    'exam_slug':   exam_slug,
                    'paper_title': title,
                    'paper_url':   url,
                    'paper_year':  _extract_year(title),
                    'subject_slug': _infer_subject(title),
                }
            )

        if len(data) == 20:
            next_url = (
                f'{WP_API}?search='
                + EXAM_SEARCH.get(exam_slug, exam_slug).replace(' ', '%20')
                + f'&per_page=20&page={page + 1}&_fields=id,title,link'
            )
            yield scrapy.Request(
                next_url,
                callback=self.parse_api,
                meta={'exam_slug': exam_slug, 'page': page + 1},
                headers={'Accept': 'application/json'},
            )

    def parse_post(self, response):
        exam_slug    = response.meta['exam_slug']
        paper_title  = response.meta['paper_title']
        paper_url    = response.meta['paper_url']
        paper_year   = response.meta['paper_year']
        subject_slug = response.meta['subject_slug']

        content = response.css('.entry-content, .post-content, article .content')
        if not content:
            return

        full_text = ' '.join(content.css('*::text').getall())
        full_text = re.sub(r'[ \t]+', ' ', full_text)
        full_text = re.sub(r'\n\s*\n', '\n', full_text)

        pairs = _parse_qa_pairs(full_text)

        for i, (question, answer) in enumerate(pairs):
            opts, correct_letter = _build_mcq(question, answer, i)
            yield MCQItem(
                question=question,
                option_a=opts[0],
                option_b=opts[1],
                option_c=opts[2],
                correct=correct_letter,
                explanation=f'Correct answer: {answer}',
                exam_slug=exam_slug,
                subject_slug=subject_slug,
                source_url=paper_url,
                paper_title=paper_title,
                paper_url=paper_url,
                paper_year=paper_year,
            )
