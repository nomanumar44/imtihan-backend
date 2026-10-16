from datetime import timedelta

from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .gamification import (
    REPEAT_WINDOW_DAYS, STREAK_BONUS_DAYS, XP_DAILY_FIRST_TEST, XP_PER_CORRECT, XP_PER_TEST,
    XP_PERFECT_SCORE, XP_STREAK_BONUS, level_for_xp, user_streak,
)
from .models import TestResult, Student, DailyPracticeLog, Achievement, UserAchievement


def _get_or_create_student(user):
    student, _ = Student.objects.get_or_create(user=user)
    return student


def _award_xp(user, xp_amount, reason=''):
    """Add XP to the user's cumulative total and derive their level from it."""
    student = _get_or_create_student(user)
    if xp_amount:
        Student.objects.filter(pk=student.pk).update(xp_points=F('xp_points') + xp_amount)
        student.refresh_from_db(fields=['xp_points'])
    level = level_for_xp(student.xp_points)
    if level != student.level:
        student.level = level
        student.save(update_fields=['level'])
    return student


def _check_achievements(user):
    """Check and award achievements based on user stats."""
    # Gather stats
    total_tests = TestResult.objects.filter(student=user).count()
    total_mcqs = TestResult.objects.filter(student=user).aggregate(
        total=models.Sum('total_questions')
    )['total'] or 0

    streak = user_streak(user)

    # Perfect score count
    perfect_tests = TestResult.objects.filter(student=user, score_percent=100).count()

    # PPSC tests count
    ppsc_tests = TestResult.objects.filter(
        student=user, exam__slug='ppsc'
    ).count()

    # Night owl: practice after 11pm
    night_owl = TestResult.objects.filter(
        student=user, created_at__hour__gte=23
    ).exists()

    # Login days (distinct dates from practice logs)
    login_days = DailyPracticeLog.objects.filter(user=user).count()

    stats = {
        'tests_completed': total_tests,
        'streak_days': streak,
        'mcqs_answered': total_mcqs,
        'perfect_score': perfect_tests,
        'ppsc_tests': ppsc_tests,
        'night_owl': 1 if night_owl else 0,
        'login_days': login_days,
    }

    unlocked = []
    for ach in Achievement.objects.filter(is_active=True):
        if UserAchievement.objects.filter(user=user, achievement=ach).exists():
            continue

        current = stats.get(ach.condition_type, 0)
        if current >= ach.condition_value:
            UserAchievement.objects.create(user=user, achievement=ach)
            _award_xp(user, ach.xp_reward, f'achievement: {ach.name}')
            DailyPracticeLog.objects.filter(user=user, date=timezone.localdate()).update(
                xp_earned=F('xp_earned') + ach.xp_reward
            )
            unlocked.append(ach.name)

    return unlocked


def xp_for_test(test_result, first_test_today, streak, repeat=False):
    """XP for one completed test: correct answers plus completion bonuses.

    A repeat of an identical question set earns half the correct-answer XP and
    no completion/perfect bonuses, so memorising one easy set can't farm XP.
    """
    if repeat:
        return test_result.correct_answers * XP_PER_CORRECT // 2 + (XP_DAILY_FIRST_TEST if first_test_today else 0)
    xp = test_result.correct_answers * XP_PER_CORRECT + XP_PER_TEST
    if test_result.total_questions and float(test_result.score_percent) >= 100:
        xp += XP_PERFECT_SCORE
    if first_test_today:
        xp += XP_DAILY_FIRST_TEST
        # The streak bonus is paid once per day while the streak is alive.
        if streak >= STREAK_BONUS_DAYS:
            xp += XP_STREAK_BONUS
    return xp


@receiver(post_save, sender=TestResult)
def on_test_completed(sender, instance, created, raw=False, **kwargs):
    """Single source of truth for XP, streaks, daily counters and achievements."""
    if not created or raw:
        return

    user = instance.student
    today = timezone.localdate()

    with transaction.atomic():
        log, first_test_today = DailyPracticeLog.objects.select_for_update().get_or_create(
            user=user, date=today,
            defaults={'mcqs_answered': 0, 'tests_completed': 0, 'xp_earned': 0}
        )
        streak = user_streak(user, today)
        repeat = bool(instance.question_set_hash) and TestResult.objects.filter(
            student=user, question_set_hash=instance.question_set_hash,
            created_at__gte=timezone.now() - timedelta(days=REPEAT_WINDOW_DAYS),
        ).exclude(pk=instance.pk).exists()
        total_xp = xp_for_test(instance, first_test_today, streak, repeat)

        log.mcqs_answered += instance.total_questions
        log.tests_completed += 1
        log.xp_earned += total_xp
        log.save(update_fields=['mcqs_answered', 'tests_completed', 'xp_earned'])

        _award_xp(user, total_xp, 'test_completed')

        student = _get_or_create_student(user)
        if student.last_practice_date != today:
            student.mcqs_today = 0
            student.tests_today = 0
        student.mcqs_today += instance.total_questions
        student.tests_today += 1
        student.last_practice_date = today
        student.streak_days = streak
        student.save(update_fields=['mcqs_today', 'tests_today', 'last_practice_date', 'streak_days'])

    _check_achievements(user)


# ─── Paid Application Service Notifications ───────────────────────────────────

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from .models import ApplicationRequest, Notification, JobListing

# Cache old status for change detection
_old_request_status = {}
_old_payment_status = {}


@receiver(pre_save, sender=ApplicationRequest)
def cache_request_status(sender, instance, **kwargs):
    """Capture previous status before save so post_save can detect changes."""
    if instance.pk:
        try:
            old = ApplicationRequest.objects.get(pk=instance.pk)
            _old_request_status[instance.pk] = old.request_status
            _old_payment_status[instance.pk] = old.payment_status
        except ApplicationRequest.DoesNotExist:
            pass


def _create_notification(user, message, link=''):
    """Create an in-app notification for a user."""
    Notification.objects.create(
        user=user,
        notification_type=Notification.NotificationType.SERVICE_REQUEST,
        message=message,
        link=link,
    )


def _send_email(subject, body, recipient_list, html_body=None):
    """Send email via Django SMTP backend."""
    if not recipient_list:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list if isinstance(recipient_list, list) else [recipient_list],
            html_message=html_body or None,
            fail_silently=True,
        )
    except Exception:
        pass


def _send_admin_email(subject, body):
    """Send email to all configured admin addresses."""
    if settings.ADMIN_EMAILS:
        _send_email(subject, body, settings.ADMIN_EMAILS)


@receiver(post_save, sender=ApplicationRequest)
def on_application_request_change(sender, instance, created, **kwargs):
    """Auto-notify users and admins on service request lifecycle events."""
    req = instance
    user = req.user
    job = req.job
    req_id = f'#REQ-{req.id:04d}'

    old_status = _old_request_status.pop(req.id, None) if not created else None
    old_payment = _old_payment_status.pop(req.id, None) if not created else None

    # ── 1. REQUEST CREATED ──
    if created:
        msg = f"Request {req_id} received. We will verify your payment within 2-4 hours."
        _create_notification(user, msg, link='/dashboard/my-requests')

        # Admin email
        pay_method = req.get_payment_method_display() if req.payment_method else 'N/A'
        admin_body = (
            f"New request from {user.username} ({user.email})\n"
            f"Job: {job.title}\n"
            f"Payment: Rs.{req.payment_amount or (req.plan.price if req.plan else 0)} via {pay_method}\n"
            f"Reference: {req.payment_reference or 'N/A'}\n"
            f"Request ID: {req_id}\n"
            f"Instructions: {req.special_instructions or 'None'}"
        )
        _send_admin_email(f"New Service Request {req_id}", admin_body)
        return

    # ── 2. PAYMENT VERIFIED ──
    if old_payment != 'paid' and req.payment_status == 'paid':
        msg = f"Payment verified! Your application for {job.title} is now in queue."
        _create_notification(user, msg, link='/dashboard/my-requests')
        _send_email(
            f"Payment Verified — {req_id}",
            f"Hi {user.username},\n\n{msg}\n\n— ImtihanHub Team",
            user.email,
        )
        return

    # ── 3. APPLICATION SUBMITTED ──
    if old_status != 'submitted' and req.request_status == 'submitted':
        ref = req.submission_reference or 'N/A'
        msg = f"Your application for {job.title} has been submitted successfully! Reference: {ref}."
        _create_notification(user, msg, link='/dashboard/my-requests')

        email_body = (
            f"Hi {user.username},\n\n"
            f"Great news! Your application for {job.title} has been successfully submitted.\n\n"
            f"Application Reference: {ref}\n"
            f"Submission Date: {req.submitted_at.strftime('%d %b %Y, %I:%M %p') if req.submitted_at else 'N/A'}\n\n"
            f"You can view the submission proof screenshot in your dashboard:\n"
            f"{settings.FRONTEND_URL}/dashboard/my-requests\n\n"
            f"— ImtihanHub Team"
        )
        _send_email(f"Application Submitted — {req_id}", email_body, user.email)
        return

    # ── 4. APPLICATION FAILED ──
    if old_status != 'failed' and req.request_status == 'failed':
        reason = req.failure_reason or 'Unknown'
        refund_msg = (
            f" A refund of Rs.{req.payment_amount or '0'} will be processed within 24 hours."
            if req.payment_status != 'refunded' else
            f" Refund of Rs.{req.payment_amount or '0'} has been processed."
        )
        msg = f"We were unable to submit your application for {job.title}. Reason: {reason}.{refund_msg}"
        _create_notification(user, msg, link='/dashboard/my-requests')

        email_body = (
            f"Hi {user.username},\n\n"
            f"We regret to inform you that we were unable to submit your application for {job.title}.\n\n"
            f"Reason: {reason}\n"
            f"{refund_msg}\n\n"
            f"You can submit a new request here:\n"
            f"{settings.FRONTEND_URL}/jobs\n\n"
            f"— ImtihanHub Team"
        )
        _send_email(f"Application Failed — {req_id}", email_body, user.email)
        return
