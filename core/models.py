from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


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
