"""
gotest_spider.py — Scrapy spider for gotest.com.pk

Crawls subject-wise tests, extracts questions with 4 options
and correct answer, yields MCQItem for DjangoPipeline.

Structure:
  https://gotest.com.pk/subjects-wise-test-online/  (subject index)
    → https://gotest.com.pk/general-english-online-test-preparation/ (tests list)
      → Test detail page (questions with answers)

Each question has options and answer in format:
  <li class="answer correct-answer"><span class="answer">...</span></li>

Usage (from project root):
    scrapy crawl gotest
    scrapy crawl gotest -s SUBJECT_KW=english
    scrapy crawl gotest -s MAX_TESTS=5
"""

import re
import scrapy
from scraper.items import MCQItem

BASE_URL = 'https://gotest.com.pk'
SUBJECT_INDEX = f'{BASE_URL}/subjects-wise-test-online/'

SUBJECT_MAP = {
    'english': 'english',
    'urdu': 'urdu',
    'general knowledge': 'general-knowledge',
    'general science': 'everyday-science',
    'everyday science': 'everyday-science',
    'pakistan studies': 'pakistan-studies',
    'islamiat': 'islamiat',
    'mathematics': 'mathematics',
    'computer science': 'computer-science',
}


def _infer_subject(text):
    """Map website subject name to DB subject slug."""
    t = text.lower()
    for kw, slug in SUBJECT_MAP.items():
        if kw in t:
            return slug
    return 'general-knowledge'


class GotestSpider(scrapy.Spider):
    name = 'gotest'
    allowed_domains = ['gotest.com.pk']
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_tests = int(getattr(self, 'MAX_TESTS', 0))
        self.subject_kw = getattr(self, 'SUBJECT_KW', '').lower()
        self._test_count = 0

    def start_requests(self):
        """Start by fetching subject index page."""
        yield scrapy.Request(SUBJECT_INDEX, callback=self.parse_subjects)

    def parse_subjects(self, response):
        """Extract subject links from main page."""
        # Look for subject links - typically divs or links with subject names
        subject_links = response.css('a[href*="/online-test-preparation/"]')
        
        for link in subject_links:
            href = link.attrib.get('href', '').strip()
            title = link.css('::text').get('').strip()
            
            if not href or not title:
                continue
            
            # Make absolute URL
            if href.startswith('/'):
                href = BASE_URL + href
            
            # Filter by subject keyword if specified
            if self.subject_kw and self.subject_kw not in title.lower():
                continue
            
            subject_slug = _infer_subject(title)
            
            yield scrapy.Request(
                href,
                callback=self.parse_tests,
                meta={'subject': title, 'subject_slug': subject_slug}
            )

    def parse_tests(self, response):
        """Extract test links from subject page."""
        subject = response.meta['subject']
        subject_slug = response.meta['subject_slug']
        
        # Look for test links - usually contains "test" in the URL or text
        test_links = response.css('a[href*="test"]')
        
        for link in test_links:
            href = link.attrib.get('href', '').strip()
            test_name = link.css('::text').get('').strip()
            
            if not href or not test_name:
                continue
            
            if self.max_tests and self._test_count >= self.max_tests:
                break
            
            # Make absolute URL
            if href.startswith('/'):
                href = BASE_URL + href
            
            self._test_count += 1
            
            yield scrapy.Request(
                href,
                callback=self.parse_questions,
                meta={
                    'subject': subject,
                    'subject_slug': subject_slug,
                    'test_name': test_name,
                    'test_url': href,
                }
            )

    def parse_questions(self, response):
        """Extract questions and answers from test page."""
        subject = response.meta['subject']
        subject_slug = response.meta['subject_slug']
        test_name = response.meta['test_name']
        test_url = response.meta['test_url']
        
        # Find all question containers
        questions = response.css('div.question, div.test-question, li.question, div[data-question]')
        
        if not questions:
            # Fallback: look for any divs that might contain questions
            questions = response.css('div')
        
        for idx, q_div in enumerate(questions):
            try:
                # Extract question text
                question_text = q_div.css('::text').getall()
                question_text = ' '.join([t.strip() for t in question_text if t.strip()])
                
                if not question_text or len(question_text) < 10:
                    continue
                
                # Extract options - usually in li or div elements
                options = q_div.css('li, div[class*="option"]')
                
                if len(options) < 4:
                    continue
                
                option_texts = []
                for opt in options[:4]:
                    opt_text = opt.css('::text').getall()
                    opt_text = ' '.join([t.strip() for t in opt_text if t.strip()])
                    option_texts.append(opt_text)
                
                # Find correct answer - marked with class="answer correct-answer"
                correct_answer_elem = q_div.css('li.answer.correct-answer, li.correct-answer')
                if not correct_answer_elem:
                    correct_answer_elem = q_div.css('[class*="correct"]')
                
                correct_idx = 0
                if correct_answer_elem:
                    # Try to find which option is marked as correct
                    correct_text = correct_answer_elem.css('::text').getall()
                    correct_text = ' '.join([t.strip() for t in correct_text if t.strip()])
                    
                    # Match with options to find index
                    for i, opt_text in enumerate(option_texts):
                        if correct_text in opt_text or opt_text in correct_text:
                            correct_idx = i
                            break
                
                correct_option = chr(65 + correct_idx)  # Convert 0-3 to A-D
                
                # Yield MCQItem
                yield MCQItem(
                    question=question_text,
                    option_a=option_texts[0] if len(option_texts) > 0 else '',
                    option_b=option_texts[1] if len(option_texts) > 1 else '',
                    option_c=option_texts[2] if len(option_texts) > 2 else '',
                    option_d=option_texts[3] if len(option_texts) > 3 else '',
                    correct_answer=correct_option,
                    explanation='',
                    exam_slug='gotest',
                    subject_name=subject,
                    subject_slug=subject_slug,
                    source_url=test_url,
                    test_name=test_name,
                )
            except Exception as e:
                self.logger.warning(f'Error parsing question: {e}')
                continue
