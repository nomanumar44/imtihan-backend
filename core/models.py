from django.db import models
from django.contrib.auth.models import User


class Exam(models.Model):
    """Exam body like PPSC, FPSC, NTS, SPSC, etc."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    badge_color = models.CharField(
        max_length=10, default='green',
        help_text='Badge color class: green, blue, amber, red'
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
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='mcqs')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='mcqs')
    past_paper = models.ForeignKey(
        'PastPaper', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mcqs'
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
        max_length=10, choices=Status.choices, default=Status.DRAFT
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

    def __str__(self):
        return self.question_text[:80]


class PastPaper(models.Model):
    """Past paper PDF uploads"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True, blank=True, default='')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='past_papers')
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='past_papers',
        null=True, blank=True
    )
    year = models.PositiveIntegerField(default=0)
    pdf_file = models.FileField(upload_to='past_papers/', blank=True, null=True)
    source_url = models.URLField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
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


class Syllabus(models.Model):
    """Syllabus for an exam/post"""
    title = models.CharField(max_length=300)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='syllabi')
    post_name = models.CharField(max_length=200, blank=True, default='')
    content = models.TextField(help_text='Syllabus content in markdown or plain text')
    pdf_file = models.FileField(upload_to='syllabus/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Syllabi'

    def __str__(self):
        return self.title


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
    last_date = models.DateField(null=True, blank=True)
    apply_link = models.URLField(blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


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
