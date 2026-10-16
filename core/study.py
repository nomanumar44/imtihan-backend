"""Study planner and spaced-repetition rules."""
import math
import re
from datetime import date, timedelta
from html import unescape

from django.utils import timezone

from .models import Flashcard, SyllabusTopic, TopicProgress

WEIGHT_RE = re.compile(r'^(?P<name>.*?)[\s:\-–(]*(?P<weight>\d{1,3})\s*%?\s*\)?\s*$')


# ── Syllabus topics ──────────────────────────────────────────────────────────

def _content_lines(content):
    """Plain-text lines from syllabus content that may be HTML from the editor."""
    text = re.sub(r'(?i)<\s*(br|/p|/li|/h\d|/div|/tr)\s*/?>', '\n', content or '')
    text = unescape(re.sub(r'<[^>]+>', ' ', text))
    for line in text.splitlines():
        line = re.sub(r'^[\s\-\*\u2022\d\.\)]+', '', line).strip()
        if 2 < len(line) <= 200:
            yield line


def parse_topics(content):
    """[(name, weight or None)] from syllabus text; "English (20%)" gives weight 20."""
    topics = []
    for line in _content_lines(content):
        match = WEIGHT_RE.match(line)
        weight = None
        if match and match.group('name').strip() and 0 < int(match.group('weight')) <= 100 and '%' in line:
            line, weight = match.group('name').strip(), int(match.group('weight'))
        if line and all(line.lower() != t[0].lower() for t in topics):
            topics.append((line[:200], weight))
    return topics[:80]


def ensure_topics(syllabus):
    """Create topics from the syllabus text the first time a plan needs them."""
    if not syllabus.topics.exists():
        SyllabusTopic.objects.bulk_create([
            SyllabusTopic(syllabus=syllabus, name=name, weight=weight, order=i)
            for i, (name, weight) in enumerate(parse_topics(syllabus.content))
        ])
    return list(syllabus.topics.select_related('subject'))


# ── Schedule ─────────────────────────────────────────────────────────────────

def build_schedule(plan, topics, statuses, today=None):
    """Weekly plan from today to the exam: unfinished topics first (heaviest first),
    then revision weeks. Returns a list of weeks and today's focus topics."""
    today = today or timezone.localdate()
    days_left = (plan.exam_date - today).days
    if days_left <= 0:
        return [], []
    weeks_total = max(1, math.ceil(days_left / 7))
    revision_weeks = 0 if weeks_total < 2 else max(1, round(weeks_total * 0.15))
    study_weeks = weeks_total - revision_weeks

    remaining = [t for t in topics if statuses.get(t.id) != TopicProgress.Status.DONE]
    remaining.sort(key=lambda t: (-(t.weight or 0), t.order, t.id))
    per_week = math.ceil(len(remaining) / study_weeks) if remaining else 0

    weeks = []
    for i in range(weeks_total):
        start = today + timedelta(days=7 * i)
        end = min(start + timedelta(days=6), plan.exam_date - timedelta(days=1))
        chunk = remaining[i * per_week:(i + 1) * per_week] if i < study_weeks else []
        weeks.append({
            'week': i + 1,
            'start': start.isoformat(),
            'end': max(end, start).isoformat(),
            'revision': i >= study_weeks,
            'topic_ids': [t.id for t in chunk],
            'hours_per_topic': round(plan.hours_per_week / len(chunk), 1) if chunk else None,
        })
    return weeks, weeks[0]['topic_ids'] if weeks else []


# ── Spaced repetition (SM-2) ─────────────────────────────────────────────────

GRADES = {'again': 1, 'hard': 3, 'good': 4, 'easy': 5}
MASTERED_INTERVAL = 21


def review(card: Flashcard, grade: str, today: date | None = None):
    """Apply one SM-2 review step to `card` and save it."""
    today = today or timezone.localdate()
    q = GRADES[grade]
    if q < 3:
        card.repetitions = 0
        card.interval_days = 0          # back in today's session
        card.lapses += 1
    else:
        card.repetitions += 1
        if card.repetitions == 1:
            card.interval_days = 1
        elif card.repetitions == 2:
            card.interval_days = 6 if q >= 4 else 3
        else:
            factor = card.ease if q >= 4 else 1.2
            card.interval_days = max(card.interval_days + 1, round(card.interval_days * factor))
        if q == 5:
            card.interval_days = round(card.interval_days * 1.3) or 1
    card.ease = max(1.3, card.ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    card.due_date = today + timedelta(days=card.interval_days)
    card.last_reviewed_at = timezone.now()
    card.save()
    return card


def card_from_mcq(mcq):
    """Front/back text for a flashcard made from an MCQ."""
    letters = ['A', 'B', 'C', 'D']
    options = [o for o in (mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d) if o]
    front = mcq.question_text + '\n\n' + '\n'.join(f'{letters[i]}. {o}' for i, o in enumerate(options))
    answer = {'A': mcq.option_a, 'B': mcq.option_b, 'C': mcq.option_c, 'D': mcq.option_d}.get(mcq.correct_option, '')
    back = f'{mcq.correct_option}. {answer}'
    if mcq.explanation:
        back += f'\n\n{mcq.explanation}'
    return front, back
