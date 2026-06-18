from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, ContactMessage, Announcement,
    Bookmark, EmailSubscription, TestAnswer, Notification,
    Category, Tag, Post, Comment, NewsSubscriber, Achievement, UserAchievement,
    AIUsage, ChatSession, ChatMessage,
    UserProfile, UserEducation, UserExperience, UserDocument, JobApplication,
    ServicePlan, ApplicationRequest, AdminNote,
)


class ExamSerializer(serializers.ModelSerializer):
    mcq_count = serializers.IntegerField(source='mcqs_count', read_only=True)
    papers_count = serializers.IntegerField(source='past_papers_count', read_only=True)
    syllabi_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = ['id', 'name', 'slug', 'description', 'icon', 'logo_url', 'badge_color', 'mcq_count', 'papers_count', 'syllabi_count', 'created_at']


class SubjectSerializer(serializers.ModelSerializer):
    mcq_count = serializers.IntegerField(source='mcqs_count', read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'slug', 'icon', 'logo_url', 'badge_color', 'mcq_count', 'created_at']


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
        fields = ['id', 'title', 'slug', 'exam', 'exam_name', 'post_name', 'bps_grade', 'marks', 'time', 'content', 'pdf_file', 'created_at', 'updated_at']


class JobListingSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    syllabus_title = serializers.CharField(source='syllabus.title', read_only=True)

    class Meta:
        model = JobListing
        fields = [
            'id', 'title', 'exam', 'exam_name', 'syllabus', 'syllabus_title',
            'department', 'location', 'bps_grade', 'description', 'qualifications',
            'vacancies', 'salary_range', 'experience', 'age_limit',
            'responsibilities', 'how_to_apply',
            'last_date', 'apply_link', 'status',
            # Eligibility requirements
            'min_age', 'max_age', 'min_education',
            'domicile_requirement', 'gender_requirement', 'min_experience_years',
            'created_at', 'updated_at',
        ]


class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'username', 'email', 'full_name',
            'phone', 'city', 'province', 'avatar',
            'xp_points', 'level', 'target_exam',
            'notify_papers', 'notify_jobs', 'notify_affairs',
            'daily_goal', 'streak_days', 'created_at'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    full_name = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'city', 'province', 'avatar',
            'target_exam', 'notify_papers', 'notify_jobs', 'notify_affairs',
            'member_since', 'xp_points', 'level', 'daily_goal', 'streak_days'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


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


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'text', 'url', 'placement', 'is_active', 'sort_order']


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


class _BookmarkMCQSerializer(serializers.ModelSerializer):
    question = serializers.CharField(source='question_text', read_only=True)
    subject = SubjectSerializer(read_only=True)
    exam = ExamSerializer(read_only=True)

    class Meta:
        model = MCQ
        fields = ['id', 'question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'explanation', 'subject', 'exam']


class BookmarkSerializer(serializers.ModelSerializer):
    mcq_question = serializers.CharField(source='mcq.question_text', read_only=True)
    mcq_exam_name = serializers.CharField(source='mcq.exam.name', read_only=True)
    mcq_subject_name = serializers.CharField(source='mcq.subject.name', read_only=True)
    mcq = _BookmarkMCQSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'mcq', 'mcq_question', 'mcq_exam_name', 'mcq_subject_name', 'created_at']
        read_only_fields = ['user', 'created_at']


class EmailSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSubscription
        fields = ['id', 'email', 'name', 'is_active', 'subscribed_at']
        read_only_fields = ['is_active', 'subscribed_at']


class TestAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAnswer
        fields = [
            'id', 'question_id', 'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'selected_option', 'explanation', 'is_correct'
        ]


class TestResultDetailSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    exam_slug = serializers.CharField(source='exam.slug', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_slug = serializers.CharField(source='subject.slug', read_only=True)
    answers = TestAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = TestResult
        fields = [
            'id', 'exam_name', 'exam_slug', 'subject_name', 'subject_slug',
            'total_questions', 'correct_answers', 'wrong_answers',
            'score_percent', 'time_taken_seconds', 'created_at', 'answers'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source='get_notification_type_display', read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'type_label', 'message', 'link', 'is_read', 'created_at', 'time_ago']

    def get_time_ago(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.created_at
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        mins = delta.seconds // 60
        return f"{mins}m ago"


class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'type', 'color', 'icon', 'post_count']

    def get_post_count(self, obj):
        return obj.posts.filter(status=Post.Status.PUBLISHED).count()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class PostListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    type_label = serializers.CharField(source='get_post_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    read_time = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'thumbnail_url',
            'category', 'tags', 'post_type', 'type_label',
            'status', 'status_label', 'is_featured',
            'views_count', 'author_name', 'read_time',
            'created_at', 'published_at',
        ]

    def get_read_time(self, obj):
        words = len(obj.content.split())
        minutes = max(1, words // 200)
        return f"{minutes} min read"

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail.url
        return None


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'name', 'content', 'created_at']


class PostDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_post_count = serializers.SerializerMethodField()
    author_bio = serializers.SerializerMethodField()
    type_label = serializers.CharField(source='get_post_type_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    read_time = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'excerpt', 'thumbnail_url',
            'category', 'tags', 'post_type', 'type_label',
            'status', 'status_label', 'is_featured',
            'views_count', 'author_name', 'author_post_count', 'author_bio', 'read_time',
            'created_at', 'published_at', 'comments',
        ]

    def get_read_time(self, obj):
        words = len(obj.content.split())
        minutes = max(1, words // 200)
        return f"{minutes} min read"

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail.url
        return None

    def get_author_post_count(self, obj):
        return Post.objects.filter(author=obj.author).count()

    def get_author_bio(self, obj):
        student = getattr(obj.author, 'student_profile', None)
        if student and student.city:
            return f"Exam prep enthusiast based in {student.city}."
        return "Content writer at ImtihanHub sharing exam prep tips and guides."


class NewsSubscriberSerializer(serializers.ModelSerializer):
    boards = serializers.PrimaryKeyRelatedField(
        queryset=Exam.objects.all(), many=True, required=False
    )

    class Meta:
        model = NewsSubscriber
        fields = ['id', 'email', 'boards', 'is_active', 'subscribed_at']


class AIUsageSerializer(serializers.ModelSerializer):
    remaining = serializers.ReadOnlyField()

    class Meta:
        model = AIUsage
        fields = ['id', 'user', 'date', 'questions_used', 'max_questions', 'remaining']


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'role', 'content', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    mcq_question = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ['id', 'user', 'mcq', 'mcq_question', 'session_id', 'created_at', 'is_active', 'messages']

    def get_mcq_question(self, obj):
        return obj.mcq.question_text[:200] if obj.mcq else None


# ─── Job Application Assistant Serializers ───

class JobProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'full_name', 'father_name', 'cnic', 'dob',
            'domicile', 'religion', 'gender',
            'permanent_address', 'current_address',
            'phone', 'whatsapp_number', 'profile_photo', 'is_profile_complete',
            'updated_at', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'updated_at', 'created_at']

    def validate_cnic(self, value):
        import re
        if value and not re.match(r'^\d{5}-\d{7}-\d{1}$', value.strip()):
            raise serializers.ValidationError('CNIC must be in format: 35201-1234567-8')
        return value.strip() if value else value

    def validate_phone(self, value):
        import re
        if value and not re.match(r'^0\d{3}-?\d{7}$', value.strip()):
            raise serializers.ValidationError('Phone must be in format: 0300-1234567')
        return value.strip() if value else value

    def validate_full_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Full name is required.')
        return value.strip()

    def validate_father_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Father's name is required.")
        return value.strip()


class UserEducationSerializer(serializers.ModelSerializer):
    percentage = serializers.ReadOnlyField()

    class Meta:
        model = UserEducation
        fields = [
            'id', 'user', 'level', 'board_university', 'passing_year',
            'total_marks', 'obtained_marks', 'grade', 'certificate_file',
            'percentage', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'percentage']


class UserExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserExperience
        fields = [
            'id', 'user', 'organization', 'designation',
            'from_date', 'to_date', 'is_current', 'experience_letter',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class UserDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDocument
        fields = ['id', 'user', 'doc_type', 'file', 'uploaded_at']
        read_only_fields = ['id', 'user', 'uploaded_at']


class JobApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    job_department = serializers.CharField(source='job.department', read_only=True)
    job_location = serializers.CharField(source='job.location', read_only=True)
    job_last_date = serializers.DateField(source='job.last_date', read_only=True)
    job_status = serializers.CharField(source='job.status', read_only=True)
    job_apply_link = serializers.CharField(source='job.apply_link', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'user', 'job', 'job_title', 'job_department', 'job_location',
            'job_last_date', 'job_status', 'job_apply_link',
            'applied_at', 'status', 'roll_number', 'test_date', 'test_venue',
            'notes', 'reminder_sent', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'applied_at', 'updated_at']


class ServicePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePlan
        fields = ['id', 'name', 'price', 'applications_included', 'validity_days', 'is_active', 'created_at']


class AdminNoteSerializer(serializers.ModelSerializer):
    added_by_name = serializers.CharField(source='added_by.username', read_only=True)

    class Meta:
        model = AdminNote
        fields = ['id', 'request', 'note', 'added_by', 'added_by_name', 'created_at']
        read_only_fields = ['id', 'added_by', 'created_at']


class ApplicationRequestSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    job_department = serializers.CharField(source='job.department', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(source='plan.price', max_digits=10, decimal_places=2, read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    admin_notes = AdminNoteSerializer(many=True, read_only=True)

    class Meta:
        model = ApplicationRequest
        fields = [
            'id', 'user', 'user_username', 'user_email',
            'job', 'job_title', 'job_department',
            'plan', 'plan_name', 'plan_price',
            'profile_snapshot', 'special_instructions',
            'payment_status', 'payment_method', 'payment_reference', 'payment_amount', 'payment_screenshot',
            'request_status', 'assigned_to', 'assigned_to_name',
            'submission_screenshot', 'submission_reference', 'submitted_at', 'failure_reason',
            'admin_notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
