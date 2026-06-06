from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, Announcement, SectionContent
)
from . import admin_views


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'description', 'logo_preview', 'icon', 'badge_color',
                    'mcq_count', 'paper_count', 'syllabus_count', 'job_count', 'created_at']
    list_editable = ['icon', 'badge_color']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _mcq_count=Count('mcqs', distinct=True),
            _paper_count=Count('past_papers', distinct=True),
            _syllabus_count=Count('syllabi', distinct=True),
            _job_count=Count('jobs', distinct=True),
        )

    def mcq_count(self, obj):
        return obj._mcq_count
    mcq_count.short_description = 'MCQs'
    mcq_count.admin_order_field = '_mcq_count'

    def paper_count(self, obj):
        return obj._paper_count
    paper_count.short_description = 'Papers'
    paper_count.admin_order_field = '_paper_count'

    def syllabus_count(self, obj):
        return obj._syllabus_count
    syllabus_count.short_description = 'Syllabi'
    syllabus_count.admin_order_field = '_syllabus_count'

    def job_count(self, obj):
        return obj._job_count
    job_count.short_description = 'Jobs'
    job_count.admin_order_field = '_job_count'

    def logo_preview(self, obj):
        if obj.logo_url:
            return format_html('<img src="{}" style="width:32px;height:32px;object-fit:contain;border-radius:4px;"/>', obj.logo_url)
        return '—'
    logo_preview.short_description = 'Logo'
    logo_preview.admin_order_field = 'logo_url'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'logo_preview', 'icon', 'badge_color',
                    'mcq_count', 'published_mcq_count', 'paper_count', 'created_at']
    list_editable = ['icon', 'badge_color']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _mcq_count=Count('mcqs', distinct=True),
            _published_mcq_count=Count('mcqs', filter=Q(mcqs__status='published'), distinct=True),
            _paper_count=Count('past_papers', distinct=True),
        )

    def mcq_count(self, obj):
        return obj._mcq_count
    mcq_count.short_description = 'MCQs'
    mcq_count.admin_order_field = '_mcq_count'

    def published_mcq_count(self, obj):
        return obj._published_mcq_count
    published_mcq_count.short_description = 'Published'
    published_mcq_count.admin_order_field = '_published_mcq_count'

    def paper_count(self, obj):
        return obj._paper_count
    paper_count.short_description = 'Papers'
    paper_count.admin_order_field = '_paper_count'

    def logo_preview(self, obj):
        if obj.logo_url:
            return format_html('<img src="{}" style="width:32px;height:32px;object-fit:contain;border-radius:4px;"/>', obj.logo_url)
        return '—'
    logo_preview.short_description = 'Logo'
    logo_preview.admin_order_field = 'logo_url'


@admin.register(CurrentAffairsCategory)
class CurrentAffairsCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'region', 'sort_order', 'mcq_count', 'is_active', 'updated_at']
    list_filter = ['region', 'is_active']
    list_editable = ['sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug', 'keywords']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_mcq_count=Count('mcqs', distinct=True))

    def mcq_count(self, obj):
        return obj._mcq_count
    mcq_count.short_description = 'MCQs'
    mcq_count.admin_order_field = '_mcq_count'


@admin.register(MCQ)
class MCQAdmin(admin.ModelAdmin):
    list_display = ['short_question', 'exam', 'subject', 'past_paper_link',
                    'current_affairs_category', 'status', 'created_at']
    list_filter  = ['status', 'exam', 'subject', 'current_affairs_category']
    search_fields = ['question_text', 'source_url']
    list_editable = ['status']
    list_select_related = ['exam', 'subject', 'past_paper', 'current_affairs_category']
    autocomplete_fields = ['exam', 'subject', 'current_affairs_category']
    readonly_fields = ['source_url', 'past_paper']
    raw_id_fields   = ['past_paper']
    change_list_template = 'admin/mcq_change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('bulk-upload/', admin_views.bulk_upload_mcq, name='core_mcq_bulk_upload'),
        ]
        return custom + urls

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Question'

    def past_paper_link(self, obj):
        if obj.past_paper:
            return format_html(
                '<a href="/admin/core/pastpaper/{}/change/" target="_blank">{}</a>',
                obj.past_paper.pk,
                obj.past_paper.title[:40],
            )
        return '—'
    past_paper_link.short_description = 'Past Paper'


class MCQInline(admin.TabularInline):
    """Read-only view of MCQs linked to a past paper."""
    model = MCQ
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ['short_question', 'subject', 'correct_option', 'status']
    readonly_fields = ['short_question', 'subject', 'correct_option', 'status']
    ordering = ['id']

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Question'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display  = ['title', 'exam', 'subject', 'year', 'mcq_count',
                     'status', 'has_pdf', 'created_at']
    list_filter   = ['status', 'exam', 'year']
    search_fields = ['title', 'slug', 'source_url']
    list_select_related = ['exam', 'subject']
    autocomplete_fields = ['exam', 'subject']
    readonly_fields = ['slug', 'source_url', 'mcq_count_display']
    inlines = [MCQInline]
    prepopulated_fields = {}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_mcq_count=Count('mcqs', distinct=True))

    def mcq_count(self, obj):
        return obj._mcq_count
    mcq_count.short_description = 'MCQs'
    mcq_count.admin_order_field = '_mcq_count'

    def mcq_count_display(self, obj):
        return obj.mcqs.count()
    mcq_count_display.short_description = 'Linked MCQs'

    def has_pdf(self, obj):
        from django.utils.html import format_html
        if obj.pdf_file:
            return format_html('<span style="color:green">&#10003;</span>')
        return format_html('<span style="color:#aaa">&#10007;</span>')
    has_pdf.short_description = 'PDF'


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'exam', 'post_name', 'job_count', 'created_at']
    list_filter = ['exam']
    search_fields = ['title', 'slug', 'post_name']
    list_select_related = ['exam']
    autocomplete_fields = ['exam']
    prepopulated_fields = {'slug': ('title',)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_job_count=Count('jobs', distinct=True))

    def job_count(self, obj):
        return obj._job_count
    job_count.short_description = 'Linked Jobs'
    job_count.admin_order_field = '_job_count'


@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'exam', 'department', 'bps_grade', 'location', 'vacancies', 'status', 'last_date', 'created_at']
    list_filter = ['status', 'exam', 'location']
    search_fields = ['title', 'department', 'location', 'bps_grade', 'syllabus__title']
    list_select_related = ['exam', 'syllabus']
    autocomplete_fields = ['exam', 'syllabus']
    fieldsets = [
        (None, {'fields': ['title', 'exam', 'department', 'location', 'status']}),
        ('Details', {'fields': ['bps_grade', 'vacancies', 'salary_range', 'experience', 'age_limit', 'last_date', 'apply_link']}),
        ('Description', {'fields': ['description', 'qualifications', 'responsibilities', 'how_to_apply']}),
        ('Syllabus', {'fields': ['syllabus']}),
    ]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'city', 'province', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone', 'city']
    list_select_related = ['user']
    autocomplete_fields = ['user']


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'subject', 'score_percent', 'created_at']
    list_filter = ['exam', 'subject']
    search_fields = ['student__username']
    list_select_related = ['student', 'exam', 'subject']
    autocomplete_fields = ['student', 'exam', 'subject']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['message', 'activity_type', 'user', 'created_at']
    list_filter = ['activity_type']
    search_fields = ['message']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['text', 'placement', 'url', 'sort_order', 'is_active', 'updated_at']
    list_filter = ['placement', 'is_active']
    list_editable = ['placement', 'sort_order', 'is_active']
    search_fields = ['text', 'url']


@admin.register(SectionContent)
class SectionContentAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'subtitle', 'is_active', 'updated_at']
    list_editable = ['title', 'subtitle', 'is_active']
    search_fields = ['key', 'title', 'subtitle']
