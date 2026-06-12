"""
Management command: send_news_digest

Usage:
    python manage.py send_news_digest [--since-hours 24]

Sends a digest email to active NewsSubscriber users containing
new posts published in their selected board categories.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from core.models import NewsSubscriber, Post


class Command(BaseCommand):
    help = 'Send news digest emails to active subscribers based on their board preferences.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--since-hours',
            type=int,
            default=24,
            help='Only include posts published within the last N hours (default: 24)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending emails.',
        )

    def handle(self, *args, **options):
        since_hours = options['since_hours']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(hours=since_hours)

        # Get new published posts since cutoff
        new_posts = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            post_type=Post.PostType.NEWS,
            published_at__gte=cutoff,
        ).select_related('category', 'author').order_by('-published_at')

        if not new_posts.exists():
            self.stdout.write(self.style.WARNING('No new posts to include in digest.'))
            return

        self.stdout.write(f'Found {new_posts.count()} new post(s) since {cutoff}')

        # Group subscribers by boards
        subscribers = NewsSubscriber.objects.filter(is_active=True).prefetch_related('boards')

        site_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        sent_count = 0

        for sub in subscribers:
            # Filter posts by subscriber's selected boards
            board_ids = list(sub.boards.values_list('id', flat=True))
            if board_ids:
                posts = new_posts.filter(category__id__in=board_ids)
            else:
                posts = new_posts  # No boards selected = all posts

            if not posts.exists():
                continue

            unsubscribe_url = f"{site_url}/api/unsubscribe/{sub.unsubscribe_token}/"

            context = {
                'posts': posts,
                'site_url': site_url,
                'unsubscribe_url': unsubscribe_url,
            }

            html_body = render_to_string('emails/news_digest.html', context)
            text_body = render_to_string('emails/news_digest.txt', context)

            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would send to {sub.email} — {posts.count()} post(s)'
                )
                continue

            try:
                send_mail(
                    subject='ImtihanHub: Latest Exam News & Updates',
                    message=text_body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@imtihanhub.com'),
                    recipient_list=[sub.email],
                    html_message=html_body,
                    fail_silently=False,
                )
                sent_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send to {sub.email}: {e}'))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'[DRY RUN] Would send to {subscribers.count()} subscriber(s)'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Sent digest to {sent_count} subscriber(s).'))
