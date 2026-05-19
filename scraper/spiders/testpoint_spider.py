"""
testpoint_spider.py — Scrapy spider for testpointpk.com

Crawls PPSC/FPSC subject-wise past paper MCQ pages, extracts questions
with 3 options and correct answer, yields MCQItem for DjangoPipeline.

Usage (from project root):
    scrapy crawl testpoint -s EXAM=ppsc -s MAX_PAPERS=5
    scrapy crawl testpoint -s EXAM=fpsc -s SUBJECT_KW=english
"""
import re
import scrapy
from scraper.items import MCQItem

EXAM_INDEX_PAGES = {
    'ppsc': 'https://testpointpk.com/past-papers-mcqs/ppsc-5-years-past-papers-subject-wise-(solved-with-details)',
    'fpsc': 'https://testpointpk.com/past-papers-mcqs/fpsc-5-years-past-papers-subject-wise-(solved-with-details)',
}

SUBJECT_MAP = {
    'general knowledge': 'general-knowledge',
    'general science':   'everyday-science',
    'everyday science':  'everyday-science',
    'pakistan stud':     'pakistan-studies',
    'islamiat':          'islamiat',
    'islamic study':     'islamiat',
    'computer':          'computer-science',
    'english':           'english',
    'urdu':              'urdu',
    'mathematics':       'mathematics',
    'basic math':        'mathematics',
    'current affairs':   'current-affairs',
    'geography':         'geography',
    'pedagogy':          'pedagogy',
    'law':               'law',
}

BASE_URL = 'https://testpointpk.com'


def _infer_subject(text):
    t = text.lower()
    for kw, slug in SUBJECT_MAP.items():
        if kw in t:
            return slug
    return 'general-knowledge'


def _extract_year(text):
    m = re.search(r'(20\d{2})', text)
    return int(m.group(1)) if m else 0


class TestPointSpider(scrapy.Spider):
    name = 'testpoint'
    custom_settings = {
        'DOWNLOAD_DELAY': 1.5,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exam       = getattr(self, 'EXAM', 'ppsc').lower()
        self.max_papers = int(getattr(self, 'MAX_PAPERS', 0))
        self.subject_kw = getattr(self, 'SUBJECT_KW', '').lower()
        self._paper_count = 0

    def start_requests(self):
        exams = (
            list(EXAM_INDEX_PAGES.items())
            if self.exam == 'all'
            else [(self.exam, EXAM_INDEX_PAGES.get(self.exam, EXAM_INDEX_PAGES['ppsc']))]
        )
        for exam_slug, url in exams:
            yield scrapy.Request(url, callback=self.parse_index,
                                 meta={'exam_slug': exam_slug})

    def parse_index(self, response):
        exam_slug = response.meta['exam_slug']
        links = response.css('a[href*="/paper-mcqs/"]')
        papers = []
        seen = set()
        for a in links:
            href = a.attrib.get('href', '').strip()
            if not href:
                continue
            if href.startswith('/'):
                href = BASE_URL + href
            if href in seen:
                continue
            seen.add(href)
            title = a.css('::text').get('').strip()
            if self.subject_kw and self.subject_kw not in title.lower():
                continue
            papers.append({'url': href, 'title': title})

        for paper in papers:
            if self.max_papers and self._paper_count >= self.max_papers:
                break
            self._paper_count += 1
            yield scrapy.Request(
                paper['url'],
                callback=self.parse_paper,
                meta={
                    'exam_slug':   exam_slug,
                    'paper_title': paper['title'],
                    'paper_url':   paper['url'],
                    'paper_year':  _extract_year(paper['title']),
                    'subject_slug': _infer_subject(paper['title']),
                }
            )

    def parse_paper(self, response):
        exam_slug    = response.meta['exam_slug']
        paper_title  = response.meta['paper_title']
        paper_url    = response.meta['paper_url']
        paper_year   = response.meta['paper_year']
        subject_slug = response.meta['subject_slug']

        for ol in response.css('ol[type="A"]'):
            # Find question text in preceding h5
            q_text = ''
            block = ol.xpath('..')
            h5 = block.css('h5 a::text').get() or block.css('h5::text').get()
            if h5:
                q_text = h5.strip()

            if not q_text or len(q_text) < 10:
                continue
            if any(w in q_text.lower() for w in ['click here', 'past papers', 'home', 'login']):
                continue

            all_options = []
            correct_idx = 0
            for i, li in enumerate(ol.css('li')):
                classes = ' '.join(li.attrib.get('class', '').split())
                text = li.css('::text').get('').strip()
                if text:
                    all_options.append(text)
                    if 'correct' in classes:
                        correct_idx = len(all_options) - 1

            if len(all_options) < 2:
                continue

            explanation = ''
            expl = response.css('.question-explanation').get('')
            if expl:
                explanation = scrapy.Selector(text=expl).css('*::text').getall()
                explanation = ' '.join(explanation).strip()[:800]

            correct_opt = all_options[correct_idx]
            distractors = [o for o in all_options if o != correct_opt][:2]
            pos = min(correct_idx, 2)
            three = distractors[:pos] + [correct_opt] + distractors[pos:]
            three = three[:3]
            while len(three) < 3:
                three.append('None of these')

            try:
                correct_letter = ['A', 'B', 'C'][three.index(correct_opt)]
            except ValueError:
                correct_letter = 'A'

            yield MCQItem(
                question=q_text,
                option_a=three[0],
                option_b=three[1],
                option_c=three[2],
                correct=correct_letter,
                explanation=explanation,
                exam_slug=exam_slug,
                subject_slug=subject_slug,
                source_url=paper_url,
                paper_title=paper_title,
                paper_url=paper_url,
                paper_year=paper_year,
            )
