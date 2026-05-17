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
    list_display = ['short_question', 'exam', 'subject', 'status', 'created_at']
    list_filter = ['status', 'exam', 'subject']
    search_fields = ['question_text']
    list_editable = ['status']

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Question'


@admin.register(PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display = ['title', 'exam', 'year', 'status', 'created_at']
    list_filter = ['status', 'exam', 'year']
    search_fields = ['title']


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
