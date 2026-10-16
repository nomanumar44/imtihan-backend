"""Daily study reminder at each student's chosen time (Dashboard → Goals).

Sends one in-app notification (and email) per day, only to students who have
set a reminder time and haven't practised yet today. Run hourly:
    0 * * * * cd /path/to/imtihan-backend && python manage.py send_study_reminders
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.gamification import user_streak
from core.models import Notification, Student, StudyPlan
from core.signals import _send_email


class Command(BaseCommand):
    help = "Remind students who set a reminder time and haven't practised today."

    def handle(self, *args, **options):
        now = timezone.localtime()
        today = now.date()
        already = set(Notification.objects.filter(
            notification_type=Notification.NotificationType.STREAK_REMINDER,
            created_at__date=today,
        ).values_list('user_id', flat=True))
        due = (Student.objects.filter(reminder_time__isnull=False, reminder_time__lte=now.time())
               .exclude(last_practice_date=today).exclude(user_id__in=already).select_related('user'))

        plans = {p.user_id: p for p in StudyPlan.objects.filter(user_id__in=[s.user_id for s in due]).select_related('syllabus')}
        sent = 0
        for student in due:
            user = student.user
            streak = user_streak(user, today)
            plan = plans.get(user.id)
            parts = []
            if streak:
                parts.append(f'Keep your {streak}-day streak going.')
            if plan:
                days = (plan.exam_date - today).days
                if days > 0:
                    parts.append(f'{days} days to your {plan.syllabus.title} exam.')
            parts.append(f'Your goal today: {student.daily_goal} MCQs.')
            message = ' '.join(parts)
            link = '/dashboard/study-plan' if plan else '/dashboard'
            Notification.objects.create(
                user=user, notification_type=Notification.NotificationType.STREAK_REMINDER,
                message=message[:300], link=link,
            )
            if user.email:
                _send_email('Time to practise on ImtihanHub',
                            f"Hi {user.first_name or user.username},\n\n{message}\n\n{settings.FRONTEND_URL}{link}\n\n— ImtihanHub Team",
                            user.email)
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Study reminders sent: {sent}'))
