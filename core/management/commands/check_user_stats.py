"""Management command to inspect a user's dashboard data for diagnostics."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import TestResult, Student, DailyPracticeLog


class Command(BaseCommand):
    help = 'Inspect user stats and test results for debugging'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username or email to inspect')

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User "{username}" not found.'))
                return

        self.stdout.write(self.style.NOTICE(f'Inspecting user: {user.username} (id={user.id})'))

        test_results = TestResult.objects.filter(student=user).order_by('-created_at')
        self.stdout.write(f'TestResult count: {test_results.count()}')
        for tr in test_results[:5]:
            self.stdout.write(f'  - Test id={tr.id} score={tr.score_percent}% questions={tr.total_questions} date={tr.created_at}')

        student = getattr(user, 'student_profile', None)
        if student:
            self.stdout.write(f'Student profile: mcqs_today={student.mcqs_today}, tests_today={student.tests_today}, '
                             f'streak_days={student.streak_days}, last_practice_date={student.last_practice_date}, '
                             f'xp={student.xp_points}, level={student.level}')
        else:
            self.stdout.write(self.style.WARNING('No Student profile found.'))

        logs = DailyPracticeLog.objects.filter(user=user).order_by('-date')[:7]
        self.stdout.write(f'DailyPracticeLog entries (last 7): {logs.count()}')
        for log in logs:
            self.stdout.write(f'  - {log.date}: mcqs={log.mcqs_answered}, tests={log.tests_completed}, xp={log.xp_earned}')

        self.stdout.write(self.style.SUCCESS('Inspection complete.'))
