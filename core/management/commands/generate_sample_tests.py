"""Generate sample test results for a user to populate dashboard charts."""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from core.models import TestResult, Exam, Subject


class Command(BaseCommand):
    help = 'Generate sample test results for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username or email')
        parser.add_argument('--count', type=int, default=10, help='Number of sample tests to create')
        parser.add_argument('--days', type=int, default=30, help='Spread tests over last N days')

    def handle(self, *args, **options):
        username = options['username']
        count = options['count']
        days = options['days']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User "{username}" not found.'))
                return

        exams = list(Exam.objects.all()[:5])
        subjects = list(Subject.objects.all()[:5])
        if not exams:
            exams = [None]
        if not subjects:
            subjects = [None]

        today = timezone.now()
        created = 0
        for i in range(count):
            total_q = random.choice([10, 15, 20, 25, 30])
            correct = random.randint(max(0, total_q - 8), total_q)
            wrong = total_q - correct
            score = round((correct / total_q) * 100, 2)
            time_taken = random.randint(300, 1800)
            offset = random.randint(0, days)
            created_at = today - timedelta(days=offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))

            tr = TestResult.objects.create(
                student=user,
                exam=random.choice(exams),
                subject=random.choice(subjects),
                total_questions=total_q,
                correct_answers=correct,
                wrong_answers=wrong,
                score_percent=score,
                time_taken_seconds=time_taken,
            )
            # Adjust created_at manually for spread over time
            TestResult.objects.filter(pk=tr.pk).update(created_at=created_at)
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created} sample test results for {user.username}.'))
        self.stdout.write('Refresh the dashboard to see updated stats and charts.')
