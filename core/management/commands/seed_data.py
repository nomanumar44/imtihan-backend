"""
Management command to seed sample data for the Imtihan dashboard.
Run: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Exam, Subject, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog
)


class Command(BaseCommand):
    help = 'Seed the database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@imtihan.pk', 'admin123')
            self.stdout.write(self.style.SUCCESS('Superuser created: admin / admin123'))

        # Exams
        exams_data = [
            ('PPSC', 'ppsc', 'green'),
            ('FPSC', 'fpsc', 'blue'),
            ('NTS', 'nts', 'amber'),
            ('SPSC', 'spsc', 'purple'),
            ('KPPSC', 'kppsc', 'red'),
            ('BPSC', 'bpsc', 'green'),
        ]
        exams = {}
        for name, slug, color in exams_data:
            e, _ = Exam.objects.get_or_create(name=name, defaults={'slug': slug, 'badge_color': color})
            exams[slug] = e

        # Subjects
        subjects_data = [
            'Pakistan Studies', 'English', 'General Knowledge',
            'Mathematics', 'Islamiat', 'Computer Science',
            'Current Affairs', 'Urdu',
        ]
        subjects = {}
        for name in subjects_data:
            slug = name.lower().replace(' ', '-')
            s, _ = Subject.objects.get_or_create(name=name, defaults={'slug': slug})
            subjects[slug] = s

        # MCQs
        mcqs_data = [
            ('Who was the first Governor General of Pakistan?', 'Quaid-e-Azam', 'Lord Mountbatten', 'Liaquat Ali Khan', 'Iskander Mirza', 'A', 'ppsc', 'pakistan-studies', 'published'),
            ('The synonym of "Benevolent" is:', 'Kind', 'Cruel', 'Selfish', 'Greedy', 'A', 'fpsc', 'english', 'published'),
            ('Islamabad became capital in which year?', '1959', '1960', '1961', '1967', 'C', 'nts', 'pakistan-studies', 'draft'),
            ('Which planet is closest to the Sun?', 'Venus', 'Mercury', 'Mars', 'Earth', 'B', 'ppsc', 'general-knowledge', 'published'),
            ('The antonym of "Ephemeral" is:', 'Permanent', 'Brief', 'Short', 'Quick', 'A', 'fpsc', 'english', 'published'),
            ('Who wrote the national anthem of Pakistan?', 'Allama Iqbal', 'Hafeez Jalandhari', 'Faiz Ahmed Faiz', 'Ahmed Faraz', 'B', 'nts', 'pakistan-studies', 'published'),
            ('What is 15% of 200?', '20', '25', '30', '35', 'C', 'ppsc', 'mathematics', 'published'),
            ('The largest desert in Pakistan is:', 'Thar', 'Cholistan', 'Thal', 'Kharan', 'A', 'spsc', 'pakistan-studies', 'draft'),
            ('TCP/IP stands for:', 'Transmission Control Protocol/Internet Protocol', 'Transfer Control Protocol/Internet Protocol', 'Transmission Computer Protocol/Internet Protocol', 'None of the above', 'A', 'fpsc', 'computer-science', 'published'),
            ('The Quaid-e-Azam was born in:', '1876', '1877', '1875', '1878', 'A', 'kppsc', 'pakistan-studies', 'flagged'),
        ]
        for q, a, b, c, d, correct, exam_slug, subj_slug, status in mcqs_data:
            MCQ.objects.get_or_create(
                question_text=q,
                defaults={
                    'option_a': a, 'option_b': b, 'option_c': c, 'option_d': d,
                    'correct_option': correct, 'exam': exams[exam_slug],
                    'subject': subjects[subj_slug], 'status': status,
                }
            )

        # Past Papers
        papers = [
            ('PPSC Patwari 2024', 'ppsc', 2024, 'published'),
            ('FPSC CSS 2023 English Essay', 'fpsc', 2023, 'published'),
            ('NTS Educator Test 2024', 'nts', 2024, 'draft'),
            ('SPSC Assistant 2023', 'spsc', 2023, 'published'),
        ]
        for title, exam_slug, year, status in papers:
            PastPaper.objects.get_or_create(
                title=title,
                defaults={
                    'exam': exams[exam_slug], 'year': year,
                    'subject': subjects['pakistan-studies'],
                    'status': status, 'pdf_file': 'past_papers/sample.pdf',
                }
            )

        # Syllabus
        syllabi = [
            ('PPSC Lecturer Syllabus', 'ppsc', 'Lecturer'),
            ('FPSC CSS Syllabus 2025', 'fpsc', 'CSS Officer'),
            ('SPSC Assistant Syllabus', 'spsc', 'Assistant'),
        ]
        for title, exam_slug, post in syllabi:
            Syllabus.objects.get_or_create(
                title=title,
                defaults={
                    'exam': exams[exam_slug], 'post_name': post,
                    'content': f'Detailed syllabus for {post}...',
                }
            )

        # Jobs
        jobs_data = [
            ('Inspector Customs', 'fpsc', 'Customs Department', 'active'),
            ('Assistant Director', 'ppsc', 'Punjab Revenue', 'active'),
            ('Junior Clerk', 'nts', 'Education Department', 'active'),
            ('Stenographer', 'spsc', 'Sindh Secretariat', 'closed'),
        ]
        for title, exam_slug, dept, status in jobs_data:
            JobListing.objects.get_or_create(
                title=title,
                defaults={
                    'exam': exams[exam_slug], 'department': dept,
                    'description': f'{title} position in {dept}.',
                    'status': status,
                }
            )

        # Activity Log
        activities = [
            ('mcq_added', 'Admin uploaded PPSC Patwari 2024 paper', '#1D9E75'),
            ('job_posted', 'New job: Inspector Customs posted (FPSC)', '#185FA5'),
            ('mcq_added', '42 MCQs added to English subject bank', '#854F0B'),
            ('syllabus_updated', 'SPSC Assistant syllabus updated', '#534AB7'),
            ('flagged', '3 flagged MCQs need review', '#A32D2D'),
        ]
        for atype, msg, color in activities:
            ActivityLog.objects.get_or_create(
                message=msg,
                defaults={'activity_type': atype, 'color': color}
            )

        self.stdout.write(self.style.SUCCESS('Sample data seeded successfully!'))
