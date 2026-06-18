from django.core.management.base import BaseCommand
from core.models import Achievement

ACHIEVEMENTS = [
    {'slug':'first-test','name':'First Test','description':'Complete your first test','icon':'target','xp_reward':50,'condition_type':'tests_completed','condition_value':1},
    {'slug':'5-tests','name':'5 Tests','description':'Complete 5 tests','icon':'book','xp_reward':100,'condition_type':'tests_completed','condition_value':5},
    {'slug':'10-tests','name':'10 Tests','description':'Complete 10 tests','icon':'book','xp_reward':200,'condition_type':'tests_completed','condition_value':10},
    {'slug':'50-tests','name':'50 Tests','description':'Complete 50 tests','icon':'trophy','xp_reward':500,'condition_type':'tests_completed','condition_value':50},
    {'slug':'7-day-streak','name':'7 Day Streak','description':'Practice 7 days in a row','icon':'flame','xp_reward':100,'condition_type':'streak_days','condition_value':7},
    {'slug':'30-day-streak','name':'30 Day Streak','description':'Practice 30 days in a row','icon':'flame','xp_reward':500,'condition_type':'streak_days','condition_value':30},
    {'slug':'100-mcqs','name':'Century','description':'Answer 100 MCQs','icon':'book','xp_reward':75,'condition_type':'mcqs_answered','condition_value':100},
    {'slug':'500-mcqs','name':'Half Millennium','description':'Answer 500 MCQs','icon':'book','xp_reward':200,'condition_type':'mcqs_answered','condition_value':500},
    {'slug':'1000-mcqs','name':'Millennium','description':'Answer 1000 MCQs','icon':'book','xp_reward':500,'condition_type':'mcqs_answered','condition_value':1000},
    {'slug':'perfect-score','name':'Perfect Score','description':'Score 100% on a test','icon':'star','xp_reward':200,'condition_type':'perfect_score','condition_value':1},
    {'slug':'5-perfect','name':'Perfectionist','description':'Score 100% on 5 tests','icon':'star','xp_reward':500,'condition_type':'perfect_score','condition_value':5},
    {'slug':'ppsc-master','name':'PPSC Master','description':'Complete 5 PPSC tests','icon':'crown','xp_reward':300,'condition_type':'ppsc_tests','condition_value':5},
    {'slug':'night-owl','name':'Night Owl','description':'Practice after 11 PM','icon':'zap','xp_reward':30,'condition_type':'night_owl','condition_value':1},
    {'slug':'early-bird','name':'Early Bird','description':'Practice before 7 AM','icon':'rocket','xp_reward':30,'condition_type':'night_owl','condition_value':1},
    {'slug':'login-7','name':'Week Warrior','description':'Login on 7 different days','icon':'award','xp_reward':50,'condition_type':'login_days','condition_value':7},
    {'slug':'login-30','name':'Monthly Master','description':'Login on 30 different days','icon':'award','xp_reward':200,'condition_type':'login_days','condition_value':30},
]

class Command(BaseCommand):
    help = 'Seed default achievements'
    def handle(self, *args, **options):
        for a in ACHIEVEMENTS:
            obj, created = Achievement.objects.get_or_create(slug=a['slug'], defaults=a)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created: {obj.name}"))
            else:
                self.stdout.write(f"Exists: {obj.name}")
        self.stdout.write(self.style.SUCCESS('Done.'))
