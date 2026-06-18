"""
Management command to seed sample data for the ImtihanHub dashboard.
Run: python manage.py seed_data
"""
import random

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Exam, Subject, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog,
    CurrentAffairsCategory, SectionContent,
    Category, Tag, Post, Announcement
)


class Command(BaseCommand):
    help = 'Seed the database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@imtihanhub.com.pk', 'admin123')
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

        # MCQs (50+ published so homepage stats look real)
        mcqs_data = [
            ('Who was the first Governor General of Pakistan?', 'Quaid-e-Azam', 'Lord Mountbatten', 'Liaquat Ali Khan', 'Iskander Mirza', 'A', 'ppsc', 'pakistan-studies', 'published'),
            ('The synonym of "Benevolent" is:', 'Kind', 'Cruel', 'Selfish', 'Greedy', 'A', 'fpsc', 'english', 'published'),
            ('Islamabad became capital in which year?', '1959', '1960', '1961', '1967', 'C', 'nts', 'pakistan-studies', 'published'),
            ('Which planet is closest to the Sun?', 'Venus', 'Mercury', 'Mars', 'Earth', 'B', 'ppsc', 'general-knowledge', 'published'),
            ('The antonym of "Ephemeral" is:', 'Permanent', 'Brief', 'Short', 'Quick', 'A', 'fpsc', 'english', 'published'),
            ('Who wrote the national anthem of Pakistan?', 'Allama Iqbal', 'Hafeez Jalandhari', 'Faiz Ahmed Faiz', 'Ahmed Faraz', 'B', 'nts', 'pakistan-studies', 'published'),
            ('What is 15% of 200?', '20', '25', '30', '35', 'C', 'ppsc', 'mathematics', 'published'),
            ('The largest desert in Pakistan is:', 'Thar', 'Cholistan', 'Thal', 'Kharan', 'A', 'spsc', 'pakistan-studies', 'published'),
            ('TCP/IP stands for:', 'Transmission Control Protocol/Internet Protocol', 'Transfer Control Protocol/Internet Protocol', 'Transmission Computer Protocol/Internet Protocol', 'None of the above', 'A', 'fpsc', 'computer-science', 'published'),
            ('The Quaid-e-Azam was born in:', '1876', '1877', '1875', '1878', 'A', 'kppsc', 'pakistan-studies', 'published'),
            ('Pakistan joined UN in:', '1947', '1948', '1950', '1951', 'A', 'ppsc', 'pakistan-studies', 'published'),
            ('Synonym of "Ample" is:', 'Enough', 'Scarce', 'Less', 'Tiny', 'A', 'fpsc', 'english', 'published'),
            ('Light year is a unit of:', 'Time', 'Distance', 'Speed', 'Intensity', 'B', 'ppsc', 'general-knowledge', 'published'),
            ('Antonym of "Fragile" is:', 'Strong', 'Weak', 'Brittle', 'Delicate', 'A', 'fpsc', 'english', 'published'),
            ('Who was the first Prime Minister of Pakistan?', 'Liaquat Ali Khan', 'Khawaja Nazimuddin', 'Mohammad Ali Bogra', 'Chaudhry Muhammad Ali', 'A', 'nts', 'pakistan-studies', 'published'),
            ('25% of 400 is:', '50', '75', '100', '125', 'C', 'ppsc', 'mathematics', 'published'),
            ('Smallest province of Pakistan by area is:', 'Punjab', 'Sindh', 'KPK', 'Balochistan', 'C', 'spsc', 'pakistan-studies', 'published'),
            ('RAM stands for:', 'Random Access Memory', 'Read Access Memory', 'Run Access Memory', 'Real Access Memory', 'A', 'fpsc', 'computer-science', 'published'),
            ('The Objectives Resolution was passed in:', '1940', '1946', '1949', '1956', 'C', 'kppsc', 'pakistan-studies', 'published'),
            ('What is 3/4 of 80?', '50', '60', '70', '55', 'B', 'ppsc', 'mathematics', 'published'),
            ('HTML stands for:', 'Hyper Text Markup Language', 'High Text Markup Language', 'Hyper Tabular Markup Language', 'None of these', 'A', 'nts', 'computer-science', 'published'),
            ('Largest dam in Pakistan is:', 'Tarbela', 'Mangla', 'Warsak', 'Rawal', 'A', 'ppsc', 'pakistan-studies', 'published'),
            ('Synonym of "Astonish" is:', 'Surprise', 'Bore', 'Tire', 'Weary', 'A', 'fpsc', 'english', 'published'),
            ('Which gas is most abundant in atmosphere?', 'Oxygen', 'Carbon Dioxide', 'Nitrogen', 'Hydrogen', 'C', 'ppsc', 'general-knowledge', 'published'),
            ('CPU stands for:', 'Central Processing Unit', 'Central Process Unit', 'Computer Personal Unit', 'Central Processor Unit', 'A', 'fpsc', 'computer-science', 'published'),
            ('Pakistan became an Islamic Republic in:', '1947', '1956', '1962', '1973', 'B', 'nts', 'pakistan-studies', 'published'),
            ('What is the square root of 144?', '10', '11', '12', '13', 'C', 'ppsc', 'mathematics', 'published'),
            ('Antonym of "Generous" is:', 'Stingy', 'Kind', 'Liberal', 'Noble', 'A', 'fpsc', 'english', 'published'),
            ('Karakoram Highway connects Pakistan with:', 'India', 'Iran', 'China', 'Afghanistan', 'C', 'spsc', 'pakistan-studies', 'published'),
            ('HTTP stands for:', 'Hyper Text Transfer Protocol', 'Hyper Text Transmission Protocol', 'High Text Transfer Protocol', 'Hyperlink Text Transfer Protocol', 'A', 'nts', 'computer-science', 'published'),
            ('What is 7 x 8?', '54', '56', '58', '52', 'B', 'ppsc', 'mathematics', 'published'),
            ('Who invented the telephone?', 'Alexander Graham Bell', 'Thomas Edison', 'Nikola Tesla', 'Guglielmo Marconi', 'A', 'fpsc', 'general-knowledge', 'published'),
            ('Synonym of "Diligent" is:', 'Hardworking', 'Lazy', 'Careless', 'Idle', 'A', 'fpsc', 'english', 'published'),
            ('Which is the longest river in Pakistan?', 'Indus', 'Jhelum', 'Chenab', 'Ravi', 'A', 'ppsc', 'pakistan-studies', 'published'),
            ('What is 20% of 500?', '50', '100', '150', '200', 'B', 'ppsc', 'mathematics', 'published'),
            ('DNS stands for:', 'Domain Name System', 'Domain Network System', 'Digital Name System', 'Data Name System', 'A', 'nts', 'computer-science', 'published'),
            ('Antonym of "Humble" is:', 'Proud', 'Modest', 'Polite', 'Meek', 'A', 'fpsc', 'english', 'published'),
            ('Pakistan shares longest border with:', 'India', 'Afghanistan', 'Iran', 'China', 'A', 'kppsc', 'pakistan-studies', 'published'),
            ('What is 9 squared?', '72', '81', '90', '99', 'B', 'ppsc', 'mathematics', 'published'),
            ('Who discovered penicillin?', 'Alexander Fleming', 'Louis Pasteur', 'Marie Curie', 'Joseph Lister', 'A', 'fpsc', 'general-knowledge', 'published'),
            ('USB stands for:', 'Universal Serial Bus', 'Universal System Bus', 'Unified Serial Bus', 'Universal Serial Buffer', 'A', 'nts', 'computer-science', 'published'),
            ('Synonym of "Brilliant" is:', 'Bright', 'Dull', 'Dim', 'Dark', 'A', 'fpsc', 'english', 'published'),
            ('Greenwich Mean Time is related to:', 'Latitude', 'Longitude', 'Altitude', 'Temperature', 'B', 'ppsc', 'general-knowledge', 'published'),
            ('What is 12 x 12?', '124', '144', '132', '122', 'B', 'ppsc', 'mathematics', 'published'),
            ('The first constitution of Pakistan was adopted in:', '1956', '1962', '1973', '1950', 'A', 'nts', 'pakistan-studies', 'published'),
            ('Antonym of "Curse" is:', 'Blessing', 'Harm', 'Damage', 'Injury', 'A', 'fpsc', 'english', 'published'),
            ('Suez Canal connects:', 'Red Sea and Mediterranean', 'Atlantic and Pacific', 'Indian and Arctic', 'Black and Caspian', 'A', 'ppsc', 'general-knowledge', 'published'),
            ('What is the cube root of 27?', '2', '3', '4', '5', 'B', 'ppsc', 'mathematics', 'published'),
            ('LAN stands for:', 'Local Area Network', 'Large Area Network', 'Long Area Network', 'Light Area Network', 'A', 'fpsc', 'computer-science', 'published'),
            ('Who was the first Chief Justice of Pakistan?', 'Abdul Rashid', 'Munir Ahmad', 'Cornelius', 'Hamoodur Rahman', 'A', 'kppsc', 'pakistan-studies', 'published'),
            ('Synonym of "Eager" is:', 'Keen', 'Reluctant', 'Unwilling', 'Indifferent', 'A', 'fpsc', 'english', 'published'),
            ('What is 100 divided by 4?', '20', '25', '30', '40', 'B', 'ppsc', 'mathematics', 'published'),
            ('Binary code uses which digits?', '0 and 1', '1 and 2', '0 and 2', '1 and 3', 'A', 'nts', 'computer-science', 'published'),
            ('The Khyber Pass connects Pakistan with:', 'India', 'Afghanistan', 'Iran', 'China', 'B', 'ppsc', 'pakistan-studies', 'published'),
            ('Antonym of "Attract" is:', 'Repel', 'Pull', 'Draw', 'Lure', 'A', 'fpsc', 'english', 'published'),
            ('What is the HCF of 24 and 36?', '6', '12', '8', '4', 'B', 'ppsc', 'mathematics', 'published'),
            ('Which organ purifies blood in the human body?', 'Heart', 'Liver', 'Kidney', 'Lungs', 'C', 'fpsc', 'general-knowledge', 'published'),
            ('WWW stands for:', 'World Wide Web', 'World Wide Wave', 'Web Wide World', 'World Web Wide', 'A', 'nts', 'computer-science', 'published'),
            ('Pakistan won Cricket World Cup in:', '1987', '1992', '1996', '1999', 'B', 'ppsc', 'pakistan-studies', 'published'),
            ('Synonym of "Competent" is:', 'Capable', 'Inept', 'Useless', 'Clumsy', 'A', 'fpsc', 'english', 'published'),
            ('What is 45% of 200?', '80', '85', '90', '95', 'C', 'ppsc', 'mathematics', 'published'),
            ('Which vitamin is produced by sunlight?', 'A', 'B', 'C', 'D', 'D', 'fpsc', 'general-knowledge', 'published'),
            ('Antonym of "Permanent" is:', 'Temporary', 'Lasting', 'Eternal', 'Fixed', 'A', 'fpsc', 'english', 'published'),
            ('What is the LCM of 4 and 5?', '10', '15', '20', '25', 'C', 'ppsc', 'mathematics', 'published'),
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

        # Current Affairs MCQs
        ca_cats = {c.slug: c for c in CurrentAffairsCategory.objects.all()}
        ca_mcqs = [
            ('Who is the current Prime Minister of Pakistan?', 'Imran Khan', 'Shehbaz Sharif', 'Nawaz Sharif', 'Asif Zardari', 'B', 'ppsc', 'pakistan-politics'),
            ('Pakistan\'s GDP growth target for FY 2025-26 is:', '2.5%', '3.6%', '4.2%', '5.0%', 'B', 'fpsc', 'pakistan-economy'),
            ('Which country hosted the 2024 G20 Summit?', 'India', 'Brazil', 'Saudi Arabia', 'USA', 'A', 'fpsc', 'global-affairs'),
            ('The IMF approved a new bailout for Pakistan in:', '2023', '2024', '2025', '2022', 'B', 'ppsc', 'pakistan-economy'),
            ('China-Pakistan Economic Corridor (CPEC) started in:', '2013', '2015', '2017', '2019', 'B', 'ppsc', 'international-relations'),
            ('Pakistan won the ICC Champions Trophy in:', '2013', '2017', '2019', '2021', 'B', 'ppsc', 'sports'),
            ('The first AI summit in Pakistan was held in:', '2023', '2024', '2025', '2022', 'B', 'nts', 'science-technology'),
            ('Which country is Pakistan\'s largest trading partner?', 'USA', 'China', 'UAE', 'Saudi Arabia', 'B', 'ppsc', 'international-relations'),
            ('Pakistan\'s current inflation rate is approximately:', '5%', '8%', '12%', '15%', 'B', 'fpsc', 'pakistan-economy'),
            ('The 2024 Paris Olympics were held in:', 'July-August', 'June-July', 'August-September', 'May-June', 'A', 'fpsc', 'sports'),
            ('Who is the current Chief of Army Staff of Pakistan?', 'Qamar Javed Bajwa', 'Asim Munir', 'Raheel Sharif', 'Pervez Musharraf', 'B', 'ppsc', 'pakistan-politics'),
            ('Pakistan\'s digital currency initiative is called:', 'e-Rupee', 'Raast', 'PayPak', 'SBP Digital', 'B', 'nts', 'science-technology'),
            ('The most recent census in Pakistan was conducted in:', '2020', '2021', '2022', '2023', 'D', 'ppsc', 'pakistan-politics'),
            ('Which Middle East country recently normalized ties with Israel via Abraham Accords?', 'Saudi Arabia', 'UAE', 'Qatar', 'Kuwait', 'B', 'fpsc', 'global-affairs'),
            ('Pakistan\'s largest source of remittances is:', 'USA', 'UK', 'Saudi Arabia', 'UAE', 'C', 'ppsc', 'pakistan-economy'),
        ]
        for q, a, b, c, d, correct, exam_slug, cat_slug in ca_mcqs:
            MCQ.objects.get_or_create(
                question_text=q,
                defaults={
                    'option_a': a, 'option_b': b, 'option_c': c, 'option_d': d,
                    'correct_option': correct, 'exam': exams[exam_slug],
                    'subject': subjects['current-affairs'], 'status': 'published',
                    'current_affairs_category': ca_cats.get(cat_slug),
                }
            )

        # Past Papers (published only so they count on homepage)
        papers = [
            ('PPSC Patwari 2024', 'ppsc', 2024, 'published'),
            ('FPSC CSS 2023 English Essay', 'fpsc', 2023, 'published'),
            ('NTS Educator Test 2024', 'nts', 2024, 'published'),
            ('SPSC Assistant 2023', 'spsc', 2023, 'published'),
            ('KPPSC Lecturer 2024', 'kppsc', 2024, 'published'),
            ('BPSC Junior Clerk 2023', 'bpsc', 2023, 'published'),
            ('PPSC Inspector 2022', 'ppsc', 2022, 'published'),
            ('FPSC Assistant Director 2022', 'fpsc', 2022, 'published'),
            ('NTS SSE 2021', 'nts', 2021, 'published'),
            ('SPSC Medical Officer 2021', 'spsc', 2021, 'published'),
            ('PPSC Tehsildar 2020', 'ppsc', 2020, 'published'),
            ('FPSC Customs Inspector 2020', 'fpsc', 2020, 'published'),
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
            ('KPPSC Tehsildar Syllabus', 'kppsc', 'Tehsildar'),
            ('BPSC Junior Clerk Syllabus', 'bpsc', 'Junior Clerk'),
            ('NTS Educator Syllabus', 'nts', 'Educator'),
            ('PPSC Patwari Syllabus', 'ppsc', 'Patwari'),
            ('FPSC Inspector Customs Syllabus', 'fpsc', 'Inspector Customs'),
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
            ('Stenographer', 'spsc', 'Sindh Secretariat', 'active'),
            ('Lecturer English', 'ppsc', 'Higher Education', 'active'),
            ('Medical Officer', 'spsc', 'Health Department', 'active'),
            ('Patwari', 'ppsc', 'Revenue Department', 'active'),
            ('Data Entry Operator', 'nts', 'IT Department', 'active'),
            ('Tehsildar', 'kppsc', 'Revenue Department', 'active'),
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

        # Students (so homepage stats show real enrolled count)
        student_users = [
            ('ahmed_khan', 'ahmed@example.com', 'Ahmed Khan', 'Lahore'),
            ('fatima_ali', 'fatima@example.com', 'Fatima Ali', 'Karachi'),
            ('usman_malik', 'usman@example.com', 'Usman Malik', 'Islamabad'),
            ('aisha_rahman', 'aisha@example.com', 'Aisha Rahman', 'Peshawar'),
            ('bilal_hassan', 'bilal@example.com', 'Bilal Hassan', 'Quetta'),
            ('sana_qadir', 'sana@example.com', 'Sana Qadir', 'Lahore'),
            ('tariq_javed', 'tariq@example.com', 'Tariq Javed', 'Multan'),
        ]
        for username, email, full_name, city in student_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': full_name.split()[0],
                    'last_name': ' '.join(full_name.split()[1:]),
                }
            )
            if created:
                user.set_password('student123')
                user.save()
            Student.objects.get_or_create(
                user=user,
                defaults={'city': city, 'xp_points': random.randint(100, 2000), 'level': random.randint(1, 5)}
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

        # ─── Current Affairs Categories ───
        ca_categories = [
            ('Pakistan Politics', 'pakistan-politics', 'pakistan', 'politics,government,parliament,prime minister,president'),
            ('Pakistan Economy', 'pakistan-economy', 'pakistan', 'economy,gdp,inflation,trade,budget,imf'),
            ('International Relations', 'international-relations', 'world', 'foreign policy,diplomacy,un,china,usa,india'),
            ('Global Affairs', 'global-affairs', 'world', 'world news,international,global,europe,middle east'),
            ('Science & Technology', 'science-technology', 'world', 'science,technology,space,ai,tech,internet'),
            ('Sports', 'sports', 'pakistan', 'cricket,football,sports,olympics,pcb,psl'),
        ]
        for name, slug, region, keywords in ca_categories:
            CurrentAffairsCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'region': region, 'keywords': keywords}
            )

        # ─── Section Content (homepage headings) ───
        sections = [
            ('exam_board', 'Choose Your Commission', 'Prepare for any Pakistani exam board with curated MCQs and past papers.'),
            ('latest_jobs', 'Latest Government Jobs', 'Discover active job openings across all public service commissions.'),
        ]
        for key, title, subtitle in sections:
            SectionContent.objects.get_or_create(
                key=key,
                defaults={'title': title, 'subtitle': subtitle, 'is_active': True}
            )

        # ─── Blog Categories ───
        blog_cats = [
            ('Exam Tips', 'exam-tips', '#10B981', 'lightbulb'),
            ('Study Strategy', 'study-strategy', '#3B82F6', 'book-open'),
            ('Current Affairs', 'current-affairs-blog', '#F59E0B', 'globe'),
            ('Success Stories', 'success-stories', '#8B5CF6', 'trophy'),
            ('Job Guidance', 'job-guidance', '#EF4444', 'briefcase'),
        ]
        blog_categories = {}
        for name, slug, color, icon in blog_cats:
            c, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'type': 'blog', 'color': color, 'icon': icon}
            )
            blog_categories[slug] = c

        # ─── Blog Posts ───
        admin_user = User.objects.filter(username='admin').first()
        blog_posts = [
            {
                'title': 'How to Prepare for PPSC Exams in 30 Days',
                'slug': 'ppsc-exam-preparation-30-days',
                'excerpt': 'A complete 30-day study plan covering all major PPSC subjects with daily targets and revision strategy.',
                'content': '<p>Preparing for PPSC exams requires a structured approach. Start with Pakistan Studies and Current Affairs, then move to English and Mathematics. Practice at least 50 MCQs daily and review past papers every weekend.</p>',
                'category': 'exam-tips',
                'tag_slugs': ['ppsc', 'mcqs', 'preparation'],
                'featured': True,
            },
            {
                'title': 'Top 10 FPSC CSS Interview Tips',
                'slug': 'fpsc-css-interview-tips',
                'excerpt': 'Expert advice from successful CSS officers on how to ace your FPSC interview with confidence.',
                'content': '<p>The CSS interview tests your personality, knowledge, and communication skills. Dress formally, stay updated on current affairs, and practice mock interviews with friends or mentors.</p>',
                'category': 'exam-tips',
                'tag_slugs': ['fpsc', 'css', 'interview'],
                'featured': True,
            },
            {
                'title': 'Best Study Schedule for Working Professionals',
                'slug': 'study-schedule-working-professionals',
                'excerpt': 'Balancing a 9-to-5 job with competitive exam prep? Here is a realistic daily schedule that works.',
                'content': '<p>Dedicate 2 hours in the morning and 1 hour at night. Focus on one subject per day. Use weekends for mock tests and revision. Consistency beats intensity.</p>',
                'category': 'study-strategy',
                'tag_slugs': ['preparation', 'study-strategy'],
                'featured': False,
            },
            {
                'title': 'Understanding Pakistan Economy 2025-26',
                'slug': 'pakistan-economy-2025-26',
                'excerpt': 'Key economic indicators, budget highlights, and IMF program updates every aspirant should know.',
                'content': '<p>Pakistan\'s economy is navigating through IMF programs and structural reforms. Key topics include inflation trends, GDP growth projections, and the role of agriculture and IT exports.</p>',
                'category': 'current-affairs-blog',
                'tag_slugs': ['current-affairs', 'gk'],
                'featured': True,
            },
            {
                'title': 'From Failure to CSS Officer: Ahmed\'s Journey',
                'slug': 'failure-to-css-officer-ahmed',
                'excerpt': 'Ahmed failed his first CSS attempt. Three years later, he topped his batch. Here is his story.',
                'content': '<p> Ahmed started with zero guidance and failed his first attempt. He joined study groups, focused on his weak areas in English Essay and Current Affairs, and finally cleared CSS with flying colors.</p>',
                'category': 'success-stories',
                'tag_slugs': ['css', 'fpsc', 'success-stories'],
                'featured': True,
            },
            {
                'title': 'How to Apply for Government Jobs Online',
                'slug': 'apply-government-jobs-online',
                'excerpt': 'Step-by-step guide to registering on OTS, CTS, and commission portals without common mistakes.',
                'content': '<p>Most candidates make errors in online applications. Keep your CNIC, domicile, and educational documents scanned. Double-check eligibility before applying. Pay fee challan before the deadline.</p>',
                'category': 'job-guidance',
                'tag_slugs': ['job-guidance', 'ppsc', 'nts'],
                'featured': False,
            },
            {
                'title': 'Mastering Pakistan Studies MCQs',
                'slug': 'mastering-pakistan-studies-mcqs',
                'excerpt': 'The most repeated Pakistan Studies questions in PPSC, FPSC, and NTS exams with explanations.',
                'content': '<p>Pakistan Studies is high-scoring if you focus on key dates, constitutional developments, and famous personalities. Practice topic-wise MCQs and memorize the Objectives Resolution and key amendments.</p>',
                'category': 'exam-tips',
                'tag_slugs': ['ppsc', 'fpsc', 'mcqs', 'past-papers'],
                'featured': False,
            },
            {
                'title': 'Why You Should Read Newspapers for Current Affairs',
                'slug': 'read-newspapers-current-affairs',
                'excerpt': 'Newspapers build context that MCQ apps cannot. Learn how to make effective notes from Dawn and The News.',
                'content': '<p>Reading newspapers improves your comprehension and vocabulary. Focus on editorials, international pages, and economic surveys. Make bullet-point notes and revise weekly.</p>',
                'category': 'current-affairs-blog',
                'tag_slugs': ['current-affairs', 'preparation', 'gk'],
                'featured': False,
            },
            {
                'title': 'NTS Test Preparation: Complete Guide',
                'slug': 'nts-test-preparation-guide',
                'excerpt': 'Everything you need to know about NTS test formats, scoring, and recommended books.',
                'content': '<p>NTS tests typically have verbal, analytical, and subject sections. Use NTS official books and practice timed tests. Focus on analogies, synonyms, and basic arithmetic.</p>',
                'category': 'exam-tips',
                'tag_slugs': ['nts', 'preparation', 'mcqs'],
                'featured': False,
            },
            {
                'title': 'Syllabus vs Past Papers: Which One First?',
                'slug': 'syllabus-vs-past-papers',
                'excerpt': 'Should you finish the full syllabus before touching past papers? Experts say no. Here is why.',
                'content': '<p>Start with past papers to understand the exam pattern, then study the syllabus topics that appear most frequently. Use the 70-30 rule: 70% from past papers, 30% from syllabus depth.</p>',
                'category': 'study-strategy',
                'tag_slugs': ['syllabus', 'past-papers', 'preparation'],
                'featured': False,
            },
        ]

        # ─── Blog Tags (dynamically collected from posts so none are missing) ───
        all_tag_slugs = set()
        for bp in blog_posts:
            all_tag_slugs.update(bp['tag_slugs'])
        tags = {}
        for slug in all_tag_slugs:
            name = slug.replace('-', ' ').title()
            t, _ = Tag.objects.get_or_create(slug=slug, defaults={'name': name})
            tags[slug] = t

        for bp in blog_posts:
            post, created = Post.objects.get_or_create(
                slug=bp['slug'],
                defaults={
                    'title': bp['title'],
                    'excerpt': bp['excerpt'],
                    'content': bp['content'],
                    'category': blog_categories[bp['category']],
                    'author': admin_user,
                    'post_type': 'blog',
                    'status': 'published',
                    'is_featured': bp['featured'],
                    'published_at': __import__('django.utils.timezone', fromlist=['now']).now(),
                }
            )
            if created:
                for tslug in bp['tag_slugs']:
                    post.tags.add(tags[tslug])

        # ─── Announcements ───
        announcements = [
            ('PPSC Lecturer jobs closing next week! Apply now.', '/jobs', 'headline'),
            ('New CSS 2025 Syllabus released', '/syllabus/fpsc-css-syllabus-2025', 'link'),
            ('Daily Current Affairs MCQs updated', '/current-affairs', 'link'),
            ('Free AI Tutor for all registered users', '/pricing', 'link'),
        ]
        for text, url, placement in announcements:
            Announcement.objects.get_or_create(
                text=text,
                defaults={'url': url, 'placement': placement, 'is_active': True}
            )

        self.stdout.write(self.style.SUCCESS('Sample data seeded successfully!'))
