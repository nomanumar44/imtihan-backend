import hmac
import json
import logging
import random
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.conf import settings
from django.db import models, transaction
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, throttle_classes, authentication_classes, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .gamification import (
    XP_PER_CORRECT, XP_PER_TEST, level_for_xp, next_level_xp as level_threshold, user_streak,
)
from .permissions import IsStaffOrReadOnly, is_staff_request

from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, ContactMessage, Announcement,
    SectionContent, Bookmark, EmailSubscription,
    Achievement, UserAchievement, DailyPracticeLog, TestAnswer, Notification,
    Category, Tag, Post, Comment, NewsSubscriber,
    AIUsage, ChatSession, ChatMessage,
    UserProfile, UserEducation, UserExperience, UserDocument, JobApplication,
    ServicePlan, ApplicationRequest, AdminNote, AISubscription,
)
from .serializers import (
    ExamSerializer, SubjectSerializer,
    MCQListSerializer, MCQDetailSerializer,
    PastPaperSerializer, SyllabusSerializer,
    JobListingSerializer, StudentSerializer,
    TestResultSerializer, TestResultDetailSerializer, ActivityLogSerializer,
    DashboardStatsSerializer, ContactMessageSerializer, UserProfileSerializer,
    BookmarkSerializer, EmailSubscriptionSerializer, NotificationSerializer,
    CategorySerializer, TagSerializer, PostListSerializer, PostDetailSerializer,
    CommentSerializer, CommentCreateSerializer, NewsSubscriberSerializer,
    AIUsageSerializer, ChatSessionSerializer, ChatMessageSerializer,
    JobProfileSerializer, UserEducationSerializer, UserExperienceSerializer,
    UserDocumentSerializer, JobApplicationSerializer,
    ServicePlanSerializer, ApplicationRequestSerializer, AdminNoteSerializer,
)


# ─── ViewSets ───────────────────────────────────────────────────────────────


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.annotate(
        mcqs_count=Count('mcqs', filter=Q(mcqs__status='published'), distinct=True),
        past_papers_count=Count('past_papers', filter=Q(past_papers__status='published'), distinct=True),
        syllabi_count=Count('syllabi', distinct=True)
    ).order_by('name')
    serializer_class = ExamSerializer
    permission_classes = [IsStaffOrReadOnly]
    lookup_field = 'slug'

class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.annotate(
        mcqs_count=Count('mcqs', filter=Q(mcqs__status='published'), distinct=True)
    ).order_by('name')
    serializer_class = SubjectSerializer
    permission_classes = [IsStaffOrReadOnly]
    lookup_field = 'slug'


class MCQViewSet(viewsets.ModelViewSet):
    queryset = MCQ.objects.select_related('exam', 'subject', 'current_affairs_category').all()
    permission_classes = [IsStaffOrReadOnly]
    # Numeric ids only, so sibling routes such as mcqs/bulk-upload/ are not captured.
    lookup_value_regex = r'\d+'

    def get_serializer_class(self):
        if self.action in ['list']:
            return MCQListSerializer
        return MCQDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not is_staff_request(self.request):
            qs = qs.filter(status=MCQ.Status.PUBLISHED)
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
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if not is_staff_request(self.request):
            qs = qs.filter(status=PastPaper.Status.PUBLISHED)
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
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        if exam:
            qs = qs.filter(exam__slug=exam)
        return qs


def open_jobs(qs, today=None):
    """Active/upcoming jobs whose last date (if known) hasn't passed."""
    today = today or timezone.localdate()
    return qs.filter(
        status__in=[JobListing.Status.ACTIVE, JobListing.Status.UPCOMING],
    ).exclude(last_date__lt=today)


class JobListingViewSet(viewsets.ModelViewSet):
    queryset = JobListing.objects.select_related('exam', 'syllabus').all()
    serializer_class = JobListingSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        exam = self.request.query_params.get('exam')
        q_status = self.request.query_params.get('status')
        if exam:
            qs = qs.filter(exam__slug=exam)
        if q_status == JobListing.Status.CLOSED:
            # Closed explicitly, or still marked open but past its last date
            qs = qs.filter(Q(status=q_status) | Q(last_date__lt=timezone.localdate()))
        elif q_status:
            qs = qs.filter(status=q_status).exclude(last_date__lt=timezone.localdate())
        return qs


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('user').order_by('id')
    serializer_class = StudentSerializer
    permission_classes = [IsAdminUser]


class TestResultViewSet(viewsets.ModelViewSet):
    queryset = TestResult.objects.select_related('student', 'exam', 'subject').all()
    serializer_class = TestResultSerializer
    permission_classes = [IsAdminUser]


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdminUser]


class SignupThrottle(AnonRateThrottle):
    scope = 'signup'  # own cache key, not shared with the global anon limit
    rate = '5/min'

class LoginThrottle(AnonRateThrottle):
    scope = 'login'  # own cache key, not shared with the global anon limit
    rate = '10/min'

class ContactThrottle(AnonRateThrottle):
    scope = 'contact'  # own cache key, not shared with the global anon limit
    rate = '3/min'


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
    """Return active category config from DB; fallback to defaults if empty or table missing."""
    try:
        categories = list(
            CurrentAffairsCategory.objects
            .filter(is_active=True)
            .order_by('region', 'sort_order', 'name')
        )
    except (OperationalError, ProgrammingError):
        return DEFAULT_CURRENT_AFFAIRS_CATEGORIES

    if not categories:
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
@permission_classes([IsAdminUser])
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
@permission_classes([IsAdminUser])
def recent_mcqs(request):
    """Return most recent 10 MCQs for the dashboard table."""
    mcqs = MCQ.objects.select_related('exam', 'subject').all()[:10]
    serializer = MCQListSerializer(mcqs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def recent_activity(request):
    """Return most recent 10 activity log entries."""
    activities = ActivityLog.objects.all()[:10]
    serializer = ActivityLogSerializer(activities, many=True)
    return Response(serializer.data)


_CORRECT_OPTION_RE = re.compile(r'(?:OPTION|OPT|ANSWER|ANS)?\s*[:.\-]?\s*\(?([A-D])\)?\.?')


def _normalize_correct_option(raw, options):
    """Map 'b', 'Option B', '(b)', '2' or the option's own text to a letter A–D ('' if unknown)."""
    value = str(raw or '').strip()
    if not value:
        return ''
    match = _CORRECT_OPTION_RE.fullmatch(value.upper())
    if match:
        return match.group(1)
    if value in ('1', '2', '3', '4'):
        return 'ABCD'[int(value) - 1]
    for key in 'abcd':
        if options[key] and options[key].lower() == value.lower():
            return key.upper()
    return ''


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_upload_mcqs(request):
    """Handle bulk creation of MCQs from the dashboard Excel/manual uploader."""
    data = request.data
    board_slug = (data.get('board') or '').strip().lower()
    subject_name = (data.get('subject') or '').strip()
    questions = data.get('questions', [])
    status_val = data.get('status', MCQ.Status.DRAFT)
    category_slug = data.get('current_affairs_category') or data.get('current_affairs_category_slug')

    if not board_slug or not subject_name or not questions or not isinstance(questions, list):
        return Response({'error': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)
    if status_val not in MCQ.Status.values:
        return Response({'error': f'Invalid status "{status_val}".'}, status=status.HTTP_400_BAD_REQUEST)

    # Reuse an existing subject by name or slug so uploads don't create near-duplicates.
    subject_slug = slugify(subject_name)
    subject = Subject.objects.filter(Q(name__iexact=subject_name) | Q(slug=subject_slug)).first()

    errors = []
    rows = []
    for index, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            errors.append(f'Row {index}: invalid row.')
            continue
        question_text = (q.get('question_text') or '').strip()
        options = {key: str(q.get(f'option_{key}') or '').strip() for key in 'abcd'}
        correct = _normalize_correct_option(q.get('correct_answer'), options)
        if not question_text or not options['a'] or not options['b'] or not options['c']:
            errors.append(f'Row {index}: question text and options A–C are required.')
        elif correct not in ('A', 'B', 'C', 'D') or (correct == 'D' and not options['d']):
            errors.append(f'Row {index}: correct answer must be A–D and point to a non-empty option.')
        else:
            rows.append((q, question_text, options, correct))

    if errors:
        return Response({'error': 'Some rows are invalid.', 'errors': errors[:50]}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        exam, _ = Exam.objects.get_or_create(slug=board_slug, defaults={'name': board_slug.upper()})
        if subject is None:
            subject = Subject.objects.create(name=subject_name, slug=subject_slug)
        current_affairs_category = None
        if category_slug:
            current_affairs_category = CurrentAffairsCategory.objects.filter(
                slug=category_slug,
                is_active=True,
            ).first()

        for q, question_text, options, correct in rows:
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
                question_text=question_text,
                option_a=options['a'],
                option_b=options['b'],
                option_c=options['c'],
                option_d=options['d'],
                correct_option=correct,
                explanation=q.get('explanation', '') or '',
                current_affairs_category=item_category if subject.slug == 'current-affairs' else None,
                source_url=data.get('source', '') or '',
                status=status_val,
                created_by=request.user,
            )

    created_count = len(rows)
    return Response({'message': f'Successfully created {created_count} MCQs', 'count': created_count})

# ─── Frontend APIs ────────────────────────────────────────────────────────────

@api_view(['GET'])
def frontend_home(request):
    """Return all necessary data for the frontend home page (cached 5 min)."""
    cache_key = 'frontend_home'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    # 1. Popular Subjects (top 8 by published MCQ count)
    subjects = Subject.objects.annotate(mcq_count=Count('mcqs', filter=Q(mcqs__status='published'))).order_by('-mcq_count')[:8]
    subjects_data = [
        {'name': s.name, 'slug': s.slug, 'count': s.mcq_count, 'icon': s.icon, 'badge_color': s.badge_color}
        for s in subjects
    ]

    # 2. Latest Jobs (latest 5 open ones; a passed last date means closed)
    today = timezone.localdate()
    jobs = open_jobs(JobListing.objects.all(), today).select_related('exam', 'syllabus').order_by('-created_at')[:5]
    jobs_data = []
    for j in jobs:
        last_date = j.last_date
        # "Closing" only when a real last date is within a week; never guessed.
        if last_date and last_date <= today + timedelta(days=7):
            job_status = 'Closing'
        elif j.created_at and timezone.localdate(j.created_at) >= today - timedelta(days=7):
            job_status = 'New'
        else:
            job_status = 'Open'
        jobs_data.append({
            'id': j.id,
            'title': j.title,
            'slug': str(j.id),  # job pages are addressed by id (/jobs/<id>)
            'org': j.exam.name if j.exam else j.department,
            'location': j.location,
            'date': j.last_date.strftime('%d %b %Y') if j.last_date else '',
            'last_date': j.last_date.isoformat() if j.last_date else None,
            'apply_link': j.apply_link,
            'status': job_status,
            'bps': j.bps_grade,
            'syllabus_id': j.syllabus_id,
            'syllabus_title': j.syllabus.title if j.syllabus else '',
            'updated_at': j.updated_at.isoformat() if j.updated_at else None,
        })

    # 3. Stats (total MCQs, Past Papers, Syllabi, Students)
    stats = {
        'total_mcqs': MCQ.objects.filter(status='published').count(),
        'total_papers': PastPaper.objects.filter(status='published').count(),
        'total_syllabi': Syllabus.objects.count(),
        'total_students': Student.objects.count()
    }
    
    # 4. Exams/Boards (all boards, ordered by published MCQ count)
    exams = Exam.objects.annotate(
        mcq_count=Count('mcqs', filter=Q(mcqs__status='published'), distinct=True),
        paper_count=Count('past_papers', filter=Q(past_papers__status='published'), distinct=True),
        syllabus_count=Count('syllabi', distinct=True)
    ).order_by('-mcq_count')
    
    exams_data = []
    for e in exams:
        exams_data.append({
            'name': e.name,
            'slug': e.slug,
            'description': e.description,
            'icon': e.icon,
            'badge_color': e.badge_color,
            'count': e.mcq_count,
            'paper_count': e.paper_count,
            'syllabus_count': e.syllabus_count
        })
    
    # 5. Editable section headings/subheadings
    sections = {
        s.key: {'title': s.title, 'subtitle': s.subtitle}
        for s in SectionContent.objects.filter(is_active=True)
    }

    data = {
        'subjects': subjects_data,
        'jobs': jobs_data,
        'stats': stats,
        'exams': exams_data,
        'sections': sections,
    }
    cache.set(cache_key, data, timeout=300)
    return Response(data)


@api_view(['GET'])
def frontend_announcements(request):
    """Return active announcement-bar items split by placement."""
    items = Announcement.objects.filter(is_active=True)
    headline = items.filter(placement=Announcement.Placement.HEADLINE).first()
    links = items.filter(placement=Announcement.Placement.LINK)

    def serialize(item):
        if not item:
            return None
        return {'id': item.id, 'text': item.text, 'url': item.url or None}

    return Response({
        'headline': serialize(headline),
        'links': [serialize(link) for link in links],
    })


# ─── Auth APIs ──────────────────────────────────────────────────────────────

def _password_error(password, user=None):
    """Run the configured AUTH_PASSWORD_VALIDATORS; return a message or None."""
    try:
        validate_password(password, user)
    except DjangoValidationError as e:
        return ' '.join(e.messages)
    return None


@api_view(['POST'])
@throttle_classes([SignupThrottle])
def student_signup(request):
    """Handle student registration."""
    data = request.data
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    accept_terms = data.get('accept_terms')
    full_name = data.get('full_name', '')
    username = data.get('username')

    email = (email or '').strip()
    if not email or not password or not confirm_password:
        return Response({'error': 'Email, password, and confirm password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if password != confirm_password:
        return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    if not accept_terms:
        return Response({'error': 'You must accept the terms and conditions.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email__iexact=email).exists():
        return Response({'error': 'Email already registered.'}, status=status.HTTP_400_BAD_REQUEST)

    if username:
        if User.objects.filter(username__iexact=username).exists():
            return Response({'error': 'Username is already taken.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        username = email.split('@')[0]
        # ensure unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

    password_error = _password_error(password, User(username=username, email=email))
    if password_error:
        return Response({'error': password_error}, status=status.HTTP_400_BAD_REQUEST)

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

    avatar_url = None
    if student.avatar:
        avatar_url = student.avatar.url
    elif student.google_picture:
        avatar_url = student.google_picture

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
            'avatar': avatar_url,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
def student_login(request):
    """Handle student login."""
    data = request.data
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Allow login with email too
    user_obj = User.objects.filter(email__iexact=username.strip()).first()
    if user_obj:
        username = user_obj.username

    user = authenticate(username=username, password=password)

    if not user:
        return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    token, _ = Token.objects.get_or_create(user=user)
    
    student = getattr(user, 'student_profile', None)

    avatar_url = None
    if student:
        if student.avatar:
            avatar_url = student.avatar.url
        elif student.google_picture:
            avatar_url = student.google_picture

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
            'avatar': avatar_url,
        }
    })


# ─── Current Affairs APIs ───────────────────────────────────────────────────

@api_view(['GET'])
def current_affairs_months(request):
    """
    Returns grouped list of months with MCQ counts for subject 'Current Affairs'
    grouped by year (newest first). Includes per-region counts. Months are taken
    in local time, matching the month detail endpoint.
    """
    from django.db.models.functions import TruncMonth

    rows = (
        _published_current_affairs()
        .annotate(month=TruncMonth('created_at'))
        .values('month', 'current_affairs_category__region')
        .annotate(n=Count('id'))
        .order_by('-month')
    )

    grouped = {}
    for row in rows:
        month = row['month']
        yr = str(month.year)
        m_name = month.strftime('%B')
        entry = grouped.setdefault(yr, {}).setdefault(m_name.lower(), {
            'name': f"{m_name} {yr}",
            'slug': m_name.lower(),
            'count': 0,
            'pak_count': 0,
            'world_count': 0,
            'general_count': 0,
        })
        entry['count'] += row['n']
        region = row['current_affairs_category__region']
        key = {'pakistan': 'pak_count', 'world': 'world_count'}.get(region, 'general_count')
        entry[key] += row['n']

    return Response({yr: list(months.values()) for yr, months in grouped.items()})


def _current_affairs_payload(mcqs, title, region_filter):
    """Group current-affairs MCQs into Pakistan / International / General categories.

    With ?region=pakistan|world only that region's category is returned.
    """
    pk_questions = []
    intl_questions = []
    general_questions = []

    for index, q in enumerate(mcqs.select_related('current_affairs_category').order_by('created_at', 'id'), start=1):
        serialized = _serialize_current_affairs_question(q, index)
        category = q.current_affairs_category
        if category and category.region == CurrentAffairsCategory.Region.PAKISTAN:
            pk_questions.append(serialized)
        elif category and category.region == CurrentAffairsCategory.Region.WORLD:
            intl_questions.append(serialized)
        else:
            general_questions.append(serialized)

    categories = []
    if region_filter == 'pakistan':
        if pk_questions:
            categories.append({'name': 'Pakistan Affairs', 'questions': pk_questions})
    elif region_filter == 'world':
        if intl_questions:
            categories.append({'name': 'International Affairs', 'questions': intl_questions})
    else:
        if intl_questions:
            categories.append({'name': 'International Affairs', 'questions': intl_questions})
        if pk_questions:
            categories.append({'name': 'Pakistan Affairs', 'questions': pk_questions})
        if general_questions:
            categories.append({'name': 'General Current Affairs', 'questions': general_questions})

    return {'title': title, 'categories': categories}


def _published_current_affairs():
    return MCQ.objects.filter(subject__slug='current-affairs', status='published')


@api_view(['GET'])
def current_affairs_detail(request, year, month):
    """
    Returns MCQs for a specific year and month categorized under International/Pakistan Affairs.
    Optional query param: ?region=pakistan|world
    """
    import calendar
    month_names = [name.lower() for name in calendar.month_name]
    if not year.isdigit() or month.lower() not in month_names[1:]:
        return Response({'error': 'Unknown month.'}, status=status.HTTP_404_NOT_FOUND)
    month_num = month_names.index(month.lower())

    mcqs = _published_current_affairs().filter(created_at__year=int(year), created_at__month=month_num)
    title = f"{month.title()} {year} Current Affairs"
    return Response(_current_affairs_payload(mcqs, title, request.query_params.get('region', '').lower()))


@api_view(['GET'])
def current_affairs_daily(request, day):
    """MCQs added on one day (YYYY-MM-DD), grouped like the monthly view."""
    from django.utils.dateparse import parse_date
    try:
        parsed = parse_date(day)
    except ValueError:
        parsed = None
    if not parsed:
        return Response({'error': 'Use a date in YYYY-MM-DD format.'}, status=status.HTTP_400_BAD_REQUEST)

    mcqs = _published_current_affairs().filter(created_at__date=parsed)
    title = f"{parsed:%d %B %Y} Current Affairs"
    return Response(_current_affairs_payload(mcqs, title, request.query_params.get('region', '').lower()))

@api_view(['GET'])
def frontend_mcq_subjects(request):
    """Return subjects that have MCQs, paginated (default 30 per page)."""
    page_num = _query_int(request, 'page', 1)
    page_size = _query_int(request, 'page_size', 30, maximum=100)
    subjects = Subject.objects.annotate(mcq_count=Count('mcqs', filter=Q(mcqs__status='published'))).filter(mcq_count__gt=0).order_by('-mcq_count')
    paginator = Paginator(subjects, page_size)
    page = paginator.get_page(page_num)
    data = [
        {'name': s.name, 'slug': s.slug, 'count': s.mcq_count}
        for s in page.object_list
    ]
    return Response({
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'page': page.number,
        'results': data,
    })

@api_view(['GET'])
def frontend_mcq_sets(request, subject_slug):
    """Return the calculated 'Test Sets' (sets of 20 MCQs) for a given subject."""
    from django.shortcuts import get_object_or_404
    subject = get_object_or_404(Subject, slug=subject_slug)
    total = MCQ.objects.filter(subject=subject, status='published').count()

    if total == 0:
        return Response({'error': 'No published MCQs found for this subject'}, status=status.HTTP_404_NOT_FOUND)

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
def frontend_mcq_subject_questions(request, subject_slug):
    """Return paginated questions for a subject, plus sets info for the sidebar."""
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    page_num = _query_int(request, 'page', 1)
    page_size = 20
    
    mcqs = MCQ.objects.filter(subject=subject, status='published').order_by('id')
    
    paginator = Paginator(mcqs, page_size)
    page_obj = paginator.get_page(page_num)
    
    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    questions_list = []
    for q in page_obj.object_list:
        questions_list.append({
            'id': q.id,
            'question': q.question_text,
            'options': [q.option_a, q.option_b, q.option_c, q.option_d] if q.option_d else [q.option_a, q.option_b, q.option_c],
            'correct': opt_map.get(q.correct_option, 0),
            'explanation': q.explanation
        })
        
    total = paginator.count
    set_size = 20
    num_sets = (total + set_size - 1) // set_size
    sets = []
    for i in range(num_sets):
        start = i * set_size + 1
        end = min((i + 1) * set_size, total)
        sets.append({
            'id': str(i + 1),
            'name': f'Set {i + 1}',
            'range': f'Questions {start}-{end}',
            'count': end - start + 1
        })

    return Response({
        'title': subject.name,
        'slug': subject.slug,
        'total': total,
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'page': page_num,
        'questions': questions_list,
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
    
    mcqs = MCQ.objects.filter(subject=subject, status='published').order_by('id')[offset:offset+set_size]

    if not mcqs:
        return Response({'error': 'Set not found or no published MCQs'}, status=404)

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

def _mock_test_title(job_slug):
    """Jobs link to their mock test by id; show the job title rather than the number."""
    if job_slug.isdigit():
        job = JobListing.objects.filter(pk=int(job_slug)).only('title').first()
        if job:
            return f'{job.title} Mock Test'
    return f'Mock Test ({job_slug.replace("-", " ").title()})'


@api_view(['GET'])
def frontend_mock_test(request, job_slug):
    """Generate a dynamic 100-question mock test based on specific syllabus weightages.

    Predefined configs exist for known job slugs.
    For unknown slugs:
      1. Check query param `?breakdown={"english":20,"math":30,...}` for user-provided weightages.
      2. If no breakdown given, auto-distribute 100 questions equally across all subjects
         that have published MCQs in the database.
    """

    # Predefined mock test configurations (known job slugs)
    mock_configs = {
        'ppsc-patwari': {
            'title': 'PPSC Patwari Mock Test',
            'total': 100,
            'breakdown': {
                'english': 20,
                'general-knowledge': 20,
                'pakistan-studies': 20,
                'islamic-studies': 10,
                'computer-science': 20,
                'mathematics': 10,
            }
        },
        'fpsc-inspector-customs': {
            'title': 'FPSC Inspector Customs Mock Test',
            'total': 100,
            'breakdown': {
                'english': 20,
                'general-knowledge': 20,
                'current-affairs': 20,
                'pakistan-studies': 10,
                'islamic-studies': 10,
                'everyday-science': 20,
            }
        },
        'ppsc-sub-inspector': {
            'title': 'PPSC Sub Inspector Mock Test',
            'total': 100,
            'breakdown': {
                'english': 40,
                'computer-science': 40,
                'general-knowledge': 20,
            }
        },
        'ppsc-assistant': {
            'title': 'PPSC Assistant Mock Test',
            'total': 100,
            'breakdown': {
                'english': 20,
                'pakistan-studies': 10,
                'general-knowledge': 30,
                'islamic-studies': 10,
                'mathematics': 10,
                'computer-science': 20,
            }
        }
    }

    config = mock_configs.get(job_slug)

    if not config:
        # ── Unknown slug: try user-provided breakdown first ──
        user_breakdown = request.query_params.get('breakdown')
        if user_breakdown:
            try:
                parsed = json.loads(user_breakdown)
                if isinstance(parsed, dict) and parsed:
                    breakdown ={str(k): max(0, min(int(v), MAX_TEST_QUESTIONS)) for k, v in parsed.items()}
                    config = {
                        'title': _mock_test_title(job_slug),
                        'total': min(sum(breakdown.values()) or 100, MAX_TEST_QUESTIONS),
                        'breakdown': breakdown,
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass  # fall through to auto-distribution

        # ── Auto-distribute across all subjects with published MCQs ──
        if not config:
            # Find every subject slug that has at least 1 published MCQ
            active_subjects = (
                Subject.objects
                .filter(mcqs__status='published')
                .annotate(mcq_count=Count('mcqs'))
                .filter(mcq_count__gt=0)
                .values_list('slug', flat=True)
                .distinct()
                .order_by('slug')
            )
            subject_slugs = list(active_subjects)

            if not subject_slugs:
                return Response(
                    {'error': 'No subjects with published MCQs found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            total_questions = 100
            count_per_subject = total_questions // len(subject_slugs)
            remainder = total_questions % len(subject_slugs)

            breakdown = {}
            for i, subj_slug in enumerate(subject_slugs):
                breakdown[subj_slug] = count_per_subject + (1 if i < remainder else 0)

            config = {
                'title': _mock_test_title(job_slug),
                'total': total_questions,
                'breakdown': breakdown,
            }

    questions_list = []
    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

    for subj_slug, count in config['breakdown'].items():
        # Fetch up to `count` random questions for this subject
        mcqs = list(MCQ.objects.filter(subject__slug=subj_slug, status='published').order_by('?')[:count])

        for q in mcqs:
            questions_list.append({
                'id': q.id,
                'question': q.question_text,
                'options': [q.option_a, q.option_b, q.option_c, q.option_d] if q.option_d else [q.option_a, q.option_b, q.option_c],
                'correct': opt_map.get(q.correct_option, 0),
                'explanation': q.explanation,
                'subject': subj_slug
            })

    # Shuffle the combined list so subjects are mixed
    random.shuffle(questions_list)

    # Ensure exactly total number of questions if possible (or less if not enough questions in DB)
    questions_list = questions_list[:config['total']]

    return Response({
        'title': config['title'],
        'questions': questions_list
    })

@api_view(['GET'])
def frontend_current_affairs_category_detail(request, slug):
    """Serve questions by DB-configured current-affairs category."""
    category = next(
        (item for item in _current_affairs_categories() if item['slug'] == slug),
        None,
    )
    # Fallback to defaults if DB config doesn't have this slug
    if category is None:
        category = next(
            (item for item in DEFAULT_CURRENT_AFFAIRS_CATEGORIES if item['slug'] == slug),
            None,
        )
    if category is None:
        return Response(
            {'error': 'Current affairs category not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    mcqs = (
        MCQ.objects
        .filter(subject__slug='current-affairs', status='published')
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
    Returns all exams with their latest 5 past papers for the mega-menu hover dropdown.
    Shape:
      [ { exam_name, exam_slug, badge_color, papers: [{title, slug, year, subject_name}] } ]
    """
    exams = Exam.objects.annotate(
        paper_count=Count('past_papers', distinct=True)
    ).filter(paper_count__gt=0).order_by('-paper_count')

    result = []
    for exam in exams:
        papers = (
            PastPaper.objects
            .select_related('subject')
            .filter(exam=exam, status=PastPaper.Status.PUBLISHED)
            .order_by('-year', '-created_at')[:5]
        )
        result.append({
            'exam_name':   exam.name,
            'exam_slug':   exam.slug,
            'badge_color': exam.badge_color,
            'papers': [
                {
                    'title': paper.title,
                    'slug': paper.slug,
                    'year': paper.year,
                    'subject_name': paper.subject.name if paper.subject else '',
                }
                for paper in papers
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
    page_num     = _query_int(request, 'page', 1)
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
    mcqs = paper.mcqs.filter(status='published').order_by('id')
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


def _latin1(text):
    """fpdf core fonts are Latin-1 only; replace anything else instead of crashing."""
    return str(text or '').encode('latin-1', 'replace').decode('latin-1')


@api_view(['GET'])
def frontend_past_paper_pdf(request, slug):
    """Generate and return a PDF of the past paper with all MCQs."""
    from django.shortcuts import get_object_or_404
    from django.http import HttpResponse
    from fpdf import FPDF

    paper = get_object_or_404(
        PastPaper.objects.select_related('exam', 'subject'),
        slug=slug, status=PastPaper.Status.PUBLISHED
    )

    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    labels = ['A', 'B', 'C', 'D']
    mcqs = paper.mcqs.filter(status='published').order_by('id')

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header / Title
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(13, 58, 92)
    pdf.cell(0, 10, _latin1(paper.title), ln=True, align='C')

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(107, 114, 128)
    meta = f"{paper.exam.name}"
    if paper.subject:
        meta += f"  -  {paper.subject.name}"
    if paper.year:
        meta += f"  -  {paper.year}"
    meta += f"  -  {mcqs.count()} Questions"
    pdf.cell(0, 6, _latin1(meta), ln=True, align='C')

    pdf.set_draw_color(29, 158, 117)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y() + 2, 195, pdf.get_y() + 2)
    pdf.ln(8)

    # Questions
    for i, q in enumerate(mcqs, start=1):
        if pdf.get_y() > 250:
            pdf.add_page()

        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(26, 32, 44)
        q_text = f"{i}.  {q.question_text}"
        pdf.multi_cell(0, 6, _latin1(q_text), ln=True)

        options = [q.option_a, q.option_b, q.option_c, q.option_d]
        correct_idx = opt_map.get(q.correct_option, 0)

        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(75, 85, 99)
        for idx, opt in enumerate(options):
            if not opt:
                continue
            label = labels[idx]
            is_correct = idx == correct_idx

            safe_opt = _latin1(opt)

            if is_correct:
                pdf.set_fill_color(225, 245, 238)
                pdf.set_text_color(15, 110, 86)
                pdf.set_font('Helvetica', 'B', 10)
            else:
                pdf.set_fill_color(243, 244, 246)
                pdf.set_text_color(75, 85, 99)
                pdf.set_font('Helvetica', '', 10)

            pdf.cell(8, 6, '', ln=0)
            label_x = pdf.get_x()
            pdf.cell(6, 6, label, border=0, ln=0, align='C', fill=True)
            pdf.set_x(label_x + 8)
            pdf.multi_cell(0, 6, safe_opt, ln=True)

            pdf.set_text_color(75, 85, 99)
            pdf.set_font('Helvetica', '', 10)

        # Correct answer bar
        pdf.set_fill_color(225, 245, 238)
        pdf.set_text_color(15, 110, 86)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(8, 5, '', ln=0)
        pdf.cell(0, 5, f"Correct Answer: {labels[correct_idx]}", ln=True, fill=True)

        # Explanation
        if q.explanation:
            pdf.set_fill_color(255, 251, 235)
            pdf.set_text_color(146, 64, 14)
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(8, 5, '', ln=0)
            safe_exp = _latin1(q.explanation)
            pdf.multi_cell(0, 5, f"Explanation: {safe_exp}", ln=True, fill=True)

        pdf.ln(4)
        pdf.set_text_color(75, 85, 99)

    # Footer
    pdf.set_y(-15)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 10, _latin1(f"Generated by ImtihanHub  -  {paper.exam.name}  -  {paper.title}"), ln=True, align='C')

    filename = f"{paper.slug}-mcqs.pdf"  # slug is ASCII-safe for the header
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['GET'])
def frontend_current_affairs_topics(request):
    """Return DB-configured Current Affairs categories with live MCQ counts."""
    mcqs = MCQ.objects.filter(subject__slug='current-affairs', status='published')

    # Start with DB categories, then merge any missing defaults
    categories = {c['slug']: c for c in _current_affairs_categories()}
    for default in DEFAULT_CURRENT_AFFAIRS_CATEGORIES:
        if default['slug'] not in categories:
            categories[default['slug']] = default

    grouped = {'pakistan': [], 'world': []}
    for category in categories.values():
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
    Returns a paginated list of syllabus entries.
    Query params: exam=<slug>&page=<int>&page_size=<int>
    """
    exam_slug = request.query_params.get('exam', '')
    page_num = _query_int(request, 'page', 1)
    page_size = _query_int(request, 'page_size', 20, maximum=100)
    qs = Syllabus.objects.select_related('exam').order_by('exam__name', 'title')
    if exam_slug:
        qs = qs.filter(exam__slug=exam_slug)

    paginator = Paginator(qs, page_size)
    page = paginator.get_page(page_num)
    data = []
    for s in page.object_list:
        data.append({
            'id':         s.id,
            'title':      s.title,
            'slug':       s.slug,
            'post_name':  s.post_name,
            'bps_grade':  s.bps_grade,
            'exam_name':  s.exam.name,
            'exam_slug':  s.exam.slug,
            'has_pdf':    bool(s.pdf_file),
            'created_at': s.created_at.isoformat(),
        })
    return Response({
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'page': page.number,
        'results': data,
    })


@api_view(['GET'])
def frontend_syllabus_detail(request, slug):
    """Returns one syllabus record including full content and PDF url."""
    from django.shortcuts import get_object_or_404
    s = get_object_or_404(Syllabus.objects.select_related('exam'), slug=slug)
    return Response({
        'id':         s.id,
        'title':      s.title,
        'slug':       s.slug,
        'post_name':  s.post_name,
        'bps_grade':  s.bps_grade,
        'marks':      s.marks,
        'time':       s.time,
        'exam_name':  s.exam.name,
        'exam_slug':  s.exam.slug,
        'content':    s.content,
        'has_pdf':    bool(s.pdf_file),
        'pdf_url':    s.pdf_file.url if s.pdf_file else None,
        'created_at': s.created_at.isoformat(),
    })


@api_view(['POST'])
@throttle_classes([ContactThrottle])
def frontend_contact(request):
    """Accept a contact form submission from the public frontend."""
    serializer = ContactMessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': True, 'message': 'Your message has been received. We\'ll get back to you soon.'}, status=status.HTTP_201_CREATED)
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# ─── Google OAuth ───────────────────────────────────────────────────────────

try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False


class GoogleLoginThrottle(AnonRateThrottle):
    scope = 'google_login'  # own cache key, not shared with the global anon limit
    rate = '10/min'


@api_view(['POST'])
@throttle_classes([GoogleLoginThrottle])
def google_login(request):
    """Verify a Google ID token and return an auth token."""
    if not GOOGLE_AUTH_AVAILABLE:
        return Response(
            {'error': 'Google auth library not installed. Run: pip install google-auth'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    id_token_str = request.data.get('id_token')
    if not id_token_str:
        return Response({'error': 'id_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        return Response(
            {'error': 'GOOGLE_CLIENT_ID is not configured on the server.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=10
        )
    except Exception as e:
        logger.info('Rejected Google token: %s', e)
        return Response({'error': 'Invalid Google token.'}, status=status.HTTP_401_UNAUTHORIZED)

    # Validate issuer
    if idinfo.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        return Response({'error': 'Invalid token issuer.'}, status=status.HTTP_401_UNAUTHORIZED)

    email = (idinfo.get('email') or '').strip()
    if not email:
        return Response({'error': 'Email not provided by Google.'}, status=status.HTTP_400_BAD_REQUEST)
    # Only a Google-verified address may sign in to (or be linked with) an account.
    if idinfo.get('email_verified') not in (True, 'true'):
        return Response({'error': 'Your Google email address is not verified.'}, status=status.HTTP_401_UNAUTHORIZED)

    google_id = idinfo.get('sub')
    full_name = idinfo.get('name', '')
    given_name = idinfo.get('given_name', '')
    family_name = idinfo.get('family_name', '')
    picture = idinfo.get('picture', '')

    # Try to find existing user by email first
    user = User.objects.filter(email__iexact=email).first()

    if user:
        # Update Google ID and picture on the profile if not set
        student, _ = Student.objects.get_or_create(user=user)
        updated_fields = []
        if google_id and not student.google_id:
            student.google_id = google_id
            updated_fields.append('google_id')
        if picture and not student.google_picture:
            student.google_picture = picture
            updated_fields.append('google_picture')
        if updated_fields:
            student.save(update_fields=updated_fields)
    else:
        # Create new user
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=None,  # unusable: Google-only accounts can't log in with a password
            first_name=given_name or (full_name.split(' ')[0] if full_name else ''),
            last_name=family_name or (' '.join(full_name.split(' ')[1:]) if full_name else ''),
        )
        Student.objects.create(
            user=user,
            google_id=google_id or '',
            google_picture=picture or ''
        )

    token, _ = Token.objects.get_or_create(user=user)
    student = getattr(user, 'student_profile', None)

    # Prefer uploaded avatar, then Google picture, then null
    avatar_url = None
    if student:
        if student.avatar:
            avatar_url = student.avatar.url
        elif student.google_picture:
            avatar_url = student.google_picture

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
            'avatar': avatar_url,
        }
    })


# ─── User Dashboard APIs ────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_dashboard_stats(request):
    """Return comprehensive stats for the authenticated user's dashboard."""
    user = request.user
    student = getattr(user, 'student_profile', None)
    today = timezone.localdate()
    # Daily counters belong to last_practice_date; on any other day they read as zero.
    mcqs_today = student.mcqs_today if student and student.last_practice_date == today else 0

    total_tests = TestResult.objects.filter(student=user).count()
    avg_score = TestResult.objects.filter(student=user).aggregate(
        avg=Avg('score_percent')
    )['avg'] or 0
    bookmarks_count = Bookmark.objects.filter(user=user).count()
    total_mcqs = TestResult.objects.filter(student=user).aggregate(
        total=Sum('total_questions')
    )['total'] or 0

    streak = user_streak(user, today)

    # Subject-wise performance for recommendations
    subject_scores = {}
    for tr in TestResult.objects.filter(student=user).select_related('subject'):
        if tr.subject:
            slug = tr.subject.slug
            if slug not in subject_scores:
                subject_scores[slug] = {
                    'name': tr.subject.name,
                    'slug': slug,
                    'total_score': 0,
                    'count': 0,
                }
            subject_scores[slug]['total_score'] += float(tr.score_percent)
            subject_scores[slug]['count'] += 1

    recommendations = sorted(
        [
            {
                'name': v['name'],
                'slug': v['slug'],
                'avg_score': round(v['total_score'] / v['count'], 1),
            }
            for v in subject_scores.values()
        ],
        key=lambda x: x['avg_score']
    )[:3]

    return Response({
        'username': user.first_name or user.username,
        'tests_attempted': total_tests,
        'average_score': round(float(avg_score), 1),
        'bookmarks_count': bookmarks_count,
        'total_mcqs_practiced': total_mcqs,
        'streak_days': streak,
        'daily_goal': student.daily_goal if student else 20,
        'mcqs_today': mcqs_today,
        'recommendations': recommendations,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_recent_tests(request):
    """Return paginated, filterable test results with summary stats."""
    user = request.user
    qs = TestResult.objects.filter(student=user).select_related('exam', 'subject')

    # Filters
    exam = request.query_params.get('exam', '')
    subject = request.query_params.get('subject', '')
    date_from = request.query_params.get('date_from', '')
    date_to = request.query_params.get('date_to', '')
    score_min = request.query_params.get('score_min', '')
    score_max = request.query_params.get('score_max', '')

    if exam:
        qs = qs.filter(exam__slug__iexact=exam)
    if subject:
        qs = qs.filter(subject__slug__iexact=subject)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if score_min:
        try:
            qs = qs.filter(score_percent__gte=float(score_min))
        except ValueError:
            pass
    if score_max:
        try:
            qs = qs.filter(score_percent__lte=float(score_max))
        except ValueError:
            pass

    qs = qs.order_by('-created_at')

    # Summary stats (on filtered set)
    total = qs.count()
    avg = qs.aggregate(avg=models.Avg('score_percent'))['avg'] or 0
    best = qs.aggregate(best=models.Max('score_percent'))['best'] or 0
    worst = qs.aggregate(worst=models.Min('score_percent'))['worst'] or 0

    # Pagination
    page_size = _query_int(request, 'page_size', 10, maximum=100)
    page_num = _query_int(request, 'page', 1)
    from django.core.paginator import Paginator
    paginator = Paginator(qs, page_size)
    page = paginator.get_page(page_num)

    serializer = TestResultSerializer(page.object_list, many=True)

    return Response({
        'total': total,
        'num_pages': paginator.num_pages,
        'page': page.number,
        'has_next': page.has_next(),
        'has_prev': page.has_previous(),
        'summary': {
            'total_tests': total,
            'average_score': round(float(avg), 1),
            'best_score': round(float(best), 1),
            'worst_score': round(float(worst), 1),
        },
        'tests': serializer.data,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def quick_practice(request):
    """Return 20 random published MCQs for quick practice."""
    mcqs = MCQ.objects.filter(status='published').select_related('exam', 'subject').order_by('?')[:20]
    opt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    questions = []
    for q in mcqs:
        questions.append({
            'id': q.id,
            'question': q.question_text,
            'options': [q.option_a, q.option_b, q.option_c, q.option_d] if q.option_d else [q.option_a, q.option_b, q.option_c],
            'correct': opt_map.get(q.correct_option, 0),
            'explanation': q.explanation,
            'subject': q.subject.name if q.subject else '',
            'exam': q.exam.name if q.exam else '',
        })
    return Response({'questions': questions, 'title': 'Quick Practice (20 Questions)'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_progress(request):
    """Return detailed progress data for charts and analytics."""
    user = request.user
    today = timezone.localdate()
    last_30 = today - timezone.timedelta(days=30)

    # Score over last 30 days
    daily_scores = {}
    for tr in TestResult.objects.filter(student=user, created_at__date__gte=last_30):
        d = str(tr.created_at.date())
        daily_scores[d] = max(daily_scores.get(d, 0), float(tr.score_percent))

    scores_over_time = [
        {'date': d, 'score': round(daily_scores[d], 1)}
        for d in sorted(daily_scores.keys())
    ]

    # Subject performance
    subject_perf = {}
    for tr in TestResult.objects.filter(student=user).select_related('subject'):
        if not tr.subject:
            continue
        slug = tr.subject.slug
        if slug not in subject_perf:
            subject_perf[slug] = {
                'name': tr.subject.name,
                'slug': slug,
                'total_questions': 0,
                'correct_answers': 0,
                'tests': 0,
                'total_score': 0,
                'test_scores': [],
            }
        subject_perf[slug]['total_questions'] += tr.total_questions
        subject_perf[slug]['correct_answers'] += tr.correct_answers
        subject_perf[slug]['tests'] += 1
        subject_perf[slug]['total_score'] += float(tr.score_percent)
        subject_perf[slug]['test_scores'].append(float(tr.score_percent))

    subject_stats = []
    for v in subject_perf.values():
        accuracy = round((v['correct_answers'] / v['total_questions']) * 100, 1) if v['total_questions'] > 0 else 0
        avg_score = round(v['total_score'] / v['tests'], 1) if v['tests'] > 0 else 0

        # Trend: compare first half vs second half of last 5 tests
        scores = v['test_scores']
        trend = 'neutral'
        if len(scores) >= 3:
            mid = len(scores) // 2
            early = sum(scores[:mid]) / mid
            recent = sum(scores[-mid:]) / mid
            if recent > early + 3:
                trend = 'improving'
            elif recent < early - 3:
                trend = 'declining'

        subject_stats.append({
            'name': v['name'],
            'slug': v['slug'],
            'accuracy': accuracy,
            'avg_score': avg_score,
            'tests': v['tests'],
            'total_questions': v['total_questions'],
            'correct_answers': v['correct_answers'],
            'wrong_answers': v['total_questions'] - v['correct_answers'],
            'trend': trend,
        })

    subject_stats_sorted = sorted(subject_stats, key=lambda x: x['accuracy'])
    weak_subjects = subject_stats_sorted[:3]
    strong_subjects = sorted(subject_stats, key=lambda x: x['accuracy'], reverse=True)[:3]

    # Overall accuracy from ALL tests (including those without a subject)
    all_results = TestResult.objects.filter(student=user)
    total_q = all_results.aggregate(total=Sum('total_questions'))['total'] or 0
    total_c = all_results.aggregate(total=Sum('correct_answers'))['total'] or 0
    overall_accuracy = round((total_c / total_q) * 100, 1) if total_q > 0 else 0

    # Study time this week vs last week
    week_start = today - timezone.timedelta(days=today.weekday())
    last_week_start = week_start - timezone.timedelta(days=7)
    last_week_end = week_start - timezone.timedelta(days=1)

    this_week_time = TestResult.objects.filter(
        student=user, created_at__date__gte=week_start
    ).aggregate(total=models.Sum('time_taken_seconds'))['total'] or 0

    last_week_time = TestResult.objects.filter(
        student=user, created_at__date__gte=last_week_start, created_at__date__lte=last_week_end
    ).aggregate(total=models.Sum('time_taken_seconds'))['total'] or 0

    return Response({
        'scores_over_time': scores_over_time,
        'subject_performance': subject_stats,
        'weak_subjects': weak_subjects,
        'strong_subjects': strong_subjects,
        'overall_accuracy': overall_accuracy,
        'total_questions': total_q,
        'total_correct': total_c,
        'study_time_this_week': this_week_time,
        'study_time_last_week': last_week_time,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_gamification(request):
    """Return streak, XP, achievements, and leaderboard data."""
    user = request.user
    student = getattr(user, 'student_profile', None)
    today = timezone.localdate()

    # Daily practice heatmap (last 90 days)
    logs = DailyPracticeLog.objects.filter(
        user=user, date__gte=today - timezone.timedelta(days=90)
    ).order_by('date')
    heatmap = [{'date': str(l.date), 'count': l.mcqs_answered} for l in logs]

    # All achievements with unlock status
    user_achievements = {
        ua.achievement.slug: ua.unlocked_at
        for ua in UserAchievement.objects.filter(user=user).select_related('achievement')
    }
    achievements = []
    for ach in Achievement.objects.filter(is_active=True):
        achievements.append({
            'id': ach.id,
            'slug': ach.slug,
            'name': ach.name,
            'description': ach.description,
            'icon': ach.icon,
            'xp_reward': ach.xp_reward,
            'condition_type': ach.condition_type,
            'condition_value': ach.condition_value,
            'unlocked': ach.slug in user_achievements,
            'unlocked_at': user_achievements.get(ach.slug),
        })

    # Leaderboard: rank by XP this week
    week_start = today - timezone.timedelta(days=today.weekday())
    weekly_xp = DailyPracticeLog.objects.filter(
        date__gte=week_start
    ).values('user').annotate(total_xp=models.Sum('xp_earned')).order_by('-total_xp')

    user_rank = None
    total_students = weekly_xp.count()
    for idx, entry in enumerate(weekly_xp, start=1):
        if entry['user'] == user.id:
            user_rank = idx
            break

    # Level thresholds (XP is cumulative; the level is derived from it)
    LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
    xp = student.xp_points if student else 0
    level = level_for_xp(xp)
    level_name = LEVELS[min(level - 1, len(LEVELS) - 1)]
    next_level_xp = level_threshold(level)

    streak = user_streak(user, today)

    return Response({
        'streak_days': streak,
        'xp_points': xp,
        'level': level,
        'level_name': level_name,
        'next_level_xp': next_level_xp,
        'xp_to_next': max(0, next_level_xp - xp),
        'rank': user_rank,
        'total_leaderboard': total_students,
        'heatmap': heatmap,
        'achievements': achievements,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_achievements(request):
    """Return all achievements with locked/unlocked status for the current user."""
    user = request.user
    user_achievements_map = {
        ua.achievement.slug: ua.unlocked_at
        for ua in UserAchievement.objects.filter(user=user).select_related('achievement')
    }
    all_achievements = []
    for ach in Achievement.objects.filter(is_active=True):
        all_achievements.append({
            'id': ach.id,
            'slug': ach.slug,
            'name': ach.name,
            'description': ach.description,
            'icon': ach.icon,
            'xp_reward': ach.xp_reward,
            'condition_type': ach.condition_type,
            'condition_label': ach.get_condition_type_display(),
            'condition_value': ach.condition_value,
            'unlocked': ach.slug in user_achievements_map,
            'unlocked_at': user_achievements_map.get(ach.slug),
        })
    return Response({'achievements': all_achievements})


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_bookmarks(request):
    """List or create bookmarks for the authenticated user."""
    if request.method == 'GET':
        bookmarks = Bookmark.objects.filter(user=request.user).select_related('mcq__exam', 'mcq__subject')
        serializer = BookmarkSerializer(bookmarks, many=True)
        return Response(serializer.data)

    # POST
    mcq_id = request.data.get('mcq_id')
    if not mcq_id:
        return Response({'error': 'mcq_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    mcq = MCQ.objects.filter(id=mcq_id).first()
    if not mcq:
        return Response({'error': 'MCQ not found.'}, status=status.HTTP_404_NOT_FOUND)

    bookmark, created = Bookmark.objects.get_or_create(user=request.user, mcq=mcq)
    if not created:
        return Response({'message': 'Already bookmarked.'}, status=status.HTTP_200_OK)

    serializer = BookmarkSerializer(bookmark)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_bookmark(request, bookmark_id):
    """Delete a bookmark for the authenticated user."""
    bookmark = Bookmark.objects.filter(id=bookmark_id, user=request.user).first()
    if not bookmark:
        return Response({'error': 'Bookmark not found.'}, status=status.HTTP_404_NOT_FOUND)
    bookmark.delete()
    return Response({'message': 'Bookmark removed.'})


class SubscribeThrottle(AnonRateThrottle):
    scope = 'subscribe'  # own cache key, not shared with the global anon limit
    rate = '5/hour'

@api_view(['POST'])
@throttle_classes([SubscribeThrottle])
def subscribe_email(request):
    """Subscribe an email for job alerts and newsletter."""
    email = request.data.get('email', '').strip().lower()
    name = request.data.get('name', '').strip()

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email(email)
    except ValidationError:
        return Response({'error': 'Invalid email address.'}, status=status.HTTP_400_BAD_REQUEST)

    sub, created = EmailSubscription.objects.get_or_create(email=email, defaults={'name': name})
    if not created:
        return Response({'message': 'You are already subscribed.'}, status=status.HTTP_200_OK)

    return Response({'message': 'Subscribed successfully!'}, status=status.HTTP_201_CREATED)


logger = logging.getLogger(__name__)

MAX_TEST_QUESTIONS = 200
MAX_TEST_SECONDS = 6 * 60 * 60


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query_int(request, name, default, minimum=1, maximum=None):
    """Integer query param clamped to [minimum, maximum]; bad input falls back to default."""
    value = _int_or_none(request.query_params.get(name))
    if value is None:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def submit_test(request):
    """Submit a completed test and save results + per-question answers.

    Correctness and score are computed here from the stored MCQs; the client's
    own is_correct / score fields are ignored. XP, streaks and daily counters
    are awarded by the TestResult post_save signal.
    """
    data = request.data
    user = request.user

    answers_data = data.get('answers')
    if not isinstance(answers_data, list) or not answers_data:
        return Response({'error': 'A test must include at least one answer.'}, status=status.HTTP_400_BAD_REQUEST)

    # One entry per question; ignore repeats and anything beyond a full-length mock.
    unique_answers = {}
    for ans in answers_data:
        if not isinstance(ans, dict):
            continue
        try:
            question_id = int(ans.get('question_id'))
        except (TypeError, ValueError):
            continue
        unique_answers.setdefault(question_id, ans)
    answers = list(unique_answers.items())[:MAX_TEST_QUESTIONS]
    if not answers:
        return Response({'error': 'No valid answers in submission.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        time_taken_seconds = int(data.get('time_taken_seconds') or 0)
    except (ValueError, TypeError):
        time_taken_seconds = 0
    time_taken_seconds = min(max(time_taken_seconds, 0), MAX_TEST_SECONDS)

    mcqs = MCQ.objects.in_bulk([question_id for question_id, _ in answers])

    rows = []
    correct_answers = wrong_answers = 0
    for question_id, ans in answers:
        selected = str(ans.get('selected_option') or '').strip().upper()[:1]
        if selected not in ('A', 'B', 'C', 'D'):
            selected = ''
        mcq = mcqs.get(question_id)
        if mcq:
            question_text, explanation = mcq.question_text, mcq.explanation
            options = [mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d]
            correct_option = mcq.correct_option
            is_correct = bool(selected) and selected == correct_option
        else:
            # Unknown question: keep the text for the review page, but it can't score.
            question_text = str(ans.get('question_text') or '')
            explanation = str(ans.get('explanation') or '')
            options = [str(ans.get(f'option_{key}') or '') for key in 'abcd']
            correct_option = str(ans.get('correct_option') or '')[:1].upper()
            is_correct = False
        if is_correct:
            correct_answers += 1
        elif selected:
            wrong_answers += 1
        rows.append(TestAnswer(
            question_id=question_id,
            question_text=question_text,
            option_a=options[0], option_b=options[1], option_c=options[2], option_d=options[3],
            correct_option=correct_option,
            selected_option=selected,
            explanation=explanation,
            is_correct=is_correct,
        ))

    total_questions = len(rows)
    score_percent = round(correct_answers * 100 / total_questions, 2)

    def single_value(ids):
        ids = set(ids)
        return ids.pop() if len(ids) == 1 else None

    exam_id, subject_id = _int_or_none(data.get('exam_id')), _int_or_none(data.get('subject_id'))
    exam = Exam.objects.filter(id=exam_id).first() if exam_id else None
    subject = Subject.objects.filter(id=subject_id).first() if subject_id else None
    if exam is None:
        exam_id = single_value(m.exam_id for m in mcqs.values())
        exam = Exam.objects.filter(id=exam_id).first() if exam_id else None
    if subject is None:
        subject_id = single_value(m.subject_id for m in mcqs.values())
        subject = Subject.objects.filter(id=subject_id).first() if subject_id else None

    try:
        with transaction.atomic():
            test_result = TestResult.objects.create(
                student=user,
                exam=exam,
                subject=subject,
                total_questions=total_questions,
                correct_answers=correct_answers,
                wrong_answers=wrong_answers,
                score_percent=score_percent,
                time_taken_seconds=time_taken_seconds,
            )
            for row in rows:
                row.test_result = test_result
            TestAnswer.objects.bulk_create(rows)

        logger.info(f"Test submitted: id={test_result.id} user={user.id} questions={total_questions} score={score_percent}%")
        return Response({
            'test_id': test_result.id,
            'message': 'Test submitted successfully.',
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'score_percent': score_percent,
        })
    except Exception as e:
        logger.exception(f"Test submission failed for user {user.id}: {e}")
        return Response({'error': 'Failed to save test result. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def test_detail(request, test_id):
    """Return a single test result with all question answers."""
    test = TestResult.objects.filter(id=test_id, student=request.user).select_related('exam', 'subject').prefetch_related('answers').first()
    if not test:
        return Response({'error': 'Test not found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = TestResultDetailSerializer(test)
    return Response(serializer.data)


@api_view(['GET'])
def leaderboard(request):
    """Return leaderboard rankings. Supports period (weekly, monthly, all_time) and board filter."""
    period = request.query_params.get('period', 'weekly')
    board = request.query_params.get('board', '')
    today = timezone.localdate()

    if period == 'weekly':
        start = today - timezone.timedelta(days=today.weekday())
    elif period == 'monthly':
        start = today.replace(day=1)
    else:
        start = None

    # Tests in scope give tests taken / average score for everyone listed.
    qs = TestResult.objects.all()
    if board:
        qs = qs.filter(exam__slug__iexact=board)
    if start:
        qs = qs.filter(created_at__date__gte=start)
    stats = {
        row['student_id']: row
        for row in qs.values('student_id').annotate(
            tests_taken=Count('id'), avg_score=Avg('score_percent'), correct=Sum('correct_answers'),
        )
    }

    # One XP source per view, so the ranking and the displayed XP always agree:
    # board views count that board's tests only; period views use the practice log
    # (which records every XP award); all-time uses each student's total XP.
    if board:
        xp_map = {
            uid: (row['correct'] or 0) * XP_PER_CORRECT + row['tests_taken'] * XP_PER_TEST
            for uid, row in stats.items()
        }
    elif start:
        xp_map = dict(
            DailyPracticeLog.objects.filter(date__gte=start)
            .values('user_id').annotate(total=Sum('xp_earned')).values_list('user_id', 'total')
        )
    else:
        xp_map = dict(Student.objects.filter(xp_points__gt=0).values_list('user_id', 'xp_points'))

    def sort_key(uid):
        row = stats.get(uid, {})
        return (-(xp_map.get(uid) or 0), -float(row.get('avg_score') or 0), -row.get('tests_taken', 0), uid)

    ranked_ids = sorted(
        (uid for uid in set(xp_map) | set(stats) if xp_map.get(uid) or uid in stats),
        key=sort_key,
    )
    top_ids = ranked_ids[:50]
    current_id = request.user.id if request.user.is_authenticated else None
    users = User.objects.select_related('student_profile').in_bulk(top_ids + ([current_id] if current_id else []))

    def entry(rank, uid):
        user = users[uid]
        row = stats.get(uid, {})
        student = getattr(user, 'student_profile', None)
        return {
            'rank': rank,
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'city': (student.city if student and student.city else 'Pakistan'),
            'xp_points': xp_map.get(uid) or 0,
            'tests_taken': row.get('tests_taken', 0),
            'avg_score': round(float(row.get('avg_score') or 0), 1),
        }

    result = [entry(idx, uid) for idx, uid in enumerate(top_ids, start=1) if uid in users]

    # The signed-in user's own position (null when they have no activity in scope)
    current_user = None
    if current_id and current_id in ranked_ids:
        current_user = entry(ranked_ids.index(current_id) + 1, current_id)

    return Response({
        'period': period,
        'board': board,
        'leaderboard': result,
        'user_rank': current_user,
    })


@api_view(['GET', 'PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update user profile."""
    user = request.user
    student, _ = Student.objects.get_or_create(user=user)

    if request.method == 'GET':
        # Stats
        total_mcqs = TestResult.objects.filter(student=user).aggregate(
            total=models.Sum('total_questions')
        )['total'] or 0
        tests_taken = TestResult.objects.filter(student=user).count()
        avg_score = TestResult.objects.filter(student=user).aggregate(
            avg=models.Avg('score_percent')
        )['avg'] or 0

        serializer = UserProfileSerializer(student)
        data = serializer.data
        data['stats'] = {
            'total_mcqs': total_mcqs,
            'tests_taken': tests_taken,
            'average_score': round(float(avg_score), 1),
        }
        return Response(data)

    # PUT — update profile
    # Handle avatar upload
    avatar = request.FILES.get('avatar')
    data = request.data.copy()
    if avatar:
        student.avatar = avatar
        student.save()
        data.pop('avatar', None)

    serializer = UserProfileSerializer(student, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change the user's password (or set a first one for Google-only accounts).

    The auth token is rotated so other devices are signed out; the new token
    is returned for the current client.
    """
    user = request.user
    current = request.data.get('current_password', '')
    new_pass = request.data.get('new_password', '')
    confirm = request.data.get('confirm_password', '')

    if user.has_usable_password() and not user.check_password(current):
        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

    if new_pass != confirm:
        return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    password_error = _password_error(new_pass, user)
    if password_error:
        return Response({'error': password_error}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_pass)
    user.save(update_fields=['password'])
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({'message': 'Password changed successfully.', 'token': token.key})


def _user_uploaded_files(user):
    """Every stored file belonging to `user` (avatar, job profile, documents, payment proofs)."""
    candidates = []
    student = getattr(user, 'student_profile', None)
    if student:
        candidates.append(student.avatar)
    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        candidates.append(profile.profile_photo)
    candidates += [e.certificate_file for e in user.educations.all()]
    candidates += [e.experience_letter for e in user.experiences.all()]
    candidates += [d.file for d in user.job_documents.all()]
    subscription = AISubscription.objects.filter(user=user).first()
    if subscription:
        candidates.append(subscription.payment_screenshot)
    for req in user.application_requests.all():
        candidates += [req.payment_screenshot, req.submission_screenshot]
    return [f for f in candidates if f]


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """Delete user account and all related data."""
    user = request.user
    password = request.data.get('password', '')

    if user.has_usable_password():
        if not user.check_password(password):
            return Response({'error': 'Password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
    elif request.data.get('confirm_text', '').strip().upper() != 'DELETE':
        return Response({'error': 'Type DELETE to confirm.'}, status=status.HTTP_400_BAD_REQUEST)

    # Rows cascade with the user, but Django leaves files on disk; remove them too.
    files = _user_uploaded_files(user)
    user.delete()
    for f in files:
        try:
            f.storage.delete(f.name)
        except Exception:
            logger.warning('Could not delete file %s for removed user', f.name)
    return Response({'message': 'Account deleted successfully.'})


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_goals(request):
    """Get or update daily goal settings and return weekly progress."""
    user = request.user
    student, _ = Student.objects.get_or_create(user=user)
    today = timezone.localdate()

    if request.method == 'POST':
        daily_goal = request.data.get('daily_goal')
        daily_test_goal = request.data.get('daily_test_goal')
        reminder_time = request.data.get('reminder_time')

        daily_goal, daily_test_goal = _int_or_none(daily_goal), _int_or_none(daily_test_goal)
        if daily_goal is not None:
            student.daily_goal = max(10, min(100, daily_goal))
        if daily_test_goal is not None:
            student.daily_test_goal = max(0, min(3, daily_test_goal))
        if reminder_time:
            from django.utils.dateparse import parse_time
            parsed = parse_time(reminder_time)
            if parsed:
                student.reminder_time = parsed
        student.save()

    # Weekly summary (Mon-Sun)
    week_start = today - timezone.timedelta(days=today.weekday())
    week_logs = DailyPracticeLog.objects.filter(
        user=user, date__gte=week_start, date__lte=today
    )
    weekly_met = 0
    weekly_days = []
    for i in range(7):
        d = week_start + timezone.timedelta(days=i)
        log = week_logs.filter(date=d).first()
        mcqs = log.mcqs_answered if log else 0
        tests = log.tests_completed if log else 0
        met = mcqs >= student.daily_goal and tests >= student.daily_test_goal
        if met:
            weekly_met += 1
        weekly_days.append({
            'date': str(d),
            'day': d.strftime('%a'),
            'met': met,
            'mcqs': mcqs,
            'tests': tests,
        })

    # Streak protection warning: a live streak that today's practice hasn't extended yet
    practiced_today = student.last_practice_date == today
    streak_days = user_streak(user, today)
    streak_at_risk = streak_days > 0 and not practiced_today

    return Response({
        'daily_goal': student.daily_goal,
        'daily_test_goal': student.daily_test_goal,
        'reminder_time': str(student.reminder_time) if student.reminder_time else None,
        'mcqs_today': student.mcqs_today if practiced_today else 0,
        'tests_today': student.tests_today if practiced_today else 0,
        'streak_days': streak_days,
        'streak_at_risk': streak_at_risk,
        'weekly_summary': {
            'days_met': weekly_met,
            'total_days': len([d for d in weekly_days if d['date'] <= str(today)]),
            'days': weekly_days,
        },
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """Return notifications for the authenticated user."""
    user = request.user
    unread_only = request.query_params.get('unread', 'false').lower() == 'true'
    qs = Notification.objects.filter(user=user)
    if unread_only:
        qs = qs.filter(is_read=False)
    notifications = qs[:50]
    serializer = NotificationSerializer(notifications, many=True)
    unread_count = Notification.objects.filter(user=user, is_read=False).count()
    return Response({
        'notifications': serializer.data,
        'unread_count': unread_count,
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark notifications as read. Pass notification_ids array, or empty to mark all."""
    user = request.user
    ids = request.data.get('notification_ids', [])
    if ids:
        Notification.objects.filter(user=user, id__in=ids).update(is_read=True)
    else:
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    return Response({'message': 'Notifications marked as read.'})


@api_view(['GET'])
def posts_list(request):
    """List published posts with filters, search, and pagination."""
    qs = Post.objects.filter(status=Post.Status.PUBLISHED).select_related('category', 'author').prefetch_related('tags')

    # Filters
    post_type = request.query_params.get('type')
    if post_type:
        qs = qs.filter(post_type=post_type)

    category_slug = request.query_params.get('category')
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    tag_slug = request.query_params.get('tag')
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            models.Q(title__icontains=search) |
            models.Q(excerpt__icontains=search) |
            models.Q(content__icontains=search)
        )

    # Pagination
    page = max(1, _int_or_none(request.query_params.get('page')) or 1)
    per_page = min(100, max(1, _int_or_none(request.query_params.get('per_page')) or 10))
    total = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    posts = qs[start:end]

    serializer = PostListSerializer(posts, many=True)
    return Response({
        'posts': serializer.data,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': (total + per_page - 1) // per_page,
    })


@api_view(['GET'])
def post_detail(request, slug):
    """Single post detail + increment view count."""
    post = Post.objects.filter(slug=slug, status=Post.Status.PUBLISHED).select_related('category', 'author').prefetch_related('tags').first()
    if not post:
        return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Increment view count atomically (concurrent requests must not lose increments)
    Post.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)
    post.views_count += 1

    serializer = PostDetailSerializer(post)
    return Response(serializer.data)


@api_view(['GET'])
def posts_featured(request):
    """Return featured posts for homepage."""
    posts = Post.objects.filter(
        status=Post.Status.PUBLISHED,
        is_featured=True
    ).select_related('category', 'author').prefetch_related('tags')[:6]
    serializer = PostListSerializer(posts, many=True)
    return Response({'posts': serializer.data})


@api_view(['GET'])
def categories_list(request):
    """All categories with published post count."""
    categories = Category.objects.annotate(
        published_count=Count('posts', filter=models.Q(posts__status=Post.Status.PUBLISHED))
    )
    serializer = CategorySerializer(categories, many=True)
    return Response({'categories': serializer.data})


@api_view(['GET'])
def posts_related(request, slug):
    """Return 4 related posts by same category, excluding the current post."""
    post = Post.objects.filter(slug=slug, status=Post.Status.PUBLISHED).first()
    if not post:
        return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

    related = Post.objects.filter(
        status=Post.Status.PUBLISHED,
        category=post.category
    ).exclude(id=post.id).select_related('category', 'author').prefetch_related('tags')[:4]
    serializer = PostListSerializer(related, many=True)
    return Response({'posts': serializer.data})


@api_view(['GET'])
def post_comments(request, slug):
    """Return approved comments for a post."""
    post = Post.objects.filter(slug=slug, status=Post.Status.PUBLISHED).first()
    if not post:
        return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
    comments = Comment.objects.filter(post=post, is_approved=True).order_by('-created_at')
    serializer = CommentSerializer(comments, many=True)
    return Response({'comments': serializer.data})


class CommentThrottle(AnonRateThrottle):
    scope = 'comment'  # own cache key, not shared with the global anon limit
    rate = '5/min'


@api_view(['POST'])
@throttle_classes([CommentThrottle])
def create_comment(request, slug):
    """Submit a comment for moderation."""
    post = Post.objects.filter(slug=slug, status=Post.Status.PUBLISHED).first()
    if not post:
        return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(post=post)
        return Response(
            {'message': 'Comment submitted for approval.'},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@throttle_classes([SubscribeThrottle])
def news_subscribe(request):
    """Subscribe email to exam news alerts with board preferences."""
    email = request.data.get('email', '').strip().lower()
    board_ids = request.data.get('boards', [])

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email(email)
    except ValidationError:
        return Response({'error': 'Invalid email address.'}, status=status.HTTP_400_BAD_REQUEST)

    # Deactivate any existing active subscription with same email
    NewsSubscriber.objects.filter(email=email, is_active=True).update(is_active=False)

    sub = NewsSubscriber.objects.create(email=email, is_active=True)
    if board_ids:
        valid_boards = Exam.objects.filter(id__in=board_ids)
        sub.boards.set(valid_boards)

    return Response({
        'message': 'Subscribed successfully!',
        'unsubscribe_url': request.build_absolute_uri(f'/api/unsubscribe/{sub.unsubscribe_token}/'),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def news_unsubscribe(request, token):
    """Unsubscribe using unique token."""
    sub = NewsSubscriber.objects.filter(unsubscribe_token=token, is_active=True).first()
    if not sub:
        return Response({'error': 'Invalid or expired unsubscribe link.'}, status=status.HTTP_404_NOT_FOUND)
    sub.is_active = False
    sub.save(update_fields=['is_active'])
    return Response({'message': 'You have been unsubscribed successfully.'})


@api_view(['GET'])
def global_search(request):
    """Search across MCQs, News, and Blog posts."""
    query = request.query_params.get('q', '').strip()
    result_type = request.query_params.get('type', 'all')

    if not query or len(query) < 2:
        return Response({
            'query': query,
            'mcqs': [],
            'news': [],
            'blog': [],
            'total': 0,
            'counts': {'mcqs': 0, 'news': 0, 'blog': 0},
        })

    limit = 20
    counts = {'mcqs': 0, 'news': 0, 'blog': 0}
    results = {'mcqs': [], 'news': [], 'blog': []}

    # Search MCQs
    if result_type in ('all', 'mcqs'):
        mcq_qs = MCQ.objects.filter(
            status=MCQ.Status.PUBLISHED,
            question_text__icontains=query
        ).select_related('exam', 'subject')[:limit]
        counts['mcqs'] = MCQ.objects.filter(
            status=MCQ.Status.PUBLISHED,
            question_text__icontains=query
        ).count()
        results['mcqs'] = [
            {
                'id': m.id,
                'type': 'mcq',
                'question': m.question_text[:200],
                'exam': m.exam.name if m.exam else None,
                'subject': m.subject.name if m.subject else None,
                'correct_option': m.correct_option,
            }
            for m in mcq_qs
        ]

    # Search News posts
    if result_type in ('all', 'news'):
        news_qs = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            post_type=Post.PostType.NEWS,
        ).filter(
            Q(title__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(content__icontains=query)
        ).select_related('category', 'author')[:limit]
        counts['news'] = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            post_type=Post.PostType.NEWS,
        ).filter(
            Q(title__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(content__icontains=query)
        ).count()
        results['news'] = [
            {
                'id': p.id,
                'type': 'news',
                'title': p.title,
                'slug': p.slug,
                'excerpt': (p.excerpt or p.title)[:150],
                'thumbnail_url': p.thumbnail.url if p.thumbnail else None,
                'category': p.category.name if p.category else None,
                'category_color': p.category.color if p.category else None,
                'published_at': p.published_at or p.created_at,
            }
            for p in news_qs
        ]

    # Search Blog posts
    if result_type in ('all', 'blog'):
        blog_qs = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            post_type=Post.PostType.BLOG,
        ).filter(
            Q(title__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(content__icontains=query)
        ).select_related('category', 'author')[:limit]
        counts['blog'] = Post.objects.filter(
            status=Post.Status.PUBLISHED,
            post_type=Post.PostType.BLOG,
        ).filter(
            Q(title__icontains=query) |
            Q(excerpt__icontains=query) |
            Q(content__icontains=query)
        ).count()
        results['blog'] = [
            {
                'id': p.id,
                'type': 'blog',
                'title': p.title,
                'slug': p.slug,
                'excerpt': (p.excerpt or p.title)[:150],
                'thumbnail_url': p.thumbnail.url if p.thumbnail else None,
                'category': p.category.name if p.category else None,
                'category_color': p.category.color if p.category else None,
                'published_at': p.published_at or p.created_at,
            }
            for p in blog_qs
        ]

    return Response({
        'query': query,
        'counts': counts,
        'total': counts['mcqs'] + counts['news'] + counts['blog'],
        **results,
    })


class QuickPostThrottle(AnonRateThrottle):
    scope = 'quick_post'  # limits guessing of the shared secret
    rate = '20/min'


def _quick_post_authorized(request):
    """Constant-time check of the X-Admin-Token header; disabled when no secret is configured."""
    expected = settings.QUICK_POST_SECRET
    supplied = request.headers.get('X-Admin-Token', '')
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


@api_view(['POST'])
@throttle_classes([QuickPostThrottle])
def quick_post(request):
    """Create a post quickly from mobile. Requires admin token header."""
    if not _quick_post_authorized(request):
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category_id = data.get('category_id')
    post_type = data.get('type', 'news')
    post_status = data.get('status', 'draft')
    excerpt = data.get('excerpt', '').strip()
    tag_ids = data.get('tags', [])
    is_featured = data.get('is_featured', False)

    if not title:
        return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not content:
        return Response({'error': 'Content is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not category_id:
        return Response({'error': 'Category is required.'}, status=status.HTTP_400_BAD_REQUEST)

    category = Category.objects.filter(id=category_id).first()
    if not category:
        return Response({'error': 'Invalid category.'}, status=status.HTTP_400_BAD_REQUEST)

    from django.utils.text import slugify
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    while Post.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    # Get or create a default admin author
    admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        return Response({'error': 'No admin user found.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    post = Post.objects.create(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt or title,
        category=category,
        author=admin_user,
        post_type=post_type if post_type in (Post.PostType.NEWS, Post.PostType.BLOG) else Post.PostType.NEWS,
        status=post_status if post_status in (Post.Status.DRAFT, Post.Status.PUBLISHED) else Post.Status.DRAFT,
        is_featured=bool(is_featured),
    )

    if tag_ids:
        valid_tags = Tag.objects.filter(id__in=tag_ids)
        post.tags.set(valid_tags)

    return Response({
        'message': 'Post created successfully.',
        'post': {
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'status': post.status,
            'type': post.post_type,
            'admin_url': f'/admin/core/post/{post.id}/change/',
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@throttle_classes([QuickPostThrottle])
def quick_post_recent(request):
    """Return last 5 posts for the quick-post page."""
    if not _quick_post_authorized(request):
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

    posts = Post.objects.select_related('category').prefetch_related('tags').order_by('-created_at')[:5]
    return Response({
        'posts': [
            {
                'id': p.id,
                'title': p.title,
                'slug': p.slug,
                'type': p.post_type,
                'status': p.status,
                'category': p.category.name if p.category else None,
                'created_at': p.created_at,
                'admin_url': f'/admin/core/post/{p.id}/change/',
            }
            for p in posts
        ]
    })


def quick_post_page(request):
    """Render the minimal quick-post HTML page."""
    from django.shortcuts import render
    return render(request, 'quick_post.html')


# ─── AI Assistant ───────────────────────────────────────────────────────────

MAX_AI_MESSAGE_CHARS = 4000


def _get_or_create_ai_usage(user):
    """Get or create today's AIUsage record for a user, respecting their subscription plan."""
    from django.utils import timezone
    today = timezone.localdate()

    # Determine max_questions from active subscription
    max_q = 5  # free tier default
    try:
        sub = AISubscription.objects.get(user=user)
        if sub.is_active_plan():
            max_q = AISubscription.PLAN_LIMITS.get(sub.plan, 5)
        else:
            # If subscription is pending, still give free tier limit
            max_q = 5
    except AISubscription.DoesNotExist:
        pass

    usage, created = AIUsage.objects.get_or_create(
        user=user, date=today,
        defaults={'questions_used': 0, 'max_questions': max_q}
    )
    # Update max_questions if it changed (e.g. subscription was approved today)
    if not created and usage.max_questions != max_q:
        usage.max_questions = max_q
        usage.save(update_fields=['max_questions'])
    return usage


def _get_ai_response(user_message, mcq=None, history=None, context_type=None):
    """Generate AI assistant response via Gemini API."""
    from .ai_service import get_ai_response as _ai_get_response

    # Normalize history to ai_service format
    normalized = []
    if history:
        for h in history:
            normalized.append({
                'role': h.get('role', 'user'),
                'content': h.get('content', ''),
            })
    # Append current user message if not already in history
    if not normalized or normalized[-1].get('content') != user_message:
        normalized.append({'role': 'user', 'content': user_message})

    ctx_type = context_type if context_type else ("mcq" if mcq else "general")
    return _ai_get_response(messages=normalized, mcq=mcq, context_type=ctx_type)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_chat(request):
    """Main AI chat endpoint. Handles new and existing sessions.

    A question slot is reserved atomically before calling the AI and refunded if
    every provider fails, so failures never cost the user a question.
    """
    from .ai_service import is_failure_response

    user = request.user
    data = request.data

    session_id = data.get('session_id')
    mcq_id = _int_or_none(data.get('mcq_id'))
    context_type = data.get('context_type', 'general')
    user_message = str(data.get('message', '') or '').strip()

    if not user_message:
        return Response({'error': 'Message is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(user_message) > MAX_AI_MESSAGE_CHARS:
        return Response({'error': f'Message is too long (max {MAX_AI_MESSAGE_CHARS} characters).'},
                        status=status.HTTP_400_BAD_REQUEST)

    session = None
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id, user=user, is_active=True)
        except (ChatSession.DoesNotExist, DjangoValidationError, ValueError):
            return Response({'error': 'Session not found.'}, status=status.HTTP_404_NOT_FOUND)

    # 1. Reserve one question from today's allowance (atomic, so parallel requests can't overshoot)
    usage = _get_or_create_ai_usage(user)
    reserved = AIUsage.objects.filter(pk=usage.pk, questions_used__lt=F('max_questions')).update(
        questions_used=F('questions_used') + 1
    )
    usage.refresh_from_db()
    if not reserved:
        return Response({
            'error': 'Daily question limit reached.',
            'used': usage.questions_used,
            'remaining': 0,
            'max': usage.max_questions,
            'resets_at': str(usage.date + timedelta(days=1)),
        }, status=status.HTTP_403_FORBIDDEN)

    # 2. Resolve session
    new_session = session is None
    if new_session:
        mcq = MCQ.objects.filter(id=mcq_id).first() if mcq_id else None
        session = ChatSession.objects.create(user=user, mcq=mcq)

    # 3. Save user message
    user_msg = ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=user_message)

    # 4. Build context (last 10 messages)
    history = list(session.messages.order_by('-created_at')[:10].values('role', 'content'))
    history.reverse()

    # 5. Generate AI response (pass context_type from frontend)
    ai_text = _get_ai_response(user_message, mcq=session.mcq, history=history, context_type=context_type)

    failed = is_failure_response(ai_text)
    if failed:
        # Give the question back and drop the unanswered message so a retry starts clean.
        AIUsage.objects.filter(pk=usage.pk, questions_used__gt=0).update(questions_used=F('questions_used') - 1)
        user_msg.delete()
        if new_session:
            session.delete()
    else:
        # 6. Save assistant message
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=ai_text)

    usage.refresh_from_db()
    return Response({
        'session_id': None if failed and new_session else str(session.session_id),
        'message': ai_text,
        'failed': failed,
        'used': usage.questions_used,
        'remaining': usage.remaining(),
        'max': usage.max_questions,
        'resets_at': str(usage.date + timedelta(days=1)),
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_usage(request):
    """Return today's AI usage for the authenticated user."""
    from django.utils import timezone
    usage = _get_or_create_ai_usage(request.user)
    # Include subscription info so frontend can hide upgrade prompts
    sub_plan = 'free'
    sub_status = 'active'
    try:
        sub = AISubscription.objects.get(user=request.user)
        sub_plan = sub.plan
        sub_status = sub.status
    except AISubscription.DoesNotExist:
        pass
    return Response({
        'used': usage.questions_used,
        'remaining': usage.remaining(),
        'max': usage.max_questions,
        'resets_at': str(usage.date + timedelta(days=1)),
        'subscription_plan': sub_plan,
        'subscription_status': sub_status,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_diagnostic(request):
    """Diagnostic endpoint to check AI provider configuration (admin only)."""
    if not request.user.is_staff:
        return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

    from django.conf import settings as dj_settings

    groq_keys = getattr(dj_settings, 'GROQ_API_KEY', '')
    kimi_keys = getattr(dj_settings, 'KIMI_API_KEY', '')
    gemini_keys = getattr(dj_settings, 'GEMINI_API_KEY', '')

    def mask(key):
        if not key:
            return None
        k = key.strip()
        if len(k) <= 8:
            return f"{k[:2]}...{k[-2:]}"
        return f"{k[:4]}...{k[-4:]}"

    providers = []
    for name, keys, model_attr in [
        ('Groq', groq_keys, 'GROQ_MODEL'),
        ('Kimi', kimi_keys, 'KIMI_MODEL'),
        ('Gemini', gemini_keys, 'GEMINI_MODEL'),
    ]:
        key_list = [k.strip() for k in (keys or '').split(',') if k.strip()]
        providers.append({
            'name': name,
            'configured': len(key_list) > 0,
            'key_count': len(key_list),
            'key_preview': [mask(k) for k in key_list],
            'model': getattr(dj_settings, model_attr, 'default'),
        })

    # Test a simple request to the first available provider
    test_result = None
    try:
        from .ai_service import get_ai_response
        test_result = get_ai_response(
            messages=[{'role': 'user', 'content': 'Say "hello" in one word.'}],
            context_type='general'
        )
    except Exception as e:
        test_result = f"Exception: {e}"

    return Response({
        'providers': providers,
        'any_configured': bool(groq_keys or kimi_keys or gemini_keys),
        'test_response': test_result[:200] if isinstance(test_result, str) else str(test_result)[:200],
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_sessions(request):
    """Return all chat sessions for the authenticated user."""
    sessions = ChatSession.objects.filter(user=request.user).select_related('mcq').order_by('-created_at')
    result = []
    for s in sessions:
        first_msg = s.messages.order_by('created_at').first()
        msg_count = s.messages.count()
        result.append({
            'session_id': str(s.session_id),
            'created_at': s.created_at,
            'is_active': s.is_active,
            'message_count': msg_count,
            'first_message_preview': (first_msg.content[:100] + '...') if first_msg and len(first_msg.content) > 100 else (first_msg.content if first_msg else ''),
            'mcq': {
                'id': s.mcq_id,
                'question_text': s.mcq.question_text[:150] if s.mcq else None,
            } if s.mcq else None,
        })
    return Response({
        'sessions': result,
        'total_sessions': len(result),
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_session_detail(request, session_id):
    """Return full chat history for a session."""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=status.HTTP_404_NOT_FOUND)

    messages = session.messages.order_by('created_at').values('role', 'content', 'created_at')
    return Response({
        'session_id': str(session.session_id),
        'mcq_id': session.mcq_id,
        'mcq_question': session.mcq.question_text[:200] if session.mcq else None,
        'is_active': session.is_active,
        'created_at': session.created_at,
        'messages': list(messages),
    })


AI_RENEWAL_WINDOW_DAYS = 3


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def ai_subscribe(request):
    """Create or update an AI subscription for the user with payment proof."""
    plan = request.data.get('plan', '').strip().lower()
    payment_method = request.data.get('payment_method', '').strip()
    phone = request.data.get('phone', '').strip()
    payment_reference = request.data.get('payment_reference', '').strip()
    payment_screenshot = request.FILES.get('payment_screenshot')

    if plan not in ('pro', 'premium'):
        return Response({'error': 'Invalid plan. Choose "pro" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)

    if not phone or len(phone) < 11:
        return Response({'error': 'A valid phone number (11+ digits) is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if payment_method not in ('jazzcash', 'easypaisa', 'card'):
        return Response({'error': 'Invalid payment method.'}, status=status.HTTP_400_BAD_REQUEST)

    if not payment_reference:
        return Response({'error': 'Transaction reference number is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if not payment_screenshot:
        return Response({'error': 'Payment screenshot is required.'}, status=status.HTTP_400_BAD_REQUEST)

    upload_error = _image_upload_error(payment_screenshot, 'Payment screenshot')
    if upload_error:
        return Response({'error': upload_error}, status=status.HTTP_400_BAD_REQUEST)

    existing = AISubscription.objects.filter(user=request.user).first()
    if _payment_reference_used(payment_reference, exclude_subscription=existing):
        return Response({'error': 'This transaction reference has already been used.'}, status=status.HTTP_400_BAD_REQUEST)

    # A running paid plan isn't reset to "pending" by a new request; renewals open
    # in the last few days and approval extends from the current expiry date.
    if (existing and existing.plan != AISubscription.Plan.FREE and existing.is_active_plan()
            and existing.expires_at and existing.expires_at > timezone.now() + timedelta(days=AI_RENEWAL_WINDOW_DAYS)):
        return Response(
            {'error': f'Your {existing.plan.title()} plan is active until {existing.expires_at:%d %b %Y}. '
                      f'You can renew it in the last {AI_RENEWAL_WINDOW_DAYS} days.'},
            status=status.HTTP_409_CONFLICT,
        )

    # Delete old screenshot if replacing
    old_screenshot = None
    sub, created = AISubscription.objects.get_or_create(
        user=request.user,
        defaults={
            'plan': plan,
            'status': 'pending',
            'payment_method': payment_method,
            'phone': phone,
            'payment_reference': payment_reference,
            'payment_screenshot': payment_screenshot,
        }
    )

    if not created:
        old_screenshot = sub.payment_screenshot.name if sub.payment_screenshot else None
        sub.plan = plan
        sub.status = 'pending'
        sub.payment_method = payment_method
        sub.phone = phone
        sub.payment_reference = payment_reference
        sub.payment_screenshot = payment_screenshot
        # expires_at is (re)set when staff approve the payment.
        sub.save()

    # Delete old screenshot file after save
    if old_screenshot and payment_screenshot:
        from django.core.files.storage import default_storage
        if default_storage.exists(old_screenshot):
            default_storage.delete(old_screenshot)

    return Response({
        'message': f'{plan.capitalize()} plan subscription request submitted! Your payment is being verified.',
        'plan': sub.plan,
        'status': sub.status,
        'daily_limit': sub.daily_limit,
        'expires_at': str(sub.expires_at) if sub.expires_at else None,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ai_subscription_status(request):
    """Return current subscription status for the user."""
    try:
        sub = AISubscription.objects.get(user=request.user)
        return Response({
            'plan': sub.plan,
            'status': sub.status,
            'daily_limit': sub.daily_limit,
            'is_active': sub.is_active_plan(),
            'payment_method': sub.payment_method,
            'expires_at': str(sub.expires_at) if sub.expires_at else None,
        })
    except AISubscription.DoesNotExist:
        return Response({
            'plan': 'free',
            'status': 'active',
            'daily_limit': 5,
            'is_active': True,
            'payment_method': None,
            'expires_at': None,
        })


# ─── Job Application Assistant API ────────────────────────────────────────────

@api_view(['GET', 'POST', 'PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_job_profile(request):
    """Get or update the user's job application profile."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        serializer = JobProfileSerializer(profile)
        return Response(serializer.data)

    # POST or PUT — update profile
    serializer = JobProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        instance = serializer.save()
        # Auto-mark profile as complete if all required fields are filled
        required_fields = ['full_name', 'father_name', 'cnic', 'dob', 'domicile',
                           'gender', 'permanent_address', 'phone']
        complete = all(getattr(instance, f, None) for f in required_fields)
        was_incomplete = not instance.is_profile_complete
        if complete and was_incomplete:
            instance.is_profile_complete = True
            instance.save(update_fields=['is_profile_complete'])

            # ─── Find eligible jobs and notify ───
            try:
                from .eligibility import find_eligible_jobs
                from .models import Notification
                matches = find_eligible_jobs(request.user)
                eligible_matches = [m for m in matches if m['is_eligible']]
                if eligible_matches:
                    count = len(eligible_matches)
                    Notification.objects.create(
                        user=request.user,
                        notification_type=Notification.NotificationType.JOB_MATCH,
                        message=f"🎉 You are eligible for {count} active job{'s' if count > 1 else ''}! Check them out.",
                        link='/jobs',
                    )
            except Exception:
                pass  # Don't fail profile save if eligibility check errors

        # If frontend explicitly sent is_profile_complete=True, honor it
        if request.data.get('is_profile_complete') and complete:
            instance.is_profile_complete = True
            instance.save(update_fields=['is_profile_complete'])

        return Response(JobProfileSerializer(instance).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_education(request):
    """List user's education records or add a new one."""
    if request.method == 'GET':
        records = request.user.educations.all()
        serializer = UserEducationSerializer(records, many=True)
        return Response(serializer.data)

    # POST
    serializer = UserEducationSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH', 'DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_education_detail(request, pk):
    """Update or delete a specific education record."""
    try:
        record = request.user.educations.get(pk=pk)
    except UserEducation.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method in ('PUT', 'PATCH'):
        serializer = UserEducationSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    record.delete()
    return Response({'message': 'Deleted.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_experience(request):
    """List user's experience records or add a new one."""
    if request.method == 'GET':
        records = request.user.experiences.all()
        serializer = UserExperienceSerializer(records, many=True)
        return Response(serializer.data)

    # POST
    serializer = UserExperienceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH', 'DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_experience_detail(request, pk):
    """Update or delete a specific experience record."""
    try:
        record = request.user.experiences.get(pk=pk)
    except UserExperience.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method in ('PUT', 'PATCH'):
        serializer = UserExperienceSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    record.delete()
    return Response({'message': 'Deleted.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_documents(request):
    """List user's uploaded documents or upload a new one."""
    if request.method == 'GET':
        docs = request.user.job_documents.all()
        serializer = UserDocumentSerializer(docs, many=True)
        return Response(serializer.data)

    # POST
    serializer = UserDocumentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_document_detail(request, pk):
    """Delete a specific document."""
    try:
        doc = request.user.job_documents.get(pk=pk)
    except UserDocument.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    doc.delete()
    return Response({'message': 'Deleted.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_applications(request):
    """List user's job applications or save/apply to a new job."""
    if request.method == 'GET':
        apps = request.user.job_applications.select_related('job').all()
        serializer = JobApplicationSerializer(apps, many=True)
        return Response(serializer.data)

    # POST — save or apply to a job
    job_id = request.data.get('job')
    if not job_id:
        return Response({'error': 'job (JobListing ID) is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        job = JobListing.objects.get(pk=job_id)
    except JobListing.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Check for existing application
    existing = JobApplication.objects.filter(user=request.user, job=job).first()
    if existing:
        return Response(
            {'error': 'You have already saved/applied to this job.', 'application': JobApplicationSerializer(existing).data},
            status=status.HTTP_409_CONFLICT
        )

    serializer = JobApplicationSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user, job=job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_application_detail(request, pk):
    """Update an existing job application (status, roll number, test details, notes)."""
    try:
        app = request.user.job_applications.get(pk=pk)
    except JobApplication.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = JobApplicationSerializer(app, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_application_delete(request, pk):
    """Remove a saved/applied job from the user's tracker."""
    try:
        app = request.user.job_applications.get(pk=pk)
    except JobApplication.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    app.delete()
    return Response({'message': 'Deleted.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def eligible_jobs(request):
    """Return active jobs that match the user's highest education level."""
    # Determine user's highest education
    educations = request.user.educations.all()
    highest_level = None
    level_order = ['matric', 'intermediate', 'graduation', 'masters', 'mphil', 'phd']
    for edu in educations:
        idx = level_order.index(edu.level) if edu.level in level_order else -1
        if idx >= 0 and (highest_level is None or idx > level_order.index(highest_level)):
            highest_level = edu.level

    # Base queryset: active jobs
    jobs = JobListing.objects.filter(status=JobListing.Status.ACTIVE)

    # If no education recorded, return all active jobs
    if not highest_level:
        serializer = JobListingSerializer(jobs, many=True)
        return Response({'highest_level': None, 'jobs': serializer.data})

    # Use structured eligibility matching
    from .eligibility import check_eligibility
    eligible = []
    not_eligible = []
    incomplete = []
    for job in jobs:
        result = check_eligibility(request.user, job)
        data = JobListingSerializer(job).data
        data['eligibility'] = result
        if result['missing_info']:
            incomplete.append(data)
        elif result['is_eligible']:
            eligible.append(data)
        else:
            not_eligible.append(data)

    return Response({
        'highest_level': highest_level,
        'highest_level_display': dict(UserEducation.Level.choices).get(highest_level, ''),
        'eligible': eligible,
        'not_eligible': not_eligible,
        'incomplete': incomplete,
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def job_eligibility(request, pk):
    """Return detailed eligibility result for a specific job."""
    from .eligibility import check_eligibility, get_eligibility_badge

    try:
        job = JobListing.objects.get(pk=pk)
    except JobListing.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    result = check_eligibility(request.user, job)
    badge = get_eligibility_badge(request.user, job)

    return Response({
        'job_id': job.id,
        'job_title': job.title,
        'job_department': job.department,
        'job_location': job.location,
        'is_eligible': result['is_eligible'],
        'reasons': result['reasons'],
        'failed_reasons': result['failed_reasons'],
        'missing_info': result['missing_info'],
        'badge': badge,
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generate_application_package(request, pk):
    """Generate and return a PDF application package for a specific job application."""
    from .pdf_generator import generate_application_package
    from django.http import HttpResponse

    try:
        app = JobApplication.objects.select_related('job').get(pk=pk, user=request.user)
    except JobApplication.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

    job = app.job
    try:
        pdf_bytes = generate_application_package(request.user, job)
    except Exception as e:
        return Response({'error': f'Failed to generate PDF: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    safe_title = job.title.replace(' ', '_').replace('/', '_')[:50]
    filename = f"ImtihanHub_Application_{safe_title}_{app.id}.pdf"

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── Paid Application Service API ────────────────────────────────────────────

MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SERVICE_PAYMENT = Decimal('100000')


def _image_upload_error(upload, label='Screenshot'):
    """Return an error message unless `upload` is a real image of at most 5 MB."""
    if upload.size > MAX_IMAGE_UPLOAD_BYTES:
        return f'{label} must be 5 MB or smaller.'
    try:
        from PIL import Image
        Image.open(upload).verify()
    except Exception:
        return f'{label} must be a valid image (JPG, PNG or WebP).'
    finally:
        upload.seek(0)
    return None


def _payment_reference_used(reference, exclude_request=None, exclude_subscription=None):
    """A transaction reference may back only one payment across both paid products."""
    requests_qs = ApplicationRequest.objects.filter(payment_reference__iexact=reference)
    if exclude_request is not None:
        requests_qs = requests_qs.exclude(pk=exclude_request.pk)
    subs_qs = AISubscription.objects.filter(payment_reference__iexact=reference)
    if exclude_subscription is not None:
        subs_qs = subs_qs.exclude(pk=exclude_subscription.pk)
    return requests_qs.exists() or subs_qs.exists()


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def service_plans(request):
    """List all active service plans."""
    plans = ServicePlan.objects.filter(is_active=True)
    serializer = ServicePlanSerializer(plans, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def create_service_request(request):
    """User creates a new paid application submission request."""
    job_id = _int_or_none(request.data.get('job'))
    plan_id = _int_or_none(request.data.get('plan'))
    special_instructions = str(request.data.get('special_instructions', '') or '')[:2000]
    payment_method = str(request.data.get('payment_method', '') or '').strip()
    payment_reference = str(request.data.get('payment_reference', '') or '').strip()[:100]
    payment_screenshot = request.FILES.get('payment_screenshot')

    if not job_id:
        return Response({'error': 'job is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        job = JobListing.objects.get(pk=job_id)
    except JobListing.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if payment_method not in ApplicationRequest.PaymentMethod.values:
        return Response({'error': 'Invalid payment method.'}, status=status.HTTP_400_BAD_REQUEST)
    if payment_screenshot:
        upload_error = _image_upload_error(payment_screenshot, 'Payment screenshot')
        if upload_error:
            return Response({'error': upload_error}, status=status.HTTP_400_BAD_REQUEST)
    if payment_reference and _payment_reference_used(payment_reference):
        return Response({'error': 'This transaction reference has already been used.'}, status=status.HTTP_400_BAD_REQUEST)

    # A failed, refunded or submitted request doesn't block a new one.
    existing = ApplicationRequest.objects.filter(user=request.user, job=job).exclude(
        request_status__in=[
            ApplicationRequest.RequestStatus.SUBMITTED,
            ApplicationRequest.RequestStatus.FAILED,
            ApplicationRequest.RequestStatus.REFUNDED,
        ]
    ).first()
    if existing:
        return Response(
            {'error': 'You already have an active request for this job.', 'request': ApplicationRequestSerializer(existing).data},
            status=status.HTTP_409_CONFLICT,
        )

    # The price comes from the plan, never from the client. Without configured
    # plans the client's amount is accepted for staff to check against the payment.
    plan = None
    if plan_id:
        try:
            plan = ServicePlan.objects.get(pk=plan_id, is_active=True)
        except ServicePlan.DoesNotExist:
            return Response({'error': 'Service plan not found.'}, status=status.HTTP_404_NOT_FOUND)
        payment_amount = plan.price
    elif ServicePlan.objects.filter(is_active=True).exists():
        return Response({'error': 'Please choose a service plan.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        try:
            payment_amount = Decimal(str(request.data.get('payment_amount')))
        except (InvalidOperation, TypeError, ValueError):
            payment_amount = None
        if payment_amount is None or not (0 < payment_amount <= MAX_SERVICE_PAYMENT):
            return Response({'error': 'Invalid payment amount.'}, status=status.HTTP_400_BAD_REQUEST)

    # Snapshot user profile at request time
    profile_snapshot = {}
    try:
        profile = request.user.job_profile
        profile_snapshot = {
            'full_name': profile.full_name,
            'father_name': profile.father_name,
            'cnic': profile.cnic,
            'dob': str(profile.dob) if profile.dob else None,
            'gender': profile.get_gender_display() if profile.gender else None,
            'religion': profile.get_religion_display() if profile.religion else None,
            'domicile': profile.get_domicile_display() if profile.domicile else None,
            'phone': profile.phone,
            'whatsapp_number': profile.whatsapp_number,
            'permanent_address': profile.permanent_address,
            'current_address': profile.current_address,
        }
    except UserProfile.DoesNotExist:
        pass

    # Snapshot education
    educations = list(request.user.educations.values('level', 'board_university', 'passing_year', 'grade', 'total_marks', 'obtained_marks'))
    profile_snapshot['educations'] = educations

    # Snapshot experience
    experiences = list(request.user.experiences.values('organization', 'designation', 'from_date', 'to_date', 'is_current'))
    profile_snapshot['experiences'] = experiences

    app_request = ApplicationRequest.objects.create(
        user=request.user,
        job=job,
        plan=plan,
        profile_snapshot=profile_snapshot,
        special_instructions=special_instructions,
        payment_method=payment_method,
        payment_reference=payment_reference,
        payment_amount=payment_amount,
        payment_screenshot=payment_screenshot,
        request_status=(
            ApplicationRequest.RequestStatus.PAYMENT_VERIFICATION
            if payment_reference or payment_screenshot
            else ApplicationRequest.RequestStatus.PAYMENT_PENDING
        ),
    )
    serializer = ApplicationRequestSerializer(app_request)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def user_service_requests(request):
    """List the logged-in user's service requests."""
    reqs = request.user.application_requests.select_related('job', 'plan', 'assigned_to').prefetch_related('admin_notes')
    serializer = ApplicationRequestSerializer(reqs, many=True)
    return Response(serializer.data)


# ─── Admin Endpoints ───────────────────────────────────────────────────────

def is_admin(user):
    """Check if user is staff or superuser."""
    return user.is_staff or user.is_superuser


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admin_service_requests(request):
    """Admin: list all service requests with filtering."""
    if not is_admin(request.user):
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    reqs = ApplicationRequest.objects.select_related('user', 'job', 'plan', 'assigned_to').prefetch_related('admin_notes')

    # Filters
    status_filter = request.query_params.get('status')
    payment_filter = request.query_params.get('payment_status')
    assigned = request.query_params.get('assigned_to')
    if status_filter:
        reqs = reqs.filter(request_status=status_filter)
    if payment_filter:
        reqs = reqs.filter(payment_status=payment_filter)
    if assigned:
        reqs = reqs.filter(assigned_to__username=assigned)

    serializer = ApplicationRequestSerializer(reqs, many=True)
    return Response(serializer.data)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def admin_update_request(request, pk):
    """Admin: update request status, assignment, submission details and proof."""
    if not is_admin(request.user):
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        app_request = ApplicationRequest.objects.select_related('job').get(pk=pk)
    except ApplicationRequest.DoesNotExist:
        return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

    choices = {
        'request_status': ApplicationRequest.RequestStatus.values,
        'payment_status': ApplicationRequest.PaymentStatus.values,
    }
    for field, valid in choices.items():
        if field in request.data and request.data[field] not in valid:
            return Response({'error': f'Invalid {field} "{request.data[field]}".'}, status=status.HTTP_400_BAD_REQUEST)

    previous_status = app_request.request_status

    # Update fields
    allowed_fields = [
        'request_status', 'assigned_to', 'payment_status',
        'submission_reference', 'failure_reason', 'special_instructions',
    ]
    for field in allowed_fields:
        if field in request.data:
            if field == 'assigned_to':
                if request.data[field] in (None, ''):
                    app_request.assigned_to = None
                else:
                    user = User.objects.filter(pk=_int_or_none(request.data[field]), is_staff=True).first()
                    if not user:
                        return Response({'error': f"Staff user {request.data[field]} not found."}, status=status.HTTP_400_BAD_REQUEST)
                    app_request.assigned_to = user
            else:
                setattr(app_request, field, request.data[field])

    submission_screenshot = request.FILES.get('submission_screenshot')
    if submission_screenshot:
        upload_error = _image_upload_error(submission_screenshot, 'Submission screenshot')
        if upload_error:
            return Response({'error': upload_error}, status=status.HTTP_400_BAD_REQUEST)
        app_request.submission_screenshot = submission_screenshot

    if (app_request.request_status == ApplicationRequest.RequestStatus.SUBMITTED
            and previous_status != ApplicationRequest.RequestStatus.SUBMITTED):
        app_request.submitted_at = timezone.now()

    app_request.save()
    serializer = ApplicationRequestSerializer(app_request)
    return Response(serializer.data)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admin_add_note(request, pk):
    """Admin: add a note to an application request."""
    if not is_admin(request.user):
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        app_request = ApplicationRequest.objects.get(pk=pk)
    except ApplicationRequest.DoesNotExist:
        return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

    note_text = request.data.get('note', '').strip()
    if not note_text:
        return Response({'error': 'note is required.'}, status=status.HTTP_400_BAD_REQUEST)

    note = AdminNote.objects.create(
        request=app_request,
        note=note_text,
        added_by=request.user,
    )
    serializer = AdminNoteSerializer(note)
    return Response(serializer.data, status=status.HTTP_201_CREATED)
