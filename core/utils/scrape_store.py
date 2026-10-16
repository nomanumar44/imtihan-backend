"""Save rules shared by the scrapers.

- An MCQ that already exists (same question text) is never overwritten, so staff
  edits and other sources keep their answer, exam, subject and status. A scrape
  may only attach it to a past paper it isn't linked to yet.
- Questions that look like placeholders or have no usable answer are saved as
  drafts for staff review instead of being published.
- A past paper's slug and status are set once, on creation, so its public URL
  stays stable and staff can unpublish it without a re-scrape undoing that.
"""
from django.utils.text import slugify

from core.models import MCQ, PastPaper

PLACEHOLDER_OPTIONS = {'option a', 'option b', 'option c', 'option d', 'a', 'b', 'c', 'd'}


def needs_review(fields):
    """True for scraped MCQs that must not go live without a human check."""
    options = [str(fields.get(f'option_{k}') or '').strip() for k in 'abcd']
    filled = [o for o in options if o]
    if len(filled) < 3 or sum(o.lower() in PLACEHOLDER_OPTIONS for o in filled) >= 2:
        return True
    correct = str(fields.get('correct_option') or '').upper()
    if correct not in ('A', 'B', 'C', 'D'):
        return True
    return not options['ABCD'.index(correct)]


def save_scraped_mcq(question_text, fields, past_paper=None):
    """Create the MCQ if it's new; return (mcq, created)."""
    defaults = dict(fields)
    defaults['past_paper'] = past_paper
    defaults.setdefault('origin', MCQ.Origin.SCRAPED)
    if needs_review(defaults):
        defaults['status'] = MCQ.Status.DRAFT
    mcq, created = MCQ.objects.get_or_create(question_text=question_text.strip(), defaults=defaults)
    if not created and past_paper is not None and mcq.past_paper_id is None:
        MCQ.objects.filter(pk=mcq.pk).update(past_paper=past_paper)
    return mcq, created


def unique_paper_slug(title):
    base = slugify(title)[:300] or 'paper'
    slug, i = base, 1
    while PastPaper.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def save_scraped_paper(source_url, title, exam, subject, year):
    """Create or refresh the paper scraped from `source_url`; return (paper, created)."""
    title = title or 'Untitled'
    paper = PastPaper.objects.filter(source_url=source_url).first()
    if paper is None:
        paper = PastPaper.objects.create(
            source_url=source_url, title=title, slug=unique_paper_slug(title),
            exam=exam, subject=subject, year=year, status=PastPaper.Status.PUBLISHED,
        )
        return paper, True
    paper.title, paper.exam, paper.subject, paper.year = title, exam, subject, year
    paper.save()
    return paper, False
