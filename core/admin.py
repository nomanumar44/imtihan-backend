from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import (
    Exam, Subject, CurrentAffairsCategory, MCQ, PastPaper, Syllabus,
    JobListing, Student, TestResult, ActivityLog, Announcement, SectionContent,
    Category, Tag, Post, PostImage, Comment, NewsSubscriber,
    AIUsage, ChatSession, ChatMessage, AISubscription,
    UserProfile, UserEducation, UserExperience, UserDocument, JobApplication,
    ServicePlan, ApplicationRequest, AdminNote,
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
        ('Eligibility Requirements', {'fields': [
            'min_age', 'max_age', 'min_education',
            'domicile_requirement', 'gender_requirement', 'min_experience_years',
        ], 'description': 'Leave fields blank to make them not required.'}),
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


# ── News & Blog Admin ────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'type', 'color_preview', 'post_count', 'created_at']
    list_filter = ['type']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 25
    list_display_links = ['name', 'slug']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'type'),
            'description': 'Set the category name and type. Slug auto-generates from name.'
        }),
        ('Appearance', {
            'fields': ('color', 'icon'),
            'description': 'Customize how this category appears on the site. Color is a hex code (e.g. #10B981). Icon is a Lucide icon name (e.g. BookOpen, Newspaper).'
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count('posts', distinct=True))

    def post_count(self, obj):
        return obj._post_count
    post_count.short_description = 'Posts'
    post_count.admin_order_field = '_post_count'

    def color_preview(self, obj):
        if obj.color:
            return format_html(
                '<span style="display:inline-flex; align-items:center; gap:6px;">'
                '<span style="display:inline-block; width:16px; height:16px; '
                'border-radius:4px; background:{}; border:1px solid #e5e7eb;"></span>'
                '<span style="font-family:monospace; font-size:12px;">{}</span>'
                '</span>',
                obj.color, obj.color
            )
        return '—'
    color_preview.short_description = 'Color'

    class Media:
        css = {
            'all': (
                'https://cdn.jsdelivr.net/npm/@simonwep/pickr@1.8.2/dist/themes/classic.min.css',
            ),
        }
        js = (
            'https://cdn.jsdelivr.net/npm/@simonwep/pickr@1.8.2/dist/pickr.min.js',
            'js/admin/color-picker.js',
        )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'post_count']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count('posts', distinct=True))

    def post_count(self, obj):
        return obj._post_count
    post_count.short_description = 'Posts'
    post_count.admin_order_field = '_post_count'


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ['image', 'caption', 'sort_order']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'post_type', 'status_badge', 'views_count',
                    'published_at', 'created_at', 'preview_button']
    list_filter = ['status', 'post_type', 'category', 'is_featured', 'created_at']
    search_fields = ['title', 'content', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    list_select_related = ['category', 'author']
    autocomplete_fields = ['category', 'tags']
    filter_horizontal = ['tags']
    readonly_fields = ['views_count', 'created_at', 'preview_button']
    inlines = [PostImageInline]
    actions = ['make_published', 'make_draft']
    change_form_template = 'admin/core/post/change_form.html'

    fieldsets = [
        (None, {
            'fields': ['title', 'slug', 'author', 'status', 'post_type', 'is_featured'],
        }),
        ('Content', {
            'fields': ['content', 'excerpt'],
        }),
        ('Media', {
            'fields': ['thumbnail', 'views_count'],
        }),
        ('Categorization', {
            'fields': ['category', 'tags'],
        }),
        ('Dates', {
            'fields': ['created_at', 'published_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'author')

    def status_badge(self, obj):
        colors = {
            Post.Status.DRAFT: '#9CA3AF',
            Post.Status.PUBLISHED: '#10B981',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            colors.get(obj.status, '#9CA3AF'),
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def preview_button(self, obj):
        return format_html(
            '<a href="{}" target="_blank" class="button" style="padding:4px 12px;background:#1f2937;color:white;text-decoration:none;border-radius:6px;font-size:12px;">Preview</a>',
            reverse('admin:core_post_preview', args=[obj.pk]),
        )
    preview_button.short_description = 'Preview'

    @admin.action(description='Publish selected posts')
    def make_published(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=Post.Status.DRAFT).update(
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.message_user(request, f'{updated} post(s) published.')

    @admin.action(description='Unpublish selected posts (set to draft)')
    def make_draft(self, request, queryset):
        updated = queryset.filter(status=Post.Status.PUBLISHED).update(
            status=Post.Status.DRAFT,
            published_at=None,
        )
        self.message_user(request, f'{updated} post(s) moved to draft.')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:post_id>/preview/', admin_views.post_preview, name='core_post_preview'),
        ]
        return custom + urls


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'post_title', 'email', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['name', 'email', 'content', 'post__title']
    list_editable = ['is_approved']
    actions = ['approve_comments']
    list_select_related = ['post']

    def post_title(self, obj):
        return obj.post.title
    post_title.short_description = 'Post'

    @admin.action(description='Approve selected comments')
    def approve_comments(self, request, queryset):
        updated = queryset.filter(is_approved=False).update(is_approved=True)
        self.message_user(request, f'{updated} comment(s) approved.')


@admin.register(NewsSubscriber)
class NewsSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'boards_list', 'is_active', 'subscribed_at']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email']
    filter_horizontal = ['boards']
    actions = ['deactivate_subscribers']

    def boards_list(self, obj):
        return ', '.join(b.name for b in obj.boards.all()) or 'All'
    boards_list.short_description = 'Boards'

    @admin.action(description='Deactivate selected subscribers')
    def deactivate_subscribers(self, request, queryset):
        updated = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{updated} subscriber(s) deactivated.')


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'questions_used', 'max_questions']
    list_filter = ['date']
    search_fields = ['user__username', 'user__email']


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['role', 'content', 'created_at']
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'mcq', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'session_id']
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']

    def content_preview(self, obj):
        return obj.content[:100]
    content_preview.short_description = 'Content'


@admin.register(AISubscription)
class AISubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'payment_method', 'phone', 'daily_limit', 'expires_at', 'created_at']
    list_filter = ['plan', 'status', 'payment_method']
    search_fields = ['user__username', 'user__email', 'phone']
    list_editable = ['plan', 'status']
    readonly_fields = ['created_at', 'updated_at']

    def daily_limit(self, obj):
        return obj.daily_limit
    daily_limit.short_description = 'Daily Limit'


# ─── Job Application Assistant Admin ───

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'cnic', 'domicile', 'gender', 'phone', 'is_profile_complete', 'created_at']
    list_filter = ['domicile', 'gender', 'is_profile_complete', 'created_at']
    search_fields = ['user__username', 'user__email', 'full_name', 'cnic', 'phone']
    list_select_related = ['user']
    fieldsets = [
        ('Personal Info', {'fields': ['user', 'full_name', 'father_name', 'cnic', 'dob', 'gender', 'religion', 'profile_photo']}),
        ('Contact & Address', {'fields': ['phone', 'whatsapp_number', 'permanent_address', 'current_address', 'domicile']}),
        ('Status', {'fields': ['is_profile_complete']}),
    ]


@admin.register(UserEducation)
class UserEducationAdmin(admin.ModelAdmin):
    list_display = ['user', 'level', 'board_university', 'passing_year', 'grade', 'percentage', 'created_at']
    list_filter = ['level', 'passing_year']
    search_fields = ['user__username', 'board_university']
    list_select_related = ['user']

    def percentage(self, obj):
        return obj.percentage()
    percentage.short_description = 'Percentage'


@admin.register(UserExperience)
class UserExperienceAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'designation', 'from_date', 'to_date', 'is_current']
    list_filter = ['is_current']
    search_fields = ['user__username', 'organization', 'designation']
    list_select_related = ['user']


@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    list_display = ['user', 'doc_type', 'file_link', 'uploaded_at']
    list_filter = ['doc_type', 'uploaded_at']
    search_fields = ['user__username']
    list_select_related = ['user']

    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View File</a>', obj.file.url)
        return '-'
    file_link.short_description = 'File'


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'job_title', 'status', 'roll_number', 'test_date', 'applied_at']
    list_filter = ['status', 'applied_at']
    search_fields = ['user__username', 'job__title', 'roll_number']
    list_select_related = ['user', 'job']
    readonly_fields = ['applied_at', 'updated_at']

    def job_title(self, obj):
        return obj.job.title
    job_title.short_description = 'Job'


# ─── Paid Application Service Admin ───

@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'applications_included', 'validity_days', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    list_editable = ['is_active']


class AdminNoteInline(admin.TabularInline):
    model = AdminNote
    extra = 1
    readonly_fields = ['added_by', 'created_at']
    fields = ['note', 'added_by', 'created_at']
    can_delete = False


@admin.register(ApplicationRequest)
class ApplicationRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'job_title', 'plan_name', 'request_status',
        'payment_status', 'assigned_to_name', 'created_at',
    ]
    list_filter = [
        'request_status', 'payment_status', 'payment_method',
        'created_at', 'plan',
    ]
    search_fields = ['user__username', 'user__email', 'job__title', 'payment_reference', 'submission_reference']
    list_select_related = ['user', 'job', 'plan', 'assigned_to']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at']
    inlines = [AdminNoteInline]
    fieldsets = [
        ('Request Info', {'fields': ['user', 'job', 'plan', 'request_status', 'assigned_to']}),
        ('Profile Snapshot', {'fields': ['profile_snapshot'], 'classes': ['collapse']}),
        ('Special Instructions', {'fields': ['special_instructions']}),
        ('Payment', {'fields': ['payment_status', 'payment_method', 'payment_reference', 'payment_amount', 'payment_screenshot']}),
        ('Submission', {'fields': ['submission_reference', 'submission_screenshot', 'submitted_at', 'failure_reason']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at']}),
    ]

    def job_title(self, obj):
        return obj.job.title
    job_title.short_description = 'Job'

    def plan_name(self, obj):
        return obj.plan.name if obj.plan else '—'
    plan_name.short_description = 'Plan'

    def assigned_to_name(self, obj):
        return obj.assigned_to.username if obj.assigned_to else 'Unassigned'
    assigned_to_name.short_description = 'Assigned'
