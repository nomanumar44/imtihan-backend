"""Staff AI tools: draft MCQs for review and topic suggestions.

Everything here goes through the same provider chain as the tutor. Output is
treated as untrusted: AI questions are saved only as drafts (origin "ai") for a
human to check in the review queue, and topic tags only fill empty topics.
"""
import json
import re

from .ai_service import get_ai_response, is_failure_response
from .models import MCQ

DRAFT_SYSTEM_PROMPT = (
    "You write multiple-choice questions for Pakistani public service commission exams "
    "(PPSC, FPSC, NTS, CSS screening). Write factual, unambiguous questions with exactly one "
    "correct option. Avoid facts that change often unless the question states the date. "
    "Reply with JSON only: a list of objects with keys \"question\", \"options\" (4 strings), "
    "\"answer\" (A, B, C or D) and \"explanation\" (one or two sentences). No other text."
)

TOPIC_SYSTEM_PROMPT = (
    "You tag exam MCQs with a short topic name (1 to 4 words, Title Case) within their subject, "
    "reusing the same name for questions on the same topic. Reply with JSON only: an object "
    "mapping each question id (as a string) to its topic. No other text."
)


class AIToolError(Exception):
    pass


def _json_from(text, opener):
    """First JSON list/object in the reply (models sometimes wrap it in prose or fences)."""
    if is_failure_response(text):
        raise AIToolError('The AI service is busy or not configured. Try again later.')
    closer = ']' if opener == '[' else '}'
    match = re.search(re.escape(opener) + r'.*' + re.escape(closer), text, re.S)
    if not match:
        raise AIToolError('The AI reply could not be read. Try again.')
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AIToolError('The AI reply was not valid JSON. Try again.') from e


def generate_draft_mcqs(exam, subject, topic, count, user):
    """Ask the AI for `count` MCQs and save the valid ones as drafts; return the new MCQs."""
    count = max(1, min(int(count), 10))
    focus = f'the topic "{topic}" in {subject.name}' if topic else subject.name
    prompt = f"Write {count} MCQs on {focus} for {exam.name} candidates."
    reply = get_ai_response([{'role': 'user', 'content': prompt}], system_instruction=DRAFT_SYSTEM_PROMPT)
    items = _json_from(reply, '[')
    if not isinstance(items, list):
        raise AIToolError('The AI reply was not a list of questions.')

    created = []
    for item in items[:count]:
        if not isinstance(item, dict):
            continue
        question = str(item.get('question') or '').strip()
        options = [str(o).strip() for o in (item.get('options') or [])][:4]
        answer = str(item.get('answer') or '').strip().upper()[:1]
        if not question or len(options) < 3 or not all(options) or answer not in tuple('ABCD'[:len(options)]):
            continue
        options += [''] * (4 - len(options))
        mcq = MCQ(
            question_text=question,
            option_a=options[0], option_b=options[1], option_c=options[2], option_d=options[3],
            correct_option=answer,
            explanation=str(item.get('explanation') or '').strip(),
            exam=exam, subject=subject, topic=(topic or '')[:120],
            status=MCQ.Status.DRAFT, origin=MCQ.Origin.AI, created_by=user,
        )
        mcq._changed_by = user
        mcq.save()
        created.append(mcq)
    if not created:
        raise AIToolError('The AI reply had no usable questions. Try again.')
    return created


def suggest_topics(mcqs):
    """Fill empty topics for a batch of MCQs from one subject; return how many were tagged."""
    batch = [m for m in mcqs if not m.topic][:40]
    if not batch:
        return 0
    lines = '\n'.join(f'{m.id}: {m.question_text[:300]}' for m in batch)
    existing = sorted(set(MCQ.objects.filter(subject=batch[0].subject).exclude(topic='')
                          .values_list('topic', flat=True)))[:60]
    prompt = (
        f"Subject: {batch[0].subject.name}\n"
        + (f"Topics already in use (reuse when they fit): {', '.join(existing)}\n" if existing else '')
        + f"Questions:\n{lines}"
    )
    tags = _json_from(get_ai_response([{'role': 'user', 'content': prompt}], system_instruction=TOPIC_SYSTEM_PROMPT), '{')
    tagged = 0
    for mcq in batch:
        topic = str(tags.get(str(mcq.id)) or '').strip()[:120] if isinstance(tags, dict) else ''
        if topic:
            mcq.topic = topic
            mcq._change_action = 'ai-topic'
            mcq.save(update_fields=['topic', 'updated_at'])
            tagged += 1
    return tagged
