import io
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count, Avg
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, ContactMessage
)
from .forms import JobListingForm, SyllabusForm, PastPaperForm, MCQForm
from .mcq_parser import parse_mcq_text
from .utils import scraper_control


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
    mcqs = MCQ.objects.select_related('exam', 'subject', 'current_affairs_category').all()
    exams = Exam.objects.all()
    subjects = Subject.objects.annotate(mcq_count=Count('mcqs')).order_by('name')
    current_affairs_categories = (
        CurrentAffairsCategory.objects
        .filter(is_active=True)
        .annotate(mcq_count=Count('mcqs'))
        .order_by('region', 'sort_order', 'name')
    )

    # Filters
    exam_filter = request.GET.get('exam')
    subject_filter = request.GET.get('subject')
    ca_category_filter = request.GET.get('current_affairs_category')
    status_filter = request.GET.get('status')

    if exam_filter:
        mcqs = mcqs.filter(exam__slug=exam_filter)
    if subject_filter:
        mcqs = mcqs.filter(subject__slug=subject_filter)
    if ca_category_filter:
        mcqs = mcqs.filter(current_affairs_category__slug=ca_category_filter)
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
        'current_affairs_categories': current_affairs_categories,
        'active_page': 'mcqs',
        'total_count': total_count,
    }
    return render(request, 'dashboard/mcqs.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_create(request):
    """MCQ creation and Excel upload page."""
    exams = Exam.objects.all()
    subjects = Subject.objects.all()
    current_affairs_categories = list(
        CurrentAffairsCategory.objects
        .filter(is_active=True)
        .order_by('region', 'sort_order', 'name')
        .values('name', 'slug', 'region')
    )
    context = {
        'active_page': 'mcqs',
        'exams': exams,
        'subjects': subjects,
        'current_affairs_categories': current_affairs_categories,
    }
    return render(request, 'dashboard/mcq_create.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_bulk_upload(request):
    """Import MCQs into the dashboard from pasted text."""
    exams = Exam.objects.all()
    subjects = Subject.objects.all()
    current_affairs_categories = list(
        CurrentAffairsCategory.objects
        .filter(is_active=True)
        .order_by('region', 'sort_order', 'name')
        .values('name', 'slug', 'region')
    )

    context = {
        'active_page': 'mcqs',
        'exams': exams,
        'subjects': subjects,
        'current_affairs_categories': current_affairs_categories,
        'status': 'draft',
    }

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        raw_text = request.POST.get('raw_text', '').strip()
        status = request.POST.get('status', 'draft')
        source_url = request.POST.get('source_url', '').strip()
        category_slug = request.POST.get('current_affairs_category', '').strip()

        context.update({
            'raw_text': raw_text,
            'source_url': source_url,
            'status': status,
            'selected_exam': exam_id,
            'selected_subject': subject_id,
            'selected_current_affairs_category': category_slug,
        })

        if status not in ('draft', 'published', 'flagged'):
            status = 'draft'

        exam = Exam.objects.filter(pk=exam_id).first()
        subject = Subject.objects.filter(pk=subject_id).first()
        if not exam or not subject:
            messages.error(request, 'Please select a valid exam and subject.')
            return render(request, 'dashboard/mcq_bulk_upload.html', context)
        current_affairs_category = None
        if subject.slug == 'current-affairs' and category_slug:
            current_affairs_category = CurrentAffairsCategory.objects.filter(
                slug=category_slug,
                is_active=True,
            ).first()

        text = raw_text

        if not text:
            messages.error(request, 'Please paste MCQ text.')
            return render(request, 'dashboard/mcq_bulk_upload.html', context)

        parsed = parse_mcq_text(text)
        context['raw_text'] = text
        context['parsed_mcqs'] = parsed
        context['parsed_count'] = len(parsed)

        if not parsed:
            messages.warning(request, 'No MCQs could be parsed. Please check the format and try again.')
            return render(request, 'dashboard/mcq_bulk_upload.html', context)

        if action != 'save':
            messages.info(request, f'Extracted text and parsed {len(parsed)} MCQs. Review or edit before saving.')
            return render(request, 'dashboard/mcq_bulk_upload.html', context)

        created_count = 0
        with transaction.atomic():
            for item in parsed:
                MCQ.objects.create(
                    question_text=item['question_text'],
                    option_a=item['option_a'],
                    option_b=item['option_b'],
                    option_c=item['option_c'],
                    option_d=item['option_d'],
                    correct_option=item['correct_option'] or 'A',
                    explanation=item['explanation'],
                    exam=exam,
                    subject=subject,
                    current_affairs_category=current_affairs_category,
                    status=status,
                    source_url=source_url,
                    created_by=request.user,
                )
                created_count += 1

        messages.success(request, f'Successfully imported {created_count} MCQs.')
        return redirect('dashboard_mcqs')

    return render(request, 'dashboard/mcq_bulk_upload.html', context)


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_edit(request, pk):
    mcq = get_object_or_404(MCQ, pk=pk)
    if request.method == 'POST':
        form = MCQForm(request.POST, instance=mcq)
        if form.is_valid():
            form.save()
            messages.success(request, 'MCQ updated successfully!')
            return redirect('dashboard_mcqs')
    else:
        form = MCQForm(instance=mcq)
    
    context = {
        'form': form,
        'title': 'Edit MCQ',
        'active_page': 'mcqs'
    }
    return render(request, 'dashboard/form.html', context)


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
    jobs = JobListing.objects.select_related('exam', 'syllabus').all()
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
    'stop_requested': False,
    'logs': []
}

def append_scraper_log(line):
    if str(line).strip():
        SCRAPER_STATE['logs'].append(str(line).strip())
    if len(SCRAPER_STATE['logs']) > 1000:
        SCRAPER_STATE['logs'] = SCRAPER_STATE['logs'][-1000:]

class ScraperLogStream:
    """A stream wrapper to capture call_command output line by line."""
    def write(self, s):
        if s.strip('\r\n'):
            for line in s.strip('\r\n').split('\n'):
                if line.strip():
                    append_scraper_log(line)
    def flush(self):
        pass

@login_required(login_url='/dashboard/login/')
def dashboard_scraper(request):
    """Scraper control panel — supports scrape_data, scrape_testpoint, scrape_pastpapers."""
    from django.core.management import call_command
    import threading

    if request.method == 'POST':
        action = request.POST.get('action', 'start')

        if action == 'stop':
            if SCRAPER_STATE['running']:
                scraper_control.request_stop()
                SCRAPER_STATE['stop_requested'] = True
                append_scraper_log('[STOP] Stop requested from dashboard. Saving collected data before exit...')
                messages.warning(request, 'Stop requested. The scraper will save collected data before exiting.')
            else:
                messages.info(request, 'No scraper is currently running.')
            return redirect('dashboard_scraper')

        scraper_cmd = request.POST.get('scraper_cmd', 'scrape_data')

        if not SCRAPER_STATE['running']:
            scraper_control.clear_stop()
            SCRAPER_STATE['running'] = True
            SCRAPER_STATE['stop_requested'] = False
            SCRAPER_STATE['logs'] = []

            # Capture ALL POST values before the thread starts — the request
            # object is not safe to read from inside a background thread after
            # the HTTP response has been sent.
            _cmd        = scraper_cmd
            _sd_type    = request.POST.get('scrape_type', 'all')
            _sd_start   = int(request.POST.get('start_page', 1))
            _sd_max     = int(request.POST.get('max_pages', 0))
            _tp_exam    = request.POST.get('tp_exam', 'all')
            _tp_engine  = request.POST.get('tp_engine', 'curl')
            _tp_max     = int(request.POST.get('tp_max_papers', 0))
            _tp_subj    = request.POST.get('tp_subject', '')
            _tp_debug   = request.POST.get('tp_debug') == '1'
            _gt_subject = request.POST.get('gt_subject', '')
            _gt_max     = int(request.POST.get('gt_max_tests', 0))
            _gt_debug   = request.POST.get('gt_debug') == '1'
            _gt_dry_run = request.POST.get('gt_dry_run') == '1'
            _pp_exam    = request.POST.get('pp_exam', 'all')
            _pp_engine  = request.POST.get('pp_engine', 'curl')
            _pp_max     = int(request.POST.get('pp_max_posts', 0))
            _pp_subj    = request.POST.get('pp_subject', '')
            _pp_debug   = request.POST.get('pp_debug') == '1'

            def run_scrape():
                stream = ScraperLogStream()
                try:
                    if _cmd == 'scrape_data':
                        kwargs = {'type': _sd_type, 'start_page': _sd_start}
                        if _sd_max > 0:
                            kwargs['max_pages'] = _sd_max
                        call_command('scrape_data', stdout=stream, stderr=stream, **kwargs)

                    elif _cmd == 'scrape_testpoint':
                        call_command(
                            'scrape_testpoint', stdout=stream, stderr=stream,
                            exam=_tp_exam, engine=_tp_engine,
                            max_papers=_tp_max, subject=_tp_subj, debug=_tp_debug,
                        )

                    elif _cmd == 'scrape_gotest':
                        call_command(
                            'scrape_gotest', stdout=stream, stderr=stream,
                            subject=_gt_subject, max_tests=_gt_max,
                            debug=_gt_debug, dry_run=_gt_dry_run,
                        )

                    elif _cmd == 'scrape_pastpapers':
                        call_command(
                            'scrape_pastpapers', stdout=stream, stderr=stream,
                            exam=_pp_exam, engine=_pp_engine,
                            max_posts=_pp_max, subject=_pp_subj, debug=_pp_debug,
                        )

                except Exception as exc:
                    import traceback
                    stream.write(f'[ERROR] {exc}')
                    stream.write(traceback.format_exc())
                finally:
                    if SCRAPER_STATE.get('stop_requested'):
                        stream.write('[STOP] Scraper stopped gracefully after saving collected data.')
                    SCRAPER_STATE['running'] = False
                    SCRAPER_STATE['stop_requested'] = False
                    scraper_control.clear_stop()

            thread = threading.Thread(target=run_scrape, daemon=True)
            thread.start()
            messages.success(request, f'Scraper "{_cmd}" started in background.')
        else:
            messages.warning(request, 'A scraper is already running!')

        return redirect('dashboard_scraper')

    context = {
        'active_page':     'scraper',
        'scraper_running': SCRAPER_STATE['running'],
        'stop_requested':  SCRAPER_STATE['stop_requested'],
        'scraper_log':     SCRAPER_STATE['logs'],
        'mcq_count':       MCQ.objects.count(),
        'paper_count':     PastPaper.objects.count(),
        'job_count':       JobListing.objects.count(),
    }
    return render(request, 'dashboard/scraper.html', context)

@login_required(login_url='/dashboard/login/')
def dashboard_scraper_status(request):
    """Returns JSON of the current scraper status and logs for the live UI."""
    from django.http import JsonResponse
    return JsonResponse({
        'running': SCRAPER_STATE['running'],
        'stop_requested': SCRAPER_STATE['stop_requested'],
        'logs': SCRAPER_STATE['logs']
    })

@login_required(login_url='/dashboard/login/')
def dashboard_trigger_scrape(request):
    """Legacy quick-run — kept for backward compat; redirects to scraper panel."""
    return redirect('dashboard_scraper')


@login_required(login_url='/dashboard/login/')
def dashboard_contact_messages(request):
    """List all contact form submissions."""
    status_filter = request.GET.get('status', '')
    qs = ContactMessage.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    try:
        msgs = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        msgs = paginator.page(1)

    return render(request, 'dashboard/contact_messages.html', {
        'active_page':    'contact',
        'msgs':           msgs,
        'total_count':    qs.count(),
        'unread_count':   ContactMessage.objects.filter(status='unread').count(),
        'status_filter':  status_filter,
    })


@login_required(login_url='/dashboard/login/')
def dashboard_contact_mark_read(request, pk):
    """Mark a contact message as read."""
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.status = 'read'
    msg.save()
    return redirect('dashboard_contact_messages')


@login_required(login_url='/dashboard/login/')
def dashboard_contact_delete(request, pk):
    """Delete a contact message."""
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.delete()
    return redirect('dashboard_contact_messages')


# ─── MCQ Excel Export / Import ───────────────────────────────────────────────

HEADER = [
    'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
    'correct_option', 'explanation', 'exam_slug', 'subject_slug', 'status',
]

HEADER_NOTES = [
    'DO NOT EDIT',
    'The full question text',
    'Option A text',
    'Option B text',
    'Option C text',
    'Option D text (optional)',
    'A / B / C / D',
    'Optional explanation',
    'Exam slug (e.g. ppsc) — DO NOT CHANGE',
    'Subject slug — DO NOT CHANGE',
    'draft / published / flagged',
]


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_export(request):
    """Download MCQs as an Excel file. Filters: subject, exam, from_row, to_row."""
    exam_slug    = request.GET.get('exam', '')
    subject_slug = request.GET.get('subject', '')
    from_row     = request.GET.get('from_row', '')
    to_row       = request.GET.get('to_row', '')

    qs = MCQ.objects.select_related('exam', 'subject').order_by('id')
    if exam_slug:
        qs = qs.filter(exam__slug=exam_slug)
    if subject_slug:
        qs = qs.filter(subject__slug=subject_slug)

    # Convert to list for slicing by row number
    mcq_list = list(qs)
    total = len(mcq_list)

    try:
        fr = max(1, int(from_row)) - 1 if from_row else 0
        tr = int(to_row) if to_row else total
        tr = min(tr, total)
        mcq_list = mcq_list[fr:tr]
    except (ValueError, TypeError):
        pass

    # Build workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'MCQs'

    # Styles
    hdr_fill = PatternFill('solid', fgColor='0C3638')
    hdr_font = Font(bold=True, color='FFFFFF', size=11)
    note_fill = PatternFill('solid', fgColor='E8F5E9')
    note_font = Font(italic=True, color='444444', size=9)
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap   = Alignment(vertical='top', wrap_text=True)

    # Row 1 — headers
    for col_idx, h in enumerate(HEADER, 1):
        cell = ws.cell(row=1, column=col_idx, value=h.upper())
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = center
        cell.border = border

    # Row 2 — notes
    for col_idx, note in enumerate(HEADER_NOTES, 1):
        cell = ws.cell(row=2, column=col_idx, value=note)
        cell.font = note_font
        cell.fill = note_fill
        cell.alignment = center
        cell.border = border

    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 30

    # Data rows
    for row_idx, mcq in enumerate(mcq_list, 3):
        row = [
            mcq.id,
            mcq.question_text,
            mcq.option_a,
            mcq.option_b,
            mcq.option_c,
            mcq.option_d,
            mcq.correct_option,
            mcq.explanation,
            mcq.exam.slug,
            mcq.subject.slug,
            mcq.status,
        ]
        for col_idx, val in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = wrap
            cell.border = border

    # Column widths
    widths = [8, 60, 35, 35, 35, 35, 10, 45, 14, 20, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Freeze top 2 rows
    ws.freeze_panes = 'A3'

    # Protect id / exam_slug / subject_slug columns with a note (col A, I, J)
    ws.protection.sheet = False  # sheet itself not locked; just visual cue via fill

    filename = f"mcqs_export_{subject_slug or exam_slug or 'all'}_{fr+1}_to_{fr+len(mcq_list)}.xlsx"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='/dashboard/login/')
def dashboard_mcq_import(request):
    """Upload an edited Excel file and bulk-update MCQs by ID."""
    if request.method != 'POST':
        return redirect('dashboard_mcqs')

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, 'No file uploaded.')
        return redirect('dashboard_mcqs')

    if not excel_file.name.endswith(('.xlsx', '.xls')):
        messages.error(request, 'Please upload a valid .xlsx file.')
        return redirect('dashboard_mcqs')

    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        ws = wb.active
    except Exception as e:
        messages.error(request, f'Could not read Excel file: {e}')
        return redirect('dashboard_mcqs')

    # Validate header row
    headers = [str(ws.cell(1, c).value or '').lower().strip() for c in range(1, len(HEADER) + 1)]
    if headers != HEADER:
        messages.error(request, f'Invalid column headers. Expected: {", ".join(HEADER)}')
        return redirect('dashboard_mcqs')

    updated = 0
    skipped = 0
    errors  = []

    # Rows start at 3 (row 1 = headers, row 2 = notes)
    for row_num in range(3, ws.max_row + 1):
        row_vals = [ws.cell(row_num, c).value for c in range(1, len(HEADER) + 1)]
        if all(v is None for v in row_vals):
            continue  # skip fully empty rows

        try:
            mcq_id       = int(row_vals[0])
            question     = str(row_vals[1] or '').strip()
            opt_a        = str(row_vals[2] or '').strip()
            opt_b        = str(row_vals[3] or '').strip()
            opt_c        = str(row_vals[4] or '').strip()
            opt_d        = str(row_vals[5] or '').strip()
            correct      = str(row_vals[6] or '').strip().upper()
            explanation  = str(row_vals[7] or '').strip()
            status       = str(row_vals[10] or 'draft').strip().lower()
        except (ValueError, TypeError) as e:
            errors.append(f'Row {row_num}: bad data — {e}')
            skipped += 1
            continue

        if not question or correct not in ('A', 'B', 'C', 'D'):
            errors.append(f'Row {row_num}: missing question or invalid correct_option "{correct}"')
            skipped += 1
            continue

        if status not in ('draft', 'published', 'flagged'):
            status = 'draft'

        try:
            mcq = MCQ.objects.get(pk=mcq_id)
            mcq.question_text  = question
            mcq.option_a       = opt_a
            mcq.option_b       = opt_b
            mcq.option_c       = opt_c
            mcq.option_d       = opt_d
            mcq.correct_option = correct
            mcq.explanation    = explanation
            mcq.status         = status
            mcq.save()
            updated += 1
        except MCQ.DoesNotExist:
            errors.append(f'Row {row_num}: MCQ id={mcq_id} not found — skipped')
            skipped += 1

    summary = f'Import complete — {updated} updated, {skipped} skipped.'
    if errors:
        summary += f' Issues: ' + ' | '.join(errors[:5])
        if len(errors) > 5:
            summary += f' … and {len(errors)-5} more.'
        messages.warning(request, summary)
    else:
        messages.success(request, summary)

    return redirect('dashboard_mcqs')
