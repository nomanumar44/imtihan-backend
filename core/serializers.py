from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, ContactMessage
)


class ExamSerializer(serializers.ModelSerializer):
    mcq_count = serializers.IntegerField(source='mcqs_count', read_only=True)
    papers_count = serializers.IntegerField(source='past_papers_count', read_only=True)
    syllabi_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = ['id', 'name', 'slug', 'badge_color', 'mcq_count', 'papers_count', 'syllabi_count', 'created_at']


class SubjectSerializer(serializers.ModelSerializer):
    mcq_count = serializers.IntegerField(source='mcqs_count', read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'slug', 'mcq_count', 'created_at']


class CurrentAffairsCategorySerializer(serializers.ModelSerializer):
    mcq_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CurrentAffairsCategory
        fields = ['id', 'name', 'slug', 'region', 'keywords', 'sort_order', 'is_active', 'mcq_count']


class MCQListSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    exam_badge_color = serializers.CharField(source='exam.badge_color', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    current_affairs_category_name = serializers.CharField(source='current_affairs_category.name', read_only=True)
    current_affairs_category_slug = serializers.CharField(source='current_affairs_category.slug', read_only=True)
    current_affairs_category_region = serializers.CharField(source='current_affairs_category.region', read_only=True)

    class Meta:
        model = MCQ
        fields = [
            'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'exam', 'exam_name', 'exam_badge_color',
            'subject', 'subject_name', 'current_affairs_category',
            'current_affairs_category_name', 'current_affairs_category_slug',
            'current_affairs_category_region', 'status', 'created_at'
        ]


class MCQDetailSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = MCQ
        fields = '__all__'


class PastPaperSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    exam_slug = serializers.CharField(source='exam.slug', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_slug = serializers.CharField(source='subject.slug', read_only=True)

    class Meta:
        model = PastPaper
        fields = '__all__'


class SyllabusSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)

    class Meta:
        model = Syllabus
        fields = '__all__'


class JobListingSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    syllabus_title = serializers.CharField(source='syllabus.title', read_only=True)

    class Meta:
        model = JobListing
        fields = '__all__'


class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'username', 'email', 'full_name',
            'phone', 'city', 'province', 'avatar', 'created_at'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class TestResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.username', read_only=True)
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = TestResult
        fields = '__all__'


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = '__all__'


class DashboardStatsSerializer(serializers.Serializer):
    total_mcqs = serializers.IntegerField()
    registered_users = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    tests_taken_today = serializers.IntegerField()
    mcqs_this_week = serializers.IntegerField()
    users_this_week = serializers.IntegerField()
    jobs_today = serializers.IntegerField()
    tests_vs_yesterday = serializers.IntegerField()


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
