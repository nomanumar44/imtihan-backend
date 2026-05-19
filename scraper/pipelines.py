"""
DjangoPipeline — saves scraped MCQItems directly into Django models.
Must be run with Django configured (DJANGO_SETTINGS_MODULE set).
"""
import os
import re
import django
from django.utils.text import slugify


def _setup_django():
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'imtihanBackend.settings')
    try:
        django.setup()
    except RuntimeError:
        pass  # already set up


_setup_django()

from core.models import Exam, Subject, MCQ, PastPaper, ActivityLog  # noqa: E402


def _unique_slug(title: str) -> str:
    base = slugify(title)[:300] or 'paper'
    slug = base
    i = 1
    while PastPaper.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


class DjangoPipeline:
    created = 0
    updated = 0

    def open_spider(self, spider):
        self.created = 0
        self.updated = 0

    def process_item(self, item, spider):
        exam_slug    = item.get('exam_slug', 'ppsc')
        subject_slug = item.get('subject_slug', 'general-knowledge')
        paper_url    = item.get('paper_url', '')
        paper_title  = item.get('paper_title', 'Scraped Paper')
        paper_year   = item.get('paper_year', 0)

        try:
            exam_obj = Exam.objects.get(slug=exam_slug)
        except Exam.DoesNotExist:
            exam_obj, _ = Exam.objects.get_or_create(
                slug=exam_slug, defaults={'name': exam_slug.upper(), 'badge_color': 'green'}
            )

        try:
            subj_obj = Subject.objects.get(slug=subject_slug)
        except Subject.DoesNotExist:
            subj_obj = Subject.objects.get(slug='general-knowledge')

        past_paper_obj = None
        if paper_url:
            slug = _unique_slug(paper_title)
            past_paper_obj, _ = PastPaper.objects.update_or_create(
                source_url=paper_url,
                defaults={
                    'title':   paper_title or 'Untitled',
                    'slug':    slug,
                    'exam':    exam_obj,
                    'subject': subj_obj,
                    'year':    paper_year,
                    'status':  PastPaper.Status.PUBLISHED,
                },
            )

        question = item.get('question', '').strip()
        if not question:
            return item

        try:
            _, created = MCQ.objects.update_or_create(
                question_text=question,
                defaults={
                    'option_a':       item.get('option_a', ''),
                    'option_b':       item.get('option_b', ''),
                    'option_c':       item.get('option_c', ''),
                    'option_d':       '',
                    'correct_option': item.get('correct', 'A'),
                    'explanation':    item.get('explanation', ''),
                    'exam':           exam_obj,
                    'subject':        subj_obj,
                    'past_paper':     past_paper_obj,
                    'source_url':     item.get('source_url', ''),
                    'status':         MCQ.Status.PUBLISHED,
                },
            )
            if created:
                self.created += 1
            else:
                self.updated += 1
        except Exception as exc:
            spider.logger.error(f'Pipeline save error: {exc}')

        return item

    def close_spider(self, spider):
        spider.logger.warning(
            f'[DjangoPipeline] Done — Created: {self.created}  Updated: {self.updated}'
        )
        if self.created > 0:
            try:
                ActivityLog.objects.create(
                    activity_type='mcq_added',
                    message=f'Scrapy spider "{spider.name}" imported {self.created} new MCQs',
                    color='#1D4E9E',
                )
            except Exception:
                pass
