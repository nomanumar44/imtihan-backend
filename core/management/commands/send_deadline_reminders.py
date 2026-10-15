"""Management command to send deadline reminder notifications to users
with pending service requests whose job last date is within 24 hours.

Usage:
    python manage.py send_deadline_reminders

Schedule via cron (e.g., twice daily at 9am and 6pm):
    0 9,18 * * * cd /path/to/project && python manage.py send_deadline_reminders
"""

from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ApplicationRequest, Notification
from core.signals import _create_notification, _send_email


class Command(BaseCommand):
    help = 'Send deadline reminders for pending service requests nearing last date.'

    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()
        # last_date is a date: applications close at the end of that day (local time),
        # so "within 24 hours" means a last date of today or tomorrow that hasn't passed.
        window_start = today
        window_end = today + timedelta(days=1)

        # Find requests that are NOT submitted/failed/refunded and whose job last_date
        # falls within the next 24 hours
        pending_statuses = [
            ApplicationRequest.RequestStatus.PAYMENT_PENDING,
            ApplicationRequest.RequestStatus.PAYMENT_VERIFICATION,
            ApplicationRequest.RequestStatus.QUEUED,
            ApplicationRequest.RequestStatus.IN_PROGRESS,
        ]

        reqs = ApplicationRequest.objects.filter(
            request_status__in=pending_statuses,
            job__last_date__gte=window_start,
            job__last_date__lte=window_end,
        ).select_related('user', 'job')

        sent = 0
        for req in reqs:
            user = req.user
            job = req.job
            req_id = f'#REQ-{req.id:04d}'
            closes_at = timezone.make_aware(datetime.combine(job.last_date, time.max))
            hours_left = int((closes_at - now).total_seconds() // 3600)
            if hours_left > 24:
                continue

            # Avoid duplicate reminders: check if a reminder was sent recently
            recent = Notification.objects.filter(
                user=user,
                notification_type=Notification.NotificationType.SERVICE_REQUEST,
                message__icontains=req_id,
                created_at__gte=now - timedelta(hours=20),
            ).exists()
            if recent:
                continue

            status_label = req.get_request_status_display()
            msg = (
                f"Your application for {job.title} has a deadline in {hours_left} hours. "
                f"Current status: {status_label}. Please ensure all documents are ready."
            )
            _create_notification(user, msg, link='/dashboard/my-requests')

            if user.email:
                body = (
                    f"Hi {user.username},\n\n"
                    f"This is a friendly reminder that your application for {job.title} "
                    f"has a deadline in {hours_left} hours (last date: {job.last_date.strftime('%d %b %Y')}).\n\n"
                    f"Current status: {status_label}\n"
                    f"Request ID: {req_id}\n\n"
                    f"Please ensure all required documents and information are ready.\n\n"
                    f"— ImtihanHub Team"
                )
                _send_email(f"Deadline Reminder — {req_id}", body, user.email)

            sent += 1
            self.stdout.write(self.style.SUCCESS(
                f'Reminder sent to {user.username} for {job.title} ({hours_left}h left)'
            ))

        self.stdout.write(self.style.SUCCESS(f'\nTotal reminders sent: {sent}'))
