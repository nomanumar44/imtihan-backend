"""Mark active/upcoming jobs whose last date has passed as closed.

The API already reports such jobs as closed; this keeps the stored status (and
the staff dashboard) in step. Schedule daily, e.g.:
    5 0 * * * cd /path/to/imtihan-backend && python manage.py close_expired_jobs
"""
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import JobListing


class Command(BaseCommand):
    help = 'Close job listings whose last date has passed.'

    def handle(self, *args, **options):
        closed = JobListing.objects.filter(
            status__in=[JobListing.Status.ACTIVE, JobListing.Status.UPCOMING],
            last_date__lt=timezone.localdate(),
        ).update(status=JobListing.Status.CLOSED, updated_at=timezone.now())
        if closed:
            cache.delete('frontend_home')
        self.stdout.write(self.style.SUCCESS(f'Closed {closed} expired job listing(s).'))
