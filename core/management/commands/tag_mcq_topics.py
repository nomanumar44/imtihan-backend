"""Suggest topics for MCQs that don't have one, using the AI provider chain.

Only empty topics are filled; staff can correct any tag in the dashboard
(each change is kept in the question's history).

    python manage.py tag_mcq_topics --subject english [--limit 200]
"""
from django.core.management.base import BaseCommand, CommandError

from core.ai_tools import AIToolError, suggest_topics
from core.models import MCQ, Subject


class Command(BaseCommand):
    help = 'Fill empty MCQ topics with AI suggestions, one subject at a time.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Subject slug')
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        subject = Subject.objects.filter(slug=options['subject']).first()
        if not subject:
            raise CommandError(f"Unknown subject '{options['subject']}'.")
        pending = list(MCQ.objects.filter(subject=subject, topic='').exclude(status=MCQ.Status.RETIRED)
                       .select_related('subject')[:options['limit']])
        tagged = 0
        for start in range(0, len(pending), 40):
            try:
                tagged += suggest_topics(pending[start:start + 40])
            except AIToolError as e:
                self.stdout.write(self.style.WARNING(f'Stopped: {e}'))
                break
            self.stdout.write(f'  {tagged} tagged so far')
        self.stdout.write(self.style.SUCCESS(f'Tagged {tagged} of {len(pending)} MCQ(s) in {subject.name}.'))
