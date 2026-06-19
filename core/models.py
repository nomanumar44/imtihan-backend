import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField


class Exam(models.Model):
    """Exam body like PPSC, FPSC, NTS, SPSC, etc."""

    class Icon(models.TextChoices):
        LANDMARK = 'landmark', 'Landmark'
        FLAG = 'flag', 'Flag'
        AWARD = 'award', 'Award'
        CROWN = 'crown', 'Crown'
        BUILDING = 'building', 'Building'
        SHIELD = 'shield', 'Shield'
        FILE = 'file', 'File'
        BOOK = 'book', 'Book'

    COLOR_CHOICES = [
        ('green', 'Green'),
        ('blue', 'Blue'),
        ('amber', 'Amber'),
        ('red', 'Red'),
        ('rose', 'Rose'),
        ('violet', 'Violet'),
        ('cyan', 'Cyan'),
        ('slate', 'Slate'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Full name shown under the badge, e.g. Punjab Public Service Commission'
    )
    icon = models.CharField(
        max_length=20, choices=Icon.choices, default=Icon.LANDMARK,
        help_text='Icon shown on the exam card.'
    )
    badge_color = models.CharField(
        max_length=10, choices=COLOR_CHOICES, default='green',
        help_text='Accent color for the exam card.'
    )
    logo_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='External logo image URL (e.g. from scraped site or CDN).'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """Subject like Pakistan Studies, English, Math, etc."""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)
    icon = models.CharField(
        max_length=20,
        choices=Exam.Icon.choices,
        default=Exam.Icon.LANDMARK,
        help_text='Icon shown on the subject card.'
    )
    badge_color = models.CharField(
        max_length=10,
        choices=Exam.COLOR_CHOICES,
        default='green',
        help_text='Accent color for the subject card.'
    )
    logo_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text='External logo image URL (e.g. from scraped site or CDN).'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CurrentAffairsCategory(models.Model):
    """Configurable topic buckets for Current Affairs MCQs."""

    class Region(models.TextChoices):
        PAKISTAN = 'pakistan', 'Pakistan'
        WORLD = 'world', 'World'

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    region = models.CharField(
        max_length=20, choices=Region.choices, default=Region.PAKISTAN
    )
    keywords = models.TextField(
        blank=True,
        default='',
        help_text='Comma-separated words/phrases used to match MCQ question text.'
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['region', 'sort_order', 'name']
        verbose_name = 'Current Affairs Category'
        verbose_name_plural = 'Current Affairs Categories'

    def __str__(self):
        return self.name

    def keyword_list(self):
        return [item.strip() for item in self.keywords.split(',') if item.strip()]


class MCQ(models.Model):
    """Multiple Choice Question"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        FLAGGED = 'flagged', 'Flagged'

    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500, blank=True, default='')
    correct_option = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    )
    explanation = models.TextField(blank=True, default='')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='mcqs', db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='mcqs', db_index=True)
    past_paper = models.ForeignKey(
        'PastPaper', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mcqs', db_index=True
    )
    current_affairs_category = models.ForeignKey(
        CurrentAffairsCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mcqs',
        help_text='Only used when subject is Current Affairs.'
    )
    source_url = models.URLField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mcqs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'MCQ'
        verbose_name_plural = 'MCQs'
        indexes = [
            models.Index(fields=['exam', 'subject', 'status']),
        ]

    def __str__(self):
        return self.question_text[:80]

    def clean(self):
        if self.correct_option == 'D' and not self.option_d.strip():
            raise ValidationError("Correct option cannot be 'D' when option D is empty.")


class PastPaper(models.Model):
    """Past paper PDF uploads"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True, blank=True, default='', db_index=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='past_papers', db_index=True)
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, related_name='past_papers',
        null=True, blank=True, db_index=True
    )
    year = models.PositiveIntegerField(default=0)
    pdf_file = models.FileField(upload_to='past_papers/', blank=True, null=True)
    source_url = models.URLField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.year})"

    def clean(self):
        from django.utils.text import slugify
        if not self.slug.strip():
            base = f"{self.title}-{self.year}" if self.title and self.year else (self.title or 'paper')
            self.slug = slugify(base)[:350]
        if not self.slug.strip():
            raise ValidationError("Unable to generate a valid slug. Please provide a title or slug.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Syllabus(models.Model):
    """Syllabus for an exam/post"""
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True, blank=True, default='', db_index=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='syllabi', db_index=True)
    post_name = models.CharField(max_length=200, blank=True, default='')
    bps_grade = models.CharField(max_length=50, blank=True, default='', help_text='e.g., BPS-14')
    marks = models.PositiveIntegerField(blank=True, null=True, help_text='Total marks for the exam')
    time = models.CharField(max_length=50, blank=True, default='', help_text='e.g., 90 minutes')
    content = models.TextField(help_text='Syllabus content in markdown or plain text')
    pdf_file = models.FileField(upload_to='syllabus/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Syllabi'

    def __str__(self):
        return self.title

    def clean(self):
        from django.utils.text import slugify
        if not self.slug.strip():
            base = f"{self.title}-{self.post_name}" if self.title and self.post_name else (self.title or 'syllabus')
            self.slug = slugify(base)[:350]
        if not self.slug.strip():
            raise ValidationError("Unable to generate a valid slug. Please provide a title or slug.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class JobListing(models.Model):
    """Government job listings"""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        CLOSED = 'closed', 'Closed'
        UPCOMING = 'upcoming', 'Upcoming'

    title = models.CharField(max_length=300)
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='jobs',
        null=True, blank=True
    )
    syllabus = models.ForeignKey(
        Syllabus, on_delete=models.PROTECT, related_name='jobs',
        null=True
    )
    department = models.CharField(max_length=200, blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='', help_text="e.g., Punjab, Federal, Sindh")
    bps_grade = models.CharField(max_length=50, blank=True, default='', help_text="e.g., BPS-14, BPS-16")
    description = models.TextField()
    qualifications = models.TextField(blank=True, default='')
    vacancies = models.PositiveIntegerField(default=1, help_text='Number of open positions')
    salary_range = models.CharField(max_length=200, blank=True, default='', help_text='e.g., Rs. 22,000 - 65,000/month')
    experience = models.CharField(max_length=200, blank=True, default='', help_text='e.g., Fresh candidates can apply')
    age_limit = models.CharField(max_length=100, blank=True, default='', help_text='e.g., 18-25 years (plus 5 years relaxation)')
    responsibilities = models.JSONField(default=list, blank=True, help_text='List of key responsibilities (one per line in admin)')
    how_to_apply = models.JSONField(default=list, blank=True, help_text='List of how-to-apply steps (one per line in admin)')
    last_date = models.DateField(null=True, blank=True)
    apply_link = models.URLField(blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    # ─── Eligibility Requirements ───
    min_age = models.PositiveIntegerField(null=True, blank=True, help_text='Minimum age in years')
    max_age = models.PositiveIntegerField(null=True, blank=True, help_text='Maximum age in years')
    min_education = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('matric', 'Matric'),
            ('intermediate', 'Intermediate'),
            ('graduation', 'Graduation'),
            ('masters', 'Masters'),
            ('mphil', 'MPhil'),
            ('phd', 'PhD'),
        ],
        help_text='Minimum education level required'
    )
    domicile_requirement = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('punjab', 'Punjab'),
            ('sindh', 'Sindh'),
            ('kpk', 'Khyber Pakhtunkhwa'),
            ('balochistan', 'Balochistan'),
            ('ict', 'Islamabad (ICT)'),
            ('gilgit', 'Gilgit-Baltistan'),
            ('ajk', 'Azad Jammu & Kashmir'),
        ],
        help_text='Domicile requirement (leave blank for any)'
    )
    gender_requirement = models.CharField(
        max_length=10, blank=True, default='',
        choices=[
            ('male', 'Male'),
            ('female', 'Female'),
        ],
        help_text='Gender requirement (leave blank for both)'
    )
    min_experience_years = models.PositiveIntegerField(null=True, blank=True, help_text='Minimum years of experience (0 for fresh)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Student(models.Model):
    """Extended student profile linked to User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    phone = models.CharField(max_length=20, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    province = models.CharField(max_length=100, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    google_id = models.CharField(max_length=255, blank=True, default='', db_index=True)
    google_picture = models.URLField(max_length=500, blank=True, default='')
    daily_goal = models.PositiveIntegerField(default=20, help_text='Daily MCQ target')
    daily_test_goal = models.PositiveIntegerField(default=1, help_text='Daily test target')
    mcqs_today = models.PositiveIntegerField(default=0, help_text='MCQs answered today')
    tests_today = models.PositiveIntegerField(default=0, help_text='Tests completed today')
    streak_days = models.PositiveIntegerField(default=0)
    last_practice_date = models.DateField(null=True, blank=True)
    xp_points = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    reminder_time = models.TimeField(null=True, blank=True, help_text='Daily reminder time')
    target_exam = models.CharField(max_length=20, blank=True, default='', choices=[
        ('', 'None'), ('PPSC', 'PPSC'), ('FPSC', 'FPSC'), ('CSS', 'CSS'), ('NTS', 'NTS'), ('PMS', 'PMS'),
    ])
    notify_papers = models.BooleanField(default=True)
    notify_jobs = models.BooleanField(default=True)
    notify_affairs = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Bookmark(models.Model):
    """MCQs bookmarked by a student for revision."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookmarks'
    )
    mcq = models.ForeignKey(
        MCQ, on_delete=models.CASCADE, related_name='bookmarks'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'mcq']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — MCQ #{self.mcq_id}"


class Achievement(models.Model):
    """Gamification badges that students can unlock."""
    class ConditionType(models.TextChoices):
        TESTS_COMPLETED = 'tests_completed', 'Tests Completed'
        STREAK_DAYS = 'streak_days', 'Streak Days'
        MCQS_ANSWERED = 'mcqs_answered', 'MCQs Answered'
        PERFECT_SCORE = 'perfect_score', 'Perfect Score'
        PPSC_TESTS = 'ppsc_tests', 'PPSC Tests'
        NIGHT_OWL = 'night_owl', 'Night Owl'
        LOGIN_DAYS = 'login_days', 'Login Days'

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=30, default='award', help_text='lucide icon name')
    xp_reward = models.PositiveIntegerField(default=0)
    condition_type = models.CharField(
        max_length=30, choices=ConditionType.choices, default=ConditionType.TESTS_COMPLETED
    )
    condition_value = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """Tracks which achievements a user has unlocked."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'achievement']

    def __str__(self):
        return f"{self.user.username} — {self.achievement.name}"


class DailyPracticeLog(models.Model):
    """Records which days a user practiced (for heatmap)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='practice_logs')
    date = models.DateField()
    mcqs_answered = models.PositiveIntegerField(default=0)
    tests_completed = models.PositiveIntegerField(default=0)
    xp_earned = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} — {self.date}"


class TestResult(models.Model):
    """Records of tests taken by students"""
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='test_results'
    )
    exam = models.ForeignKey(
        Exam, on_delete=models.SET_NULL, null=True, related_name='test_results'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, related_name='test_results'
    )
    total_questions = models.PositiveIntegerField()
    correct_answers = models.PositiveIntegerField()
    wrong_answers = models.PositiveIntegerField(default=0)
    score_percent = models.DecimalField(max_digits=5, decimal_places=2)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} — {self.score_percent}%"


class TestAnswer(models.Model):
    """Individual question answers recorded during a test."""
    test_result = models.ForeignKey(
        TestResult, on_delete=models.CASCADE, related_name='answers'
    )
    question_id = models.PositiveIntegerField()
    question_text = models.TextField()
    option_a = models.TextField(blank=True, default='')
    option_b = models.TextField(blank=True, default='')
    option_c = models.TextField(blank=True, default='')
    option_d = models.TextField(blank=True, default='')
    correct_option = models.CharField(max_length=1)
    selected_option = models.CharField(max_length=1, blank=True, default='')
    explanation = models.TextField(blank=True, default='')
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Q{self.question_id} — {self.test_result}"


class ActivityLog(models.Model):
    """Admin activity log for the dashboard"""

    class ActivityType(models.TextChoices):
        MCQ_ADDED = 'mcq_added', 'MCQ Added'
        PAPER_UPLOADED = 'paper_uploaded', 'Paper Uploaded'
        JOB_POSTED = 'job_posted', 'Job Posted'
        SYLLABUS_UPDATED = 'syllabus_updated', 'Syllabus Updated'
        FLAGGED = 'flagged', 'Flagged'
        OTHER = 'other', 'Other'

    activity_type = models.CharField(
        max_length=20, choices=ActivityType.choices, default=ActivityType.OTHER
    )
    message = models.CharField(max_length=500)
    color = models.CharField(max_length=7, default='#1D9E75')
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:80]


class Announcement(models.Model):
    """Items shown in the site-wide announcement bar.

    A `headline` placement renders as the bell message on the left, while
    `link` placement items render as quick links on the right of the bar.
    """

    class Placement(models.TextChoices):
        HEADLINE = 'headline', 'Headline (left message)'
        LINK = 'link', 'Quick link (right side)'

    text = models.CharField(
        max_length=255,
        help_text='Announcement message or quick-link label.'
    )
    url = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Optional link. Leave blank for a non-clickable message.'
    )
    placement = models.CharField(
        max_length=10, choices=Placement.choices, default=Placement.HEADLINE
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.text[:80]


class SectionContent(models.Model):
    """Editable heading/subheading text for frontend sections.

    The `key` is referenced by the frontend (e.g. `exam_board`) to look up
    the title/subtitle so admins can edit section copy without code changes.
    """

    key = models.SlugField(
        max_length=60, unique=True,
        help_text='Identifier used by the frontend, e.g. exam_board'
    )
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True, default='')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Section Content'
        verbose_name_plural = 'Section Content'

    def __str__(self):
        return self.key


class ContactMessage(models.Model):
    SUBJECT_CHOICES = [
        ('general',     'General inquiry'),
        ('bug',         'Report a bug'),
        ('content',     'Suggest content'),
        ('partnership', 'Partnership'),
        ('other',       'Other'),
    ]
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('read',   'Read'),
        ('replied','Replied'),
    ]

    name       = models.CharField(max_length=200)
    email      = models.EmailField()
    subject    = models.CharField(max_length=50, choices=SUBJECT_CHOICES, default='general')
    message    = models.TextField()
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.get_subject_display()} ({self.created_at:%d %b %Y})"


class EmailSubscription(models.Model):
    """Email subscribers for job alerts and newsletter."""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email


class Notification(models.Model):
    """User notifications for activity on the platform."""
    class NotificationType(models.TextChoices):
        PAST_PAPER = 'past_paper', 'New Past Paper'
        JOB_POSTED = 'job_posted', 'New Job Posted'
        CURRENT_AFFAIRS = 'current_affairs', 'Current Affairs Ready'
        STREAK_REMINDER = 'streak_reminder', 'Streak Reminder'
        ACHIEVEMENT = 'achievement', 'Achievement Unlocked'
        JOB_MATCH = 'job_match', 'Job Match Found'
        SERVICE_REQUEST = 'service_request', 'Service Request Update'
        SYSTEM = 'system', 'System'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.message[:40]}"


class Category(models.Model):
    """Categories for news and blog posts."""
    class Type(models.TextChoices):
        NEWS = 'news', 'News'
        BLOG = 'blog', 'Blog'

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.BLOG)
    color = models.CharField(max_length=7, default='#10B981', help_text='Hex color code')
    icon = models.CharField(max_length=50, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Tags for news and blog posts."""
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Post(models.Model):
    """News articles and blog posts."""
    class PostType(models.TextChoices):
        NEWS = 'news', 'News'
        BLOG = 'blog', 'Blog'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True)
    content = RichTextUploadingField(config_name='default')
    excerpt = models.TextField(blank=True, default='', help_text='Short summary')
    thumbnail = models.ImageField(upload_to='posts/thumbnails/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='posts')
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    post_type = models.CharField(max_length=10, choices=PostType.choices, default=PostType.BLOG)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('api-post-detail', kwargs={'slug': self.slug})


class PostImage(models.Model):
    """Additional images for a blog/news post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='posts/images/')
    caption = models.CharField(max_length=200, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Post Image'
        verbose_name_plural = 'Post Images'

    def __str__(self):
        return f"Image for {self.post.title}"


class Comment(models.Model):
    """Comments on blog posts. Approved by admin before public display."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    content = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} on {self.post.title}"


class NewsSubscriber(models.Model):
    """Email subscribers for exam news alerts by board."""
    email = models.EmailField()
    boards = models.ManyToManyField(Exam, blank=True, related_name='subscribers')
    is_active = models.BooleanField(default=True)
    unsubscribe_token = models.CharField(max_length=64, unique=True, db_index=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-subscribed_at']
        constraints = [
            models.UniqueConstraint(fields=['email'], condition=models.Q(is_active=True), name='unique_active_email')
        ]

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            import secrets
            self.unsubscribe_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({'active' if self.is_active else 'inactive'})"


class AIUsage(models.Model):
    """Tracks daily AI assistant question usage per user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_usage')
    date = models.DateField()
    questions_used = models.PositiveIntegerField(default=0)
    max_questions = models.PositiveIntegerField(default=5)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']

    def remaining(self):
        return max(0, self.max_questions - self.questions_used)

    def __str__(self):
        return f"{self.user.username} — {self.date} ({self.questions_used}/{self.max_questions})"


class ChatSession(models.Model):
    """A conversation thread for the AI assistant."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    mcq = models.ForeignKey(MCQ, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_sessions')
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.session_id} ({self.user.username})"


class ChatMessage(models.Model):
    """Individual message within a chat session."""
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role} — {self.content[:60]}"


# ─── AI Subscription Models ───

class AISubscription(models.Model):
    """Tracks paid AI subscription plans for users."""
    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'
        PREMIUM = 'premium', 'Premium'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PENDING = 'pending', 'Pending Payment'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    PLAN_LIMITS = {
        'free': 5,
        'pro': 100,
        'premium': 9999,  # Essentially unlimited
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ai_subscription')
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    payment_method = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, default='', help_text='Transaction ID / reference number')
    payment_screenshot = models.ImageField(upload_to='ai_payments/', blank=True, null=True, help_text='Payment proof screenshot')
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def daily_limit(self):
        return self.PLAN_LIMITS.get(self.plan, 5)

    def is_active_plan(self):
        if self.status != 'active':
            return False
        if self.expires_at and self.expires_at < timezone.now():
            self.status = 'expired'
            self.save(update_fields=['status'])
            return False
        return True

    def __str__(self):
        return f"{self.user.username} — {self.plan} ({self.status})"


# ─── Job Application Assistant Models ───

class UserProfile(models.Model):
    """Extended profile for job applications — personal details."""

    class Domicile(models.TextChoices):
        PUNJAB = 'punjab', 'Punjab'
        SINDH = 'sindh', 'Sindh'
        KPK = 'kpk', 'Khyber Pakhtunkhwa'
        BALOCHISTAN = 'balochistan', 'Balochistan'
        ICT = 'ict', 'Islamabad (ICT)'
        GILGIT = 'gilgit', 'Gilgit-Baltistan'
        AJK = 'ajk', 'Azad Jammu & Kashmir'

    class Religion(models.TextChoices):
        ISLAM = 'islam', 'Islam'
        CHRISTIANITY = 'christianity', 'Christianity'
        HINDUISM = 'hinduism', 'Hinduism'
        SIKHISM = 'sikhism', 'Sikhism'
        OTHER = 'other', 'Other'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='job_profile')
    full_name = models.CharField(max_length=200, blank=True, default='')
    father_name = models.CharField(max_length=200, blank=True, default='')
    cnic = models.CharField(max_length=50, blank=True, default='', help_text='Encrypted CNIC number')
    dob = models.DateField(null=True, blank=True)
    domicile = models.CharField(max_length=20, choices=Domicile.choices, blank=True, default='')
    religion = models.CharField(max_length=20, choices=Religion.choices, blank=True, default='')
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default='')
    permanent_address = models.TextField(blank=True, default='')
    current_address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    whatsapp_number = models.CharField(max_length=30, blank=True, default='')
    profile_photo = models.ImageField(upload_to='job_profiles/photos/', blank=True, null=True)
    is_profile_complete = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} Profile"


class UserEducation(models.Model):
    """Educational qualifications for job applications."""

    class Level(models.TextChoices):
        MATRIC = 'matric', 'Matric'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        GRADUATION = 'graduation', 'Graduation'
        MASTERS = 'masters', 'Masters'
        MPHIL = 'mphil', 'MPhil'
        PHD = 'phd', 'PhD'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='educations')
    level = models.CharField(max_length=20, choices=Level.choices)
    board_university = models.CharField(max_length=200, blank=True, default='')
    passing_year = models.PositiveIntegerField(null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True)
    obtained_marks = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=20, blank=True, default='')
    certificate_file = models.FileField(upload_to='job_profiles/education/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-level', '-passing_year']

    def __str__(self):
        return f"{self.user.username} — {self.get_level_display()}"

    def percentage(self):
        if self.total_marks and self.obtained_marks:
            return round((self.obtained_marks / self.total_marks) * 100, 2)
        return None


class UserExperience(models.Model):
    """Work experience for job applications."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiences')
    organization = models.CharField(max_length=200)
    designation = models.CharField(max_length=200)
    from_date = models.DateField()
    to_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    experience_letter = models.FileField(upload_to='job_profiles/experience/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-from_date']

    def __str__(self):
        return f"{self.user.username} — {self.designation} at {self.organization}"


class UserDocument(models.Model):
    """Uploaded documents for job applications."""

    class DocType(models.TextChoices):
        CNIC_FRONT = 'cnic_front', 'CNIC Front'
        CNIC_BACK = 'cnic_back', 'CNIC Back'
        DOMICILE = 'domicile', 'Domicile Certificate'
        CHARACTER = 'character', 'Character Certificate'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_documents')
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    file = models.FileField(upload_to='job_profiles/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.user.username} — {self.get_doc_type_display()}"


class JobApplication(models.Model):
    """User's job application tracker."""

    class Status(models.TextChoices):
        SAVED = 'saved', 'Saved'
        APPLIED = 'applied', 'Applied'
        ROLL_NUMBER = 'roll_number', 'Roll Number Received'
        TEST_SCHEDULED = 'test_scheduled', 'Test Scheduled'
        INTERVIEW = 'interview', 'Interview'
        SELECTED = 'selected', 'Selected'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_applications')
    job = models.ForeignKey('JobListing', on_delete=models.CASCADE, related_name='applications')
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SAVED)
    roll_number = models.CharField(max_length=100, blank=True, default='')
    test_date = models.DateTimeField(null=True, blank=True)
    test_venue = models.CharField(max_length=300, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    reminder_sent = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_at']
        unique_together = ['user', 'job']

    def __str__(self):
        return f"{self.user.username} — {self.job.title} ({self.get_status_display()})"


class ServicePlan(models.Model):
    """Paid job application submission service plans."""

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price in PKR')
    applications_included = models.PositiveIntegerField(help_text='Number of applications included')
    validity_days = models.PositiveIntegerField(null=True, blank=True, help_text='Days of validity (null for monthly)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} — Rs. {self.price}"


class ApplicationRequest(models.Model):
    """User's paid application submission request handled by admin."""

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    class PaymentMethod(models.TextChoices):
        JAZZCASH = 'jazzcash', 'JazzCash'
        EASYPAISA = 'easypaisa', 'EasyPaisa'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        MANUAL = 'manual', 'Manual'

    class RequestStatus(models.TextChoices):
        PAYMENT_PENDING = 'payment_pending', 'Payment Pending'
        PAYMENT_VERIFICATION = 'payment_verification', 'Payment Verification'
        QUEUED = 'queued', 'Queued'
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_requests')
    job = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='service_requests')
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT, related_name='requests', null=True, blank=True)
    profile_snapshot = models.JSONField(default=dict, blank=True, help_text='Snapshot of user profile at request time')
    special_instructions = models.TextField(blank=True, default='', help_text='User notes for the submission')

    # Payment
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True, default='')
    payment_reference = models.CharField(max_length=100, blank=True, default='', help_text='Transaction ID / reference number')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_screenshot = models.ImageField(upload_to='service_payments/', blank=True, null=True, help_text='Payment proof screenshot')

    # Request tracking
    request_status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.PAYMENT_PENDING)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_requests')
    submission_screenshot = models.ImageField(upload_to='service_submissions/', blank=True, null=True, help_text='Proof of submission')
    submission_reference = models.CharField(max_length=100, blank=True, default='', help_text='Application number after submission')
    submitted_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default='', help_text='Reason if submission failed')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.job.title} ({self.get_request_status_display()})"


class AdminNote(models.Model):
    """Internal notes added by admins on application requests."""

    request = models.ForeignKey(ApplicationRequest, on_delete=models.CASCADE, related_name='admin_notes')
    note = models.TextField()
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_notes_added')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.request.id} by {self.added_by.username}"
