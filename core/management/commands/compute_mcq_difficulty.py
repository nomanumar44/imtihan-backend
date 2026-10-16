"""Set MCQ difficulty from how students actually answered it.

Only questions with enough attempts and no difficulty set by staff are changed:
easy ≥ 75% correct, hard ≤ 40% correct, medium in between.

    python manage.py compute_mcq_difficulty [--min-attempts 20] [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from core.models import MCQ, TestAnswer


class Command(BaseCommand):
    help = 'Derive difficulty for untagged MCQs from student answer accuracy.'

    def add_arguments(self, parser):
        parser.add_argument('--min-attempts', type=int, default=20)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        stats = (
            TestAnswer.objects.exclude(selected_option='')
            .values('question_id')
            .annotate(n=Count('id'), right=Count('id', filter=Q(is_correct=True)))
            .filter(n__gte=options['min_attempts'])
        )
        by_id = {row['question_id']: row for row in stats}
        updated = 0
        for mcq in MCQ.objects.filter(id__in=list(by_id), difficulty=''):
            row = by_id[mcq.id]
            accuracy = row['right'] / row['n']
            level = MCQ.Difficulty.EASY if accuracy >= 0.75 else MCQ.Difficulty.HARD if accuracy <= 0.40 else MCQ.Difficulty.MEDIUM
            if not options['dry_run']:
                mcq.difficulty = level
                mcq._change_action = 'auto-difficulty'
                mcq.save(update_fields=['difficulty', 'updated_at'])
            updated += 1
        prefix = '[dry run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(f'{prefix}Set difficulty on {updated} MCQ(s).'))
