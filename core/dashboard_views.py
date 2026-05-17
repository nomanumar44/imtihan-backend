from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count, Avg
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import (
    Exam, Subject, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog
)
from .forms import JobListingForm, SyllabusForm, PastPaperForm


def dashboard_login(request):
    """Custom login page for the admin dashboard."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard_home')

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('dashboard_home')
        else:
            messages.error(request, 'Invalid credentials or insufficient permissions.')

    return render(request, 'dashboard/login.html')


def dashboard_logout(request):
    logout(request)
    return redirect('dashboard_login')


@login_required(login_url='/dashboard/login/')
def dashboard_home(request):
    """Main dashboard page with stats, recent MCQs, activity, quick actions."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    # Stats
    total_mcqs = MCQ.objects.count()
    mcqs_this_week = MCQ.objects.filter(created_at__gte=week_start).count()
    registered_users = User.objects.count()
    users_this_week = User.objects.filter(date_joined__gte=week_start).count()
    active_jobs = JobListing.objects.filter(status='active').count()
    jobs_today = JobListing.objects.filter(created_at__gte=today_start).count()
    tests_today = TestResult.objects.filter(created_at__gte=today_start).count()
    tests_yesterday = TestResult.objects.filter(
        created_at__gte=yesterday_start, created_at__lt=today_start
    ).count()
    tests_vs_yesterday = tests_today - tests_yesterday

    # Recent MCQs
    recent_mcqs = MCQ.objects.select_related('exam', 'subject').all()[:5]

    # Recent Activity
    recent_activity = ActivityLog.objects.all()[:5]

    context = {
        'total_mcqs': f'{total_mcqs:,}',
        'mcqs_this_week': mcqs_this_week,
        'registered_users': f'{registered_users:,}',
        'users_this_week': users_this_week,
        'active_jobs': f'{active_jobs:,}',
        'jobs_today': jobs_today,
        'tests_today': f'{tests_today:,}',
        'tests_vs_yesterday': tests_vs_yesterday,
        'recent_mcqs': recent_mcqs,
        'recent_activity': recent_activity,
        'active_page': 'dashboard',
    }
    return render(request, 'dashboard/home.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_mcqs(request):
    """MCQ bank listing page."""
    mcqs = MCQ.objects.select_related('exam', 'subject').all()
    exams = Exam.objects.all()
    subjects = Subject.objects.all()

    # Filters
    exam_filter = request.GET.get('exam')
    subject_filter = request.GET.get('subject')
    status_filter = request.GET.get('status')

    if exam_filter:
        mcqs = mcqs.filter(exam__slug=exam_filter)
    if subject_filter:
        mcqs = mcqs.filter(subject__slug=subject_filter)
    if status_filter:
        mcqs = mcqs.filter(status=status_filter)

    total_count = mcqs.count()

    # Pagination
    paginator = Paginator(mcqs, 25) # 25 items per page
    page = request.GET.get('page')
    try:
        mcqs_page = paginator.page(page)
    except PageNotAnInteger:
        mcqs_page = paginator.page(1)
    except EmptyPage:
        mcqs_page = paginator.page(paginator.num_pages)

    context = {
        'mcqs': mcqs_page,
        'exams': exams,
        'subjects': subjects,
        'active_page': 'mcqs',
        'total_count': total_count,
    }
    return render(request, 'dashboard/mcqs.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_create(request):
    """MCQ creation and Excel upload page."""
    context = {'active_page': 'mcqs'}
    return render(request, 'dashboard/mcq_create.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_past_papers(request):
    """Past papers listing page."""
    papers = PastPaper.objects.select_related('exam', 'subject').all()
    total_count = papers.count()

    # Pagination
    paginator = Paginator(papers, 25)
    page = request.GET.get('page')
    try:
        papers_page = paginator.page(page)
    except PageNotAnInteger:
        papers_page = paginator.page(1)
    except EmptyPage:
        papers_page = paginator.page(paginator.num_pages)

    context = {
        'papers': papers_page,
        'active_page': 'past_papers',
        'total_count': total_count,
    }
    return render(request, 'dashboard/past_papers.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_syllabus(request):
    """Syllabus listing page."""
    syllabi = Syllabus.objects.select_related('exam').all()
    total_count = syllabi.count()

    # Pagination
    paginator = Paginator(syllabi, 25)
    page = request.GET.get('page')
    try:
        syllabi_page = paginator.page(page)
    except PageNotAnInteger:
        syllabi_page = paginator.page(1)
    except EmptyPage:
        syllabi_page = paginator.page(paginator.num_pages)

    context = {
        'syllabi': syllabi_page,
        'active_page': 'syllabus',
        'total_count': total_count,
    }
    return render(request, 'dashboard/syllabus.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_jobs(request):
    """Job listings page."""
    jobs = JobListing.objects.select_related('exam').all()
    total_count = jobs.count()

    # Pagination
    paginator = Paginator(jobs, 25)
    page = request.GET.get('page')
    try:
        jobs_page = paginator.page(page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = paginator.page(paginator.num_pages)

    context = {
        'jobs': jobs_page,
        'active_page': 'jobs',
        'total_count': total_count,
    }
    return render(request, 'dashboard/jobs.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_students(request):
    """Students listing page."""
    students = Student.objects.select_related('user').all()
    total_count = students.count()

    # Pagination
    paginator = Paginator(students, 25)
    page = request.GET.get('page')
    try:
        students_page = paginator.page(page)
    except PageNotAnInteger:
        students_page = paginator.page(1)
    except EmptyPage:
        students_page = paginator.page(paginator.num_pages)

    context = {
        'students': students_page,
        'active_page': 'students',
        'total_count': total_count,
    }
    return render(request, 'dashboard/students.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_test_results(request):
    """Test results listing page."""
    results = TestResult.objects.select_related('student', 'exam', 'subject').all()
    total_count = results.count()

    # Pagination
    paginator = Paginator(results, 25)
    page = request.GET.get('page')
    try:
        results_page = paginator.page(page)
    except PageNotAnInteger:
        results_page = paginator.page(1)
    except EmptyPage:
        results_page = paginator.page(paginator.num_pages)

    context = {
        'results': results_page,
        'active_page': 'test_results',
        'total_count': total_count,
    }
    return render(request, 'dashboard/test_results.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_settings(request):
    """Settings page placeholder."""
    context = {'active_page': 'settings'}
    return render(request, 'dashboard/settings.html', context)


# ─── Job listings CRUD ────────────────────────────────────────────────────────

@login_required(login_url='/dashboard/login/')
def dashboard_job_create(request):
    if request.method == 'POST':
        form = JobListingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job listing posted successfully!')
            return redirect('dashboard_jobs')
    else:
        form = JobListingForm()
    
    context = {
        'form': form,
        'title': 'Post Job',
        'active_page': 'jobs'
    }
    return render(request, 'dashboard/form.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_job_edit(request, pk):
    job = get_object_or_404(JobListing, pk=pk)
    if request.method == 'POST':
        form = JobListingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job listing updated successfully!')
            return redirect('dashboard_jobs')
    else:
        form = JobListingForm(instance=job)
    
    context = {
        'form': form,
        'title': 'Edit Job Listing',
        'active_page': 'jobs'
    }
    return render(request, 'dashboard/form.html', context)


# ─── Syllabus CRUD ────────────────────────────────────────────────────────────

@login_required(login_url='/dashboard/login/')
def dashboard_syllabus_create(request):
    if request.method == 'POST':
        form = SyllabusForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Syllabus entry created successfully!')
            return redirect('dashboard_syllabus')
    else:
        form = SyllabusForm()
    
    context = {
        'form': form,
        'title': 'Add Syllabus Entry',
        'active_page': 'syllabus'
    }
    return render(request, 'dashboard/form.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_syllabus_edit(request, pk):
    syllabus = get_object_or_404(Syllabus, pk=pk)
    if request.method == 'POST':
        form = SyllabusForm(request.POST, request.FILES, instance=syllabus)
        if form.is_valid():
            form.save()
            messages.success(request, 'Syllabus entry updated successfully!')
            return redirect('dashboard_syllabus')
    else:
        form = SyllabusForm(instance=syllabus)
    
    context = {
        'form': form,
        'title': 'Edit Syllabus Entry',
        'active_page': 'syllabus'
    }
    return render(request, 'dashboard/form.html', context)


# ─── Past Papers CRUD ─────────────────────────────────────────────────────────

@login_required(login_url='/dashboard/login/')
def dashboard_past_paper_create(request):
    if request.method == 'POST':
        form = PastPaperForm(request.POST, request.FILES)
        if form.is_valid():
            paper = form.save(commit=False)
            paper.created_by = request.user
            paper.save()
            messages.success(request, 'Past paper uploaded successfully!')
            return redirect('dashboard_past_papers')
    else:
        form = PastPaperForm()
    
    context = {
        'form': form,
        'title': 'Upload Past Paper',
        'active_page': 'past_papers'
    }
    return render(request, 'dashboard/form.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_past_paper_edit(request, pk):
    paper = get_object_or_404(PastPaper, pk=pk)
    if request.method == 'POST':
        form = PastPaperForm(request.POST, request.FILES, instance=paper)
        if form.is_valid():
            form.save()
            messages.success(request, 'Past paper updated successfully!')
            return redirect('dashboard_past_papers')
    else:
        form = PastPaperForm(instance=paper)
    
    context = {
        'form': form,
        'title': 'Edit Past Paper',
        'active_page': 'past_papers'
    }
    return render(request, 'dashboard/form.html', context)


# Global state for simple log streaming without redis/celery
SCRAPER_STATE = {
    'running': False,
    'logs': []
}

class ScraperLogStream:
    """A stream wrapper to capture call_command output line by line."""
    def write(self, s):
        if s.strip('\r\n'):
            for line in s.strip('\r\n').split('\n'):
                if line.strip():
                    SCRAPER_STATE['logs'].append(line.strip())
            # Keep only the last 1000 lines to avoid memory bloat
            if len(SCRAPER_STATE['logs']) > 1000:
                SCRAPER_STATE['logs'] = SCRAPER_STATE['logs'][-1000:]
    def flush(self):
        pass

@login_required(login_url='/dashboard/login/')
def dashboard_scraper(request):
    """Scraper control panel — choose type & max pages, then launch."""
    from django.core.management import call_command
    import threading

    if request.method == 'POST':
        scrape_type  = request.POST.get('scrape_type', 'all')
        start_page   = int(request.POST.get('start_page', 1))
        max_pages    = int(request.POST.get('max_pages', 0))
        valid_types  = ['all', 'mcqs', 'current-affairs', 'jobs']
        if scrape_type not in valid_types:
            scrape_type = 'all'

        if not SCRAPER_STATE['running']:
            SCRAPER_STATE['running'] = True
            SCRAPER_STATE['logs'] = []
            
            def run_scrape():
                stream = ScraperLogStream()
                try:
                    kwargs = {'type': scrape_type, 'start_page': start_page}
                    if max_pages > 0:
                        kwargs['max_pages'] = max_pages
                    # Pass stream to stdout so call_command writes directly to our global logs
                    call_command('scrape_data', stdout=stream, stderr=stream, **kwargs)
                except Exception as exc:
                    stream.write(f'[ERROR] {exc}')
                finally:
                    SCRAPER_STATE['running'] = False

            thread = threading.Thread(target=run_scrape, daemon=True)
            thread.start()

            messages.success(request,
                f'Scraper started in background — Type: {scrape_type.upper()}'
                + f', Start page: {start_page}'
                + (f', Limit: {max_pages} pages' if max_pages else ', All remaining pages')
            )
        else:
            messages.warning(request, 'Scraper is already running!')
            
        return redirect('dashboard_scraper')

    context = {
        'active_page':      'scraper',
        'scraper_running':  SCRAPER_STATE['running'],
        'scraper_log':      SCRAPER_STATE['logs'],
        'mcq_count':        MCQ.objects.count(),
        'job_count':        JobListing.objects.count(),
    }
    return render(request, 'dashboard/scraper.html', context)

@login_required(login_url='/dashboard/login/')
def dashboard_scraper_status(request):
    """Returns JSON of the current scraper status and logs for the live UI."""
    from django.http import JsonResponse
    return JsonResponse({
        'running': SCRAPER_STATE['running'],
        'logs': SCRAPER_STATE['logs']
    })

@login_required(login_url='/dashboard/login/')
def dashboard_trigger_scrape(request):
    """Legacy quick-run — kept for backward compat; redirects to scraper panel."""
    return redirect('dashboard_scraper')
