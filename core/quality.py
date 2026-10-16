"""Question quality: change history, student reports and duplicate detection.

Views that edit an MCQ set ``mcq._changed_by = request.user`` before saving so
the revision records who made the change.
"""
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import MCQ, MCQRevision, QuestionReport

TRACKED_FIELDS = [
    'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option',
    'explanation', 'exam_id', 'subject_id', 'past_paper_id', 'current_affairs_category_id',
    'topic', 'difficulty', 'event_date', 'source_url', 'status',
]

# Distinct signed-in reporters needed before a published question is hidden for review.
AUTO_FLAG_REPORTS = 3


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


@receiver(pre_save, sender=MCQ)
def _remember_mcq_changes(sender, instance, raw=False, **kwargs):
    instance._pending_changes = {}
    if raw or not instance.pk:
        return
    old = MCQ.objects.filter(pk=instance.pk).values(*TRACKED_FIELDS).first()
    if not old:
        return
    for field in TRACKED_FIELDS:
        before, after = old[field], getattr(instance, field)
        if before != after:
            instance._pending_changes[field.removesuffix('_id')] = [_jsonable(before), _jsonable(after)]


@receiver(post_save, sender=MCQ)
def _record_mcq_revision(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    user = getattr(instance, '_changed_by', None) or (instance.created_by if created else None)
    if created:
        MCQRevision.objects.create(mcq=instance, changed_by=user, action='created')
        return
    changes = getattr(instance, '_pending_changes', None)
    if changes:
        action = getattr(instance, '_change_action', None) or 'updated'
        MCQRevision.objects.create(mcq=instance, changed_by=user, action=action, changes=changes)
    instance._pending_changes = {}
    instance._change_action = None


def set_status(mcq, status, user, action=None):
    """Change an MCQ's status with an attributed history entry."""
    if mcq.status == status:
        return False
    mcq.status = status
    mcq._changed_by = user
    mcq._change_action = action or status
    mcq.save(update_fields=['status', 'updated_at'])
    return True


def file_report(mcq, user, reason, message=''):
    """Record a report (one open report per signed-in user) and auto-flag on consensus."""
    if user is not None and user.is_authenticated:
        report, created = QuestionReport.objects.get_or_create(
            mcq=mcq, user=user, status=QuestionReport.Status.OPEN,
            defaults={'reason': reason, 'message': message},
        )
        if not created:
            report.reason, report.message = reason, message or report.message
            report.save(update_fields=['reason', 'message'])
    else:
        report = QuestionReport.objects.create(mcq=mcq, reason=reason, message=message)

    reporters = (
        QuestionReport.objects.filter(mcq=mcq, status=QuestionReport.Status.OPEN, user__isnull=False)
        .values('user').distinct().count()
    )
    if mcq.status == MCQ.Status.PUBLISHED and reporters >= AUTO_FLAG_REPORTS:
        set_status(mcq, MCQ.Status.FLAGGED, None, action='auto-flagged')
    return report


def close_reports(mcq, user, status=QuestionReport.Status.RESOLVED):
    return QuestionReport.objects.filter(mcq=mcq, status=QuestionReport.Status.OPEN).update(
        status=status, resolved_by=user, resolved_at=timezone.now(),
    )


def duplicate_groups(limit=50):
    """Groups of active MCQs whose normalised question text is identical."""
    hashes = (
        MCQ.objects.exclude(status=MCQ.Status.RETIRED).exclude(normalized_hash='')
        .values('normalized_hash').annotate(n=Count('id')).filter(n__gt=1)
        .order_by('-n').values_list('normalized_hash', flat=True)[:limit]
    )
    groups = []
    for h in hashes:
        groups.append(list(
            MCQ.objects.filter(normalized_hash=h).exclude(status=MCQ.Status.RETIRED)
            .select_related('exam', 'subject').order_by('id')
        ))
    return groups
