from django.contrib import admin
from .models import (
    Exam, Subject, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog
)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'badge_color', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(MCQ)
class MCQAdmin(admin.ModelAdmin):
    list_display = ['short_question', 'exam', 'subject', 'past_paper_link',
                    'status', 'created_at']
    list_filter  = ['status', 'exam', 'subject']
    search_fields = ['question_text', 'source_url']
    list_editable = ['status']
    readonly_fields = ['source_url', 'past_paper']
    raw_id_fields   = ['past_paper']

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Question'

    def past_paper_link(self, obj):
        from django.utils.html import format_html
        if obj.past_paper:
            return format_html(
                '<a href="/admin/core/pastpaper/{}/change/" target="_blank">{}</a>',
                obj.past_paper.pk,
                obj.past_paper.title[:40],
            )
        return '—'
    past_paper_link.short_description = 'Past Paper'


@admin.register(PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display  = ['title', 'exam', 'subject', 'year', 'mcq_count',
                     'status', 'has_pdf', 'created_at']
    list_filter   = ['status', 'exam', 'year']
    search_fields = ['title', 'source_url']
    readonly_fields = ['slug', 'source_url', 'mcq_count_display']
    prepopulated_fields = {}

    def mcq_count(self, obj):
        return obj.mcqs.count()
    mcq_count.short_description = 'MCQs'

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
    list_display = ['title', 'exam', 'post_name', 'created_at']
    list_filter = ['exam']
    search_fields = ['title', 'post_name']


@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'exam', 'department', 'bps_grade', 'location', 'status', 'last_date', 'created_at']
    list_filter = ['status', 'exam', 'location']
    search_fields = ['title', 'department', 'location', 'bps_grade']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'city', 'province', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone', 'city']


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'subject', 'score_percent', 'created_at']
    list_filter = ['exam', 'subject']
    search_fields = ['student__username']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['message', 'activity_type', 'user', 'created_at']
    list_filter = ['activity_type']
    search_fields = ['message']
