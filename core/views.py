from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth import authenticate

from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, ContactMessage
)
from .serializers import (
    ExamSerializer, SubjectSerializer,
    MCQListSerializer, MCQDetailSerializer,
    PastPaperSerializer, SyllabusSerializer,
    JobListingSerializer, StudentSerializer,
    TestResultSerializer, ActivityLogSerializer,
    DashboardStatsSerializer, ContactMessageSerializer,
)


# ─── ViewSets ───────────────────────────────────────────────────────────────


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.annotate(
        mcqs_count=Count('mcqs', distinct=True),
        past_papers_count=Count('past_papers', distinct=True),
        syllabi_count=Count('syllabi', distinct=True)
    ).all()
    serializer_class = ExamSerializer
    lookup_field = 'slug'

class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.annotate(
        mcqs_count=Count('mcqs', distinct=True)
    ).all()
    serializer_class = SubjectSerializer
    lookup_field = 'slug'


class MCQViewSet(viewsets.ModelViewSet):
    queryset = MCQ.objects.select_related('exam', 'subject', 'current_affairs_category').all()

    def get_serializer_class(self):
        if self.action in ['list']:
            return MCQListSerializer
        return MCQDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        subject = self.request.query_params.get('subject')
        current_affairs_category = self.request.query_params.get('current_affairs_category')
        q_status = self.request.query_params.get('status')
        if exam:
            qs = qs.filter(exam__slug=exam)
        if subject:
            qs = qs.filter(subject__slug=subject)
        if current_affairs_category:
            qs = qs.filter(current_affairs_category__slug=current_affairs_category)
        if q_status:
            qs = qs.filter(status=q_status)
        return qs


class PastPaperViewSet(viewsets.ModelViewSet):
    queryset = PastPaper.objects.select_related('exam', 'subject').all()
    serializer_class = PastPaperSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        year = self.request.query_params.get('year')
        if exam:
            qs = qs.filter(exam__slug=exam)
        if year:
            qs = qs.filter(year=year)
        return qs


class SyllabusViewSet(viewsets.ModelViewSet):
    queryset = Syllabus.objects.select_related('exam').all()
    serializer_class = SyllabusSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        if exam:
            qs = qs.filter(exam__slug=exam)
        return qs


class JobListingViewSet(viewsets.ModelViewSet):
    queryset = JobListing.objects.select_related('exam', 'syllabus').all()
    serializer_class = JobListingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        q_status = self.request.query_params.get('status')
        if exam:
            qs = qs.filter(exam__slug=exam)
        if q_status:
            qs = qs.filter(status=q_status)
        return qs


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('user').all()
    serializer_class = StudentSerializer


class TestResultViewSet(viewsets.ModelViewSet):
    queryset = TestResult.objects.select_related('student', 'exam', 'subject').all()
    serializer_class = TestResultSerializer


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.all()[:50]
    serializer_class = ActivityLogSerializer


# ─── Current Affairs Helpers ────────────────────────────────────────────────

DEFAULT_CURRENT_AFFAIRS_CATEGORIES = [
    {'name': "Current IG's of Police", 'slug': 'current-igs-of-police', 'region': 'pakistan', 'keywords': ['ig']},
    {'name': 'Current Governors', 'slug': 'current-governors', 'region': 'pakistan', 'keywords': ['governor']},
    {'name': 'Current Chief Justices', 'slug': 'current-chief-justices', 'region': 'pakistan', 'keywords': ['chief justice']},
    {'name': 'Current Ambassadors', 'slug': 'current-ambassadors', 'region': 'pakistan', 'keywords': ['ambassador']},
    {'name': 'Federal Ministers', 'slug': 'current-federal-ministers', 'region': 'pakistan', 'keywords': ['minister']},
    {'name': 'Chief Ministers', 'slug': 'current-chief-ministers', 'region': 'pakistan', 'keywords': ['chief minister']},
    {'name': 'KPK Ministers', 'slug': 'current-kpk-ministers', 'region': 'pakistan', 'keywords': ['kpk']},
    {'name': 'Punjab Ministers', 'slug': 'current-punjab-ministers', 'region': 'pakistan', 'keywords': ['punjab']},
    {'name': 'Balochistan Ministers', 'slug': 'current-balochistan-ministers', 'region': 'pakistan', 'keywords': ['balochistan']},
    {'name': 'Sindh Ministers', 'slug': 'current-sindh-ministers', 'region': 'pakistan', 'keywords': ['sindh']},
    {'name': 'Gilgit Baltistan Ministers', 'slug': 'gilgit-baltistan-ministers', 'region': 'pakistan', 'keywords': ['gilgit']},
    {'name': 'Presidents & CEOs', 'slug': 'current-presidents-chairmen-ceos', 'region': 'pakistan', 'keywords': ['president']},
    {'name': 'World Organizations', 'slug': 'world-organizations', 'region': 'world', 'keywords': ['organization']},
    {'name': 'Capitals & Currencies', 'slug': 'world-capitals-currencies', 'region': 'world', 'keywords': ['capital']},
    {'name': 'International Days', 'slug': 'international-days', 'region': 'world', 'keywords': ['day']},
    {'name': 'Nobel Prize Winners', 'slug': 'nobel-prize-winners', 'region': 'world', 'keywords': ['nobel']},
    {'name': 'Sports Affairs', 'slug': 'sports-current-affairs', 'region': 'world', 'keywords': ['sport']},
    {'name': 'Technology & Science', 'slug': 'technology-science', 'region': 'world', 'keywords': ['science']},
    {'name': 'World Politics', 'slug': 'world-politics', 'region': 'world', 'keywords': ['politic']},
    {'name': 'Global Economy', 'slug': 'global-economy', 'region': 'world', 'keywords': ['economy']},
    {'name': 'Famous Books & Authors', 'slug': 'famous-books-authors', 'region': 'world', 'keywords': ['author']},
    {'name': 'International Awards', 'slug': 'international-awards', 'region': 'world', 'keywords': ['award']},
    {'name': 'World Health', 'slug': 'world-health', 'region': 'world', 'keywords': ['health']},
    {'name': 'Education & Universities', 'slug': 'education-universities', 'region': 'world', 'keywords': ['education']},
]


def _current_affairs_categories():
    """Return active category config from DB; fallback only before migrations run."""
    try:
        categories = list(
            CurrentAffairsCategory.objects
            .filter(is_active=True)
            .order_by('region', 'sort_order', 'name')
        )
    except (OperationalError, ProgrammingError):
        return DEFAULT_CURRENT_AFFAIRS_CATEGORIES

    return [
        {
            'name': category.name,
            'slug': category.slug,
            'region': category.region,
            'keywords': category.keyword_list(),
        }
        for category in categories
    ]


def _current_affairs_category_q(category):
    keywords = category.get('keywords') or [category['slug'].replace('-', ' ')]
    query = Q()
    for keyword in keywords:
        query |= Q(question_text__icontains=keyword)
    return query


def _current_affairs_category_filter(category):
    return (
        Q(current_affairs_category__slug=category['slug']) |
        (Q(current_affairs_category__isnull=True) & _current_affairs_category_q(category))
    )


def _serialize_current_affairs_question(question, index):
    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    return {
        'id': index,
        'question': question.question_text,
        'options': [question.option_a, question.option_b, question.option_c, question.option_d],
        'correct': opt_map.get(question.correct_option, 0),
    }


# ─── Dashboard Stats ────────────────────────────────────────────────────────

@api_view(['GET'])
def dashboard_stats(request):
    """Return aggregate stats for the admin dashboard."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    total_mcqs = MCQ.objects.count()
    mcqs_this_week = MCQ.objects.filter(created_at__gte=week_start).count()

    registered_users = User.objects.count()
    users_this_week = User.objects.filter(date_joined__gte=week_start).count()

    active_jobs = JobListing.objects.filter(status='active').count()
    jobs_today = JobListing.objects.filter(created_at__gte=today_start).count()

    tests_today = TestResult.objects.filter(created_at__gte=today_start).count()
    tests_yesterday = TestResult.objects.filter(
        created_at__gte=yesterday_start,
        created_at__lt=today_start
    ).count()
    tests_vs_yesterday = tests_today - tests_yesterday

    data = {
        'total_mcqs': total_mcqs,
        'registered_users': registered_users,
        'active_jobs': active_jobs,
        'tests_taken_today': tests_today,
        'mcqs_this_week': mcqs_this_week,
        'users_this_week': users_this_week,
        'jobs_today': jobs_today,
        'tests_vs_yesterday': tests_vs_yesterday,
    }
    serializer = DashboardStatsSerializer(data)
    return Response(serializer.data)


@api_view(['GET'])
def recent_mcqs(request):
    """Return most recent 10 MCQs for the dashboard table."""
    mcqs = MCQ.objects.select_related('exam', 'subject').all()[:10]
    serializer = MCQListSerializer(mcqs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def recent_activity(request):
    """Return most recent 10 activity log entries."""
    activities = ActivityLog.objects.all()[:10]
    serializer = ActivityLogSerializer(activities, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def bulk_upload_mcqs(request):
    """Handle bulk creation of MCQs from Excel uploader."""
    data = request.data
    board_slug = data.get('board')
    subject_name = data.get('subject')
    questions = data.get('questions', [])
    status_val = data.get('status', 'draft')
    category_slug = data.get('current_affairs_category') or data.get('current_affairs_category_slug')

    if not board_slug or not subject_name or not questions:
        return Response({'error': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)

    # Get or create Exam and Subject
    exam, _ = Exam.objects.get_or_create(slug=board_slug, defaults={'name': board_slug.upper()})
    subject, _ = Subject.objects.get_or_create(name=subject_name, defaults={'slug': subject_name.lower().replace(' ', '-')})
    current_affairs_category = None
    if category_slug:
        current_affairs_category = CurrentAffairsCategory.objects.filter(
            slug=category_slug,
            is_active=True,
        ).first()

    created_count = 0
    for q in questions:
        item_category = current_affairs_category
        item_category_slug = q.get('current_affairs_category') or q.get('current_affairs_category_slug')
        if item_category_slug:
            item_category = CurrentAffairsCategory.objects.filter(
                slug=item_category_slug,
                is_active=True,
            ).first()

        MCQ.objects.create(
            exam=exam,
            subject=subject,
            question_text=q.get('question_text', ''),
            option_a=q.get('option_a', ''),
            option_b=q.get('option_b', ''),
            option_c=q.get('option_c', ''),
            option_d=q.get('option_d', ''),
            correct_option=q.get('correct_answer', 'A')[:1].upper(),
            explanation=q.get('explanation', ''),
            current_affairs_category=item_category if subject.slug == 'current-affairs' else None,
            source_url=data.get('source', ''),
            status=status_val
        )
        created_count += 1

    return Response({'message': f'Successfully created {created_count} MCQs', 'count': created_count})

# ─── Frontend APIs ────────────────────────────────────────────────────────────

@api_view(['GET'])
def frontend_home(request):
    """Return all necessary data for the frontend home page."""
    # 1. Popular Subjects (top 8 by MCQ count)
    subjects = Subject.objects.annotate(mcq_count=Count('mcqs')).order_by('-mcq_count')[:8]
    subjects_data = [{'name': s.name, 'slug': s.slug, 'count': s.mcq_count} for s in subjects]

    # 2. Latest Jobs (top 4 active)
    jobs = JobListing.objects.filter(status=JobListing.Status.ACTIVE).select_related('exam', 'syllabus').order_by('-created_at')[:4]
    jobs_data = []
    for j in jobs:
        jobs_data.append({
            'id': j.id,
            'title': j.title,
            'org': j.exam.name if j.exam else j.department,
            'location': j.location if j.location else ('Federal' if j.exam and 'FPSC' in j.exam.name else 'Provincial'),
            'date': j.last_date.strftime('%d %b') if j.last_date else 'Closing Soon',
            'status': 'New', 
            'bps': j.bps_grade if j.bps_grade else 'BPS-14',
            'syllabus_id': j.syllabus_id,
            'syllabus_title': j.syllabus.title if j.syllabus else '',
        })

    # 3. Stats (total MCQs, Past Papers, Syllabi, Students)
    stats = {
        'total_mcqs': MCQ.objects.filter(status='published').count(),
        'total_papers': PastPaper.objects.filter(status='published').count(),
        'total_syllabi': Syllabus.objects.count(),
        'total_students': Student.objects.count()
    }
    
    # 4. Exams/Boards (top 4 by MCQ count, annotated with papers and syllabi counts)
    exams = Exam.objects.annotate(
        mcq_count=Count('mcqs', distinct=True),
        paper_count=Count('past_papers', distinct=True),
        syllabus_count=Count('syllabi', distinct=True)
    ).order_by('-mcq_count')[:4]
    
    exams_data = []
    for e in exams:
        exams_data.append({
            'name': e.name,
            'slug': e.slug,
            'count': e.mcq_count,
            'paper_count': e.paper_count,
            'syllabus_count': e.syllabus_count
        })
    
    return Response({
        'subjects': subjects_data,
        'jobs': jobs_data,
        'stats': stats,
        'exams': exams_data
    })


# ─── Auth APIs ──────────────────────────────────────────────────────────────

@api_view(['POST'])
def student_signup(request):
    """Handle student registration."""
    data = request.data
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    accept_terms = data.get('accept_terms')
    full_name = data.get('full_name', '')
    username = data.get('username')

    if not email or not password or not confirm_password:
        return Response({'error': 'Email, password, and confirm password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if password != confirm_password:
        return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    if not accept_terms:
        return Response({'error': 'You must accept the terms and conditions.'}, status=status.HTTP_400_BAD_REQUEST)

    if not username:
        username = email.split('@')[0]
        # ensure unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=full_name.split(' ')[0] if full_name else '',
        last_name=' '.join(full_name.split(' ')[1:]) if full_name else ''
    )

    # Create empty student profile
    student = Student.objects.create(user=user)

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def student_login(request):
    """Handle student login."""
    data = request.data
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Allow login with email too
    user_obj = User.objects.filter(email=username).first()
    if user_obj:
        username = user_obj.username

    user = authenticate(username=username, password=password)

    if not user:
        return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    token, _ = Token.objects.get_or_create(user=user)
    
    student = getattr(user, 'student_profile', None)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': student.phone if student else '',
            'city': student.city if student else '',
            'avatar': student.avatar.url if student and student.avatar else None,
        }
    })


# ─── Current Affairs APIs ───────────────────────────────────────────────────

@api_view(['GET'])
def current_affairs_months(request):
    """
    Returns grouped list of months with MCQ counts for subject 'Current Affairs'
    grouped by year.
    """
    try:
        mcqs = MCQ.objects.filter(subject__slug='current-affairs')
        
        if not mcqs.exists():
            return Response({
                '2026': [
                    { 'name': 'January 2026', 'slug': 'january', 'count': 120 },
                    { 'name': 'February 2026', 'slug': 'february', 'count': 95 },
                    { 'name': 'March 2026', 'slug': 'march', 'count': 110 },
                    { 'name': 'April 2026', 'slug': 'april', 'count': 85 },
                    { 'name': 'May 2026', 'slug': 'may', 'count': 70 },
                ],
                '2025': [
                    { 'name': 'December 2025', 'slug': 'december', 'count': 130 },
                    { 'name': 'November 2025', 'slug': 'november', 'count': 115 },
                    { 'name': 'October 2025', 'slug': 'october', 'count': 105 },
                    { 'name': 'September 2025', 'slug': 'september', 'count': 90 },
                    { 'name': 'August 2025', 'slug': 'august', 'count': 88 },
                ]
            })
            
        grouped = {}
        for mcq in mcqs:
            yr = str(mcq.created_at.year)
            m_name = mcq.created_at.strftime('%B')
            m_slug = m_name.lower()
            
            if yr not in grouped:
                grouped[yr] = {}
            if m_slug not in grouped[yr]:
                grouped[yr][m_slug] = {
                    'name': f"{m_name} {yr}",
                    'slug': m_slug,
                    'count': 0
                }
            grouped[yr][m_slug]['count'] += 1
            
        res = {}
        for yr, months_dict in grouped.items():
            res[yr] = list(months_dict.values())
        return Response(res)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def current_affairs_detail(request, year, month):
    """
    Returns MCQs for a specific year and month categorized under International/Pakistan Affairs
    """
    try:
        import calendar
        try:
            month_num = list(calendar.month_name).index(month.title())
        except ValueError:
            month_num = 1

        mcqs = MCQ.objects.filter(
            subject__slug='current-affairs',
            created_at__year=year,
            created_at__month=month_num
        )
        
        if not mcqs.exists():
            return Response({
                'title': f"{month.title()} {year} Current Affairs",
                'categories': []
            })

        questions_list = [
            _serialize_current_affairs_question(q, index)
            for index, q in enumerate(mcqs, start=1)
        ]
            
        pk_questions = [q for q in questions_list if 'pakistan' in q['question'].lower()]
        intl_questions = [q for q in questions_list if 'pakistan' not in q['question'].lower()]
        
        categories = []
        if intl_questions:
            categories.append({
                'name': 'International Affairs',
                'questions': intl_questions
            })
        if pk_questions:
            categories.append({
                'name': 'Pakistan Affairs',
                'questions': pk_questions
            })
            
        if not categories:
            categories.append({
                'name': 'General Current Affairs',
                'questions': questions_list
            })
            
        return Response({
            'title': f"{month.title()} {year} Current Affairs",
            'categories': categories
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def frontend_mcq_subjects(request):
    """Return all subjects that have MCQs for the frontend dynamic routing."""
    subjects = Subject.objects.annotate(mcq_count=Count('mcqs')).filter(mcq_count__gt=0).order_by('-mcq_count')
    data = [{'name': s.name, 'slug': s.slug, 'count': s.mcq_count} for s in subjects]
    return Response(data)

@api_view(['GET'])
def frontend_mcq_sets(request, subject_slug):
    """Return the calculated 'Test Sets' (sets of 20 MCQs) for a given subject."""
    from django.shortcuts import get_object_or_404
    subject = get_object_or_404(Subject, slug=subject_slug)
    total = MCQ.objects.filter(subject=subject, status='published').count()
    if total == 0:
        total = MCQ.objects.filter(subject=subject).count() # fallback if none published

    if total == 0:
        return Response({'error': 'No MCQs found for this subject'}, status=status.HTTP_404_NOT_FOUND)

    set_size = 20
    num_sets = (total + set_size - 1) // set_size
    
    sets = []
    for i in range(num_sets):
        start = i * set_size + 1
        end = min((i + 1) * set_size, total)
        sets.append({
            'id': str(i + 1),
            'name': f'Test {i + 1}',
            'range': f'Questions {start}-{end}',
            'count': end - start + 1
        })
        
    return Response({
        'bank': {'title': subject.name, 'slug': subject.slug},
        'total': total,
        'sets': sets
    })

@api_view(['GET'])
def frontend_mcq_set_detail(request, subject_slug, set_id):
    """Return exactly 20 questions for a specific test set."""
    from django.shortcuts import get_object_or_404
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    try:
        set_id = int(set_id)
    except ValueError:
        return Response({'error': 'Invalid set ID'}, status=400)

    set_size = 20
    offset = (set_id - 1) * set_size
    
    # Try fetching only published MCQs first
    mcqs = MCQ.objects.filter(subject=subject, status='published').order_by('id')[offset:offset+set_size]
    if not mcqs:
        # Fallback to any status
        mcqs = MCQ.objects.filter(subject=subject).order_by('id')[offset:offset+set_size]

    if not mcqs:
        return Response({'error': 'Set not found'}, status=404)

    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    questions_list = []
    
    for q in mcqs:
        questions_list.append({
            'id': q.id,
            'question': q.question_text,
            'options': [q.option_a, q.option_b, q.option_c, q.option_d],
            'correct': opt_map.get(q.correct_option, 0),
            'explanation': q.explanation
        })

    return Response({
        'title': subject.name,
        'questions': questions_list
    })

@api_view(['GET'])
def frontend_current_affairs_category_detail(request, slug):
    """Serve questions by DB-configured current-affairs category."""
    category = next(
        (item for item in _current_affairs_categories() if item['slug'] == slug),
        None,
    )
    if category is None:
        return Response(
            {'error': 'Current affairs category not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    mcqs = (
        MCQ.objects
        .filter(subject__slug='current-affairs')
        .filter(_current_affairs_category_filter(category))
        .order_by('-created_at')
    )

    questions_list = [
        _serialize_current_affairs_question(q, index)
        for index, q in enumerate(mcqs, start=1)
    ]

    return Response({
        'title': category['name'],
        'slug': category['slug'],
        'region': category['region'],
        'questions': questions_list
    })

# ─── Past Papers Frontend APIs ──────────────────────────────────────────────

@api_view(['GET'])
def frontend_past_papers_menu(request):
    """
    Returns all exams with their past-paper categories (subjects) for the
    mega-menu hover dropdown.  Shape:
      [ { exam_name, exam_slug, badge_color, subjects: [{name, slug, count}] } ]
    """
    exams = Exam.objects.annotate(
        paper_count=Count('past_papers', distinct=True)
    ).filter(paper_count__gt=0).order_by('-paper_count')

    result = []
    for exam in exams:
        subjects = (
            Subject.objects
            .filter(past_papers__exam=exam)
            .annotate(count=Count('past_papers'))
            .order_by('-count')
        )
        result.append({
            'exam_name':   exam.name,
            'exam_slug':   exam.slug,
            'badge_color': exam.badge_color,
            'subjects': [
                {'name': s.name, 'slug': s.slug, 'count': s.count}
                for s in subjects
            ],
        })
    return Response(result)


@api_view(['GET'])
def frontend_past_papers_list(request):
    """
    Returns a numbered list of past papers.
    Query params: exam=<slug>  subject=<slug>  page=<n>
    """
    exam_slug    = request.query_params.get('exam', '')
    subject_slug = request.query_params.get('subject', '')
    page_num     = int(request.query_params.get('page', 1))
    page_size    = 20

    qs = PastPaper.objects.select_related('exam', 'subject').filter(
        status=PastPaper.Status.PUBLISHED
    )
    if exam_slug:
        qs = qs.filter(exam__slug=exam_slug)
    if subject_slug:
        qs = qs.filter(subject__slug=subject_slug)
    qs = qs.order_by('-year', '-created_at')

    from django.core.paginator import Paginator
    paginator  = Paginator(qs, page_size)
    page_obj   = paginator.get_page(page_num)

    papers = []
    for idx, p in enumerate(page_obj.object_list, start=(page_num - 1) * page_size + 1):
        papers.append({
            'number':      idx,
            'id':          p.id,
            'title':       p.title,
            'slug':        p.slug,
            'year':        p.year,
            'exam_name':   p.exam.name,
            'exam_slug':   p.exam.slug,
            'subject_name': p.subject.name if p.subject else '',
            'subject_slug': p.subject.slug if p.subject else '',
            'mcq_count':   p.mcqs.count(),
            'source_url':  p.source_url,
            'has_pdf':     bool(p.pdf_file),
        })

    return Response({
        'count':      paginator.count,
        'num_pages':  paginator.num_pages,
        'page':       page_num,
        'papers':     papers,
    })


@api_view(['GET'])
def frontend_past_paper_detail(request, slug):
    """
    Returns a single past paper's info + all linked MCQs.
    URL: /api/frontend/past-papers/<slug>/
    """
    from django.shortcuts import get_object_or_404
    paper = get_object_or_404(
        PastPaper.objects.select_related('exam', 'subject'),
        slug=slug, status=PastPaper.Status.PUBLISHED
    )

    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    mcqs = paper.mcqs.order_by('id')
    questions = []
    for i, q in enumerate(mcqs, start=1):
        questions.append({
            'number':      i,
            'id':          q.id,
            'question':    q.question_text,
            'options':     [q.option_a, q.option_b, q.option_c,
                            q.option_d] if q.option_d else [q.option_a, q.option_b, q.option_c],
            'correct':     opt_map.get(q.correct_option, 0),
            'explanation': q.explanation,
        })

    return Response({
        'id':           paper.id,
        'title':        paper.title,
        'slug':         paper.slug,
        'year':         paper.year,
        'exam_name':    paper.exam.name,
        'exam_slug':    paper.exam.slug,
        'subject_name': paper.subject.name if paper.subject else '',
        'subject_slug': paper.subject.slug if paper.subject else '',
        'source_url':   paper.source_url,
        'has_pdf':      bool(paper.pdf_file),
        'pdf_url':      paper.pdf_file.url if paper.pdf_file else None,
        'mcq_count':    len(questions),
        'questions':    questions,
    })


@api_view(['GET'])
def frontend_current_affairs_topics(request):
    """Return DB-configured Current Affairs categories with live MCQ counts."""
    mcqs = MCQ.objects.filter(subject__slug='current-affairs')

    grouped = {'pakistan': [], 'world': []}
    for category in _current_affairs_categories():
        region = category.get('region') or 'pakistan'
        grouped.setdefault(region, []).append({
            'name': category['name'],
            'slug': category['slug'],
            'count': mcqs.filter(_current_affairs_category_filter(category)).count(),
        })

    return Response(grouped)


# ─── Syllabus Frontend APIs ──────────────────────────────────────────────────

@api_view(['GET'])
def frontend_syllabus_list(request):
    """
    Returns a list of all syllabus entries grouped by exam.
    Query param: exam=<slug>
    """
    exam_slug = request.query_params.get('exam', '')
    qs = Syllabus.objects.select_related('exam').order_by('exam__name', 'title')
    if exam_slug:
        qs = qs.filter(exam__slug=exam_slug)

    from django.db.models import F
    data = []
    for s in qs:
        data.append({
            'id':         s.id,
            'title':      s.title,
            'post_name':  s.post_name,
            'exam_name':  s.exam.name,
            'exam_slug':  s.exam.slug,
            'has_pdf':    bool(s.pdf_file),
            'created_at': s.created_at.isoformat(),
        })
    return Response(data)


@api_view(['GET'])
def frontend_syllabus_detail(request, pk):
    """Returns one syllabus record including full content and PDF url."""
    from django.shortcuts import get_object_or_404
    s = get_object_or_404(Syllabus.objects.select_related('exam'), pk=pk)
    return Response({
        'id':         s.id,
        'title':      s.title,
        'post_name':  s.post_name,
        'exam_name':  s.exam.name,
        'exam_slug':  s.exam.slug,
        'content':    s.content,
        'has_pdf':    bool(s.pdf_file),
        'pdf_url':    s.pdf_file.url if s.pdf_file else None,
        'created_at': s.created_at.isoformat(),
    })


@api_view(['POST'])
def frontend_contact(request):
    """Accept a contact form submission from the public frontend."""
    serializer = ContactMessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': True, 'message': 'Your message has been received. We\'ll get back to you soon.'}, status=status.HTTP_201_CREATED)
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
