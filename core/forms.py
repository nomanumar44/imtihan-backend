from django import forms
from django.utils.text import slugify
from .models import JobListing, Syllabus, PastPaper, Exam, Subject, CurrentAffairsCategory, MCQ, Announcement, SectionContent, Post, Category, Tag, Testimonial, MockTestTemplate


class SectionContentForm(forms.ModelForm):
    class Meta:
        model = SectionContent
        fields = ['key', 'title', 'subtitle', 'is_active']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., exam_board'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Browse by exam board'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Pick your commission to see papers, syllabus & MCQs'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'type', 'color', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., CSS Updates'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto-generated from name if empty'}),
            'type': forms.Select(attrs={'class': 'form-input'}),
            'color': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '#10B981', 'type': 'color'}),
            'icon': forms.Select(attrs={'class': 'form-input'}, choices=[
                ('', '— Select Icon —'),
                ('BookOpen', 'BookOpen'),
                ('Book', 'Book'),
                ('Newspaper', 'Newspaper'),
                ('FileText', 'FileText'),
                ('PenTool', 'PenTool'),
                ('GraduationCap', 'GraduationCap'),
                ('Award', 'Award'),
                ('Trophy', 'Trophy'),
                ('Flag', 'Flag'),
                ('Globe', 'Globe'),
                ('MapPin', 'MapPin'),
                ('Landmark', 'Landmark'),
                ('Building', 'Building'),
                ('Star', 'Star'),
                ('Sparkles', 'Sparkles'),
                ('Lightbulb', 'Lightbulb'),
                ('Target', 'Target'),
                ('TrendingUp', 'TrendingUp'),
                ('BarChart', 'BarChart'),
                ('PieChart', 'PieChart'),
                ('Users', 'Users'),
                ('User', 'User'),
                ('Heart', 'Heart'),
                ('HelpCircle', 'HelpCircle'),
                ('Info', 'Info'),
                ('MessageCircle', 'MessageCircle'),
                ('Bell', 'Bell'),
                ('Calendar', 'Calendar'),
                ('Clock', 'Clock'),
                ('History', 'History'),
                ('Folder', 'Folder'),
                ('Layers', 'Layers'),
                ('Grid', 'Grid'),
                ('List', 'List'),
                ('Bookmark', 'Bookmark'),
                ('Tag', 'Tag'),
                ('Hash', 'Hash'),
                ('Search', 'Search'),
                ('Filter', 'Filter'),
                ('Menu', 'Menu'),
                ('MoreHorizontal', 'MoreHorizontal'),
            ]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['icon'].required = False
        self.fields['color'].required = True

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('name') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid category name or slug.')
        qs = Category.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A category with this slug already exists.')
        return slug

    def clean_color(self):
        color = self.cleaned_data.get('color', '').strip()
        if not color:
            return '#10B981'
        return color


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Pakistan Studies'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto-generated from name if empty'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('name') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid tag name or slug.')
        qs = Tag.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A tag with this slug already exists.')
        return slug


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'slug', 'description', 'icon', 'logo_url', 'badge_color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., PPSC'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto generated from name if empty'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab Public Service Commission'}),
            'icon': forms.Select(attrs={'class': 'form-input'}),
            'logo_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://example.com/logo.png'}),
            'badge_color': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('name') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid exam name or slug.')
        qs = Exam.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('An exam with this slug already exists.')
        return slug


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'slug', 'icon', 'logo_url', 'badge_color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., General Knowledge'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto generated from name if empty'}),
            'icon': forms.Select(attrs={'class': 'form-input'}),
            'logo_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://example.com/logo.png'}),
            'badge_color': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('name') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid subject name or slug.')
        qs = Subject.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A subject with this slug already exists.')
        return slug

class JobListingForm(forms.ModelForm):
    responsibilities = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input rich-text-editor', 'rows': 5, 'placeholder': 'Describe key responsibilities...'}),
        required=False,
        help_text='Use the editor to format responsibilities. They will be saved as rich text.'
    )
    how_to_apply = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input rich-text-editor', 'rows': 5, 'placeholder': 'Describe application steps...'}),
        required=False,
        help_text='Use the editor to format how-to-apply steps. They will be saved as rich text.'
    )

    class Meta:
        model = JobListing
        fields = [
            'title', 'exam', 'syllabus', 'department', 'location',
            'bps_grade', 'vacancies', 'salary_range', 'experience', 'age_limit',
            'description', 'qualifications', 'responsibilities', 'how_to_apply',
            'last_date', 'apply_link', 'advertisement_url', 'status',
            # Eligibility (used by the eligibility checker and job filters)
            'min_age', 'max_age', 'min_education', 'domicile_requirement',
            'gender_requirement', 'min_experience_years',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'syllabus': forms.Select(attrs={'class': 'form-input'}),
            'department': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab Police'}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab'}),
            'bps_grade': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., BPS-14'}),
            'vacancies': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 150', 'min': 1}),
            'salary_range': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Rs. 22,000 - 65,000/month'}),
            'experience': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Fresh candidates can apply'}),
            'age_limit': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 18-25 years (plus 5 years relaxation)'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Job description and details...'}),
            'qualifications': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Required qualifications...'}),
            'last_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'apply_link': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fields without an explicit widget above still get the dashboard input style.
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
        if self.instance and self.instance.pk:
            if isinstance(self.instance.responsibilities, list):
                self.fields['responsibilities'].initial = '\n'.join(self.instance.responsibilities)
            if isinstance(self.instance.how_to_apply, list):
                self.fields['how_to_apply'].initial = '\n'.join(self.instance.how_to_apply)

    def clean_responsibilities(self):
        text = self.cleaned_data.get('responsibilities', '')
        stripped = text.strip()
        return [stripped] if stripped else []

    def clean_how_to_apply(self):
        text = self.cleaned_data.get('how_to_apply', '')
        stripped = text.strip()
        return [stripped] if stripped else []


class SyllabusForm(forms.ModelForm):
    class Meta:
        model = Syllabus
        fields = ['title', 'slug', 'exam', 'post_name', 'bps_grade', 'marks', 'time', 'content', 'pdf_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector Syllabus'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto generated from title if empty'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'post_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector'}),
            'bps_grade': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., BPS-14'}),
            'marks': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 100', 'min': 1}),
            'time': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 90 minutes'}),
            'content': forms.Textarea(attrs={'class': 'form-input rich-text-editor', 'rows': 6, 'placeholder': 'Syllabus topics and distribution...'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-input'}),
        }


class PastPaperForm(forms.ModelForm):
    class Meta:
        model = PastPaper
        fields = ['title', 'slug', 'exam', 'subject', 'year', 'post_name', 'source_url', 'pdf_file', 'status']
        widgets = {
            'post_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Sub Inspector'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., PPSC GK Past Paper 2024'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto-generated from title + year if left empty'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 2024'}),
            'source_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        if not slug:
            title = self.cleaned_data.get('title', '')
            year = self.cleaned_data.get('year', '')
            base = f"{title}-{year}" if title and year else title or 'paper'
            slug = slugify(base)
        qs = PastPaper.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            # Append a counter to make unique
            original = slug
            counter = 1
            while PastPaper.objects.filter(slug=slug).exclude(pk=self.instance.pk if self.instance else None).exists():
                slug = f"{original}-{counter}"
                counter += 1
        return slug


class MCQForm(forms.ModelForm):
    class Meta:
        model = MCQ
        fields = [
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'explanation', 'exam', 'subject', 'topic', 'difficulty',
            'past_paper', 'current_affairs_category', 'event_date', 'source_url', 'status'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter question text...'}),
            'option_a': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option A'}),
            'option_b': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option B'}),
            'option_c': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option C'}),
            'option_d': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option D'}),
            'correct_option': forms.Select(attrs={'class': 'form-input'}),
            'explanation': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Explanation...'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'past_paper': forms.Select(attrs={'class': 'form-input'}),
            'current_affairs_category': forms.Select(attrs={'class': 'form-input'}),
            'topic': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Mughal Empire'}),
            'difficulty': forms.Select(attrs={'class': 'form-input'}),
            'event_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'source_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://… (where the answer was verified)'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('correct_option') == 'D' and not (cleaned.get('option_d') or '').strip():
            self.add_error('correct_option', "Correct option can't be D when option D is empty.")
        return cleaned


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ['name', 'city', 'exam', 'quote', 'rating', 'consent_confirmed', 'is_approved', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'city': forms.TextInput(attrs={'class': 'form-input'}),
            'exam': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'PPSC'}),
            'quote': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'rating': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 5}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-input'}),
        }

    def clean_rating(self):
        rating = self.cleaned_data['rating']
        if not 1 <= rating <= 5:
            raise forms.ValidationError('Rating must be between 1 and 5.')
        return rating

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_approved') and not cleaned.get('consent_confirmed'):
            self.add_error('is_approved', 'Confirm the student agreed to publication before approving.')
        return cleaned


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['text', 'url', 'placement', 'sort_order', 'is_active']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., PPSC Patwari 2025 roll no slips are available now.'
            }),
            'url': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Optional link e.g. /past-papers or https://...'
            }),
            'placement': forms.Select(attrs={'class': 'form-input'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class CurrentAffairsCategoryForm(forms.ModelForm):
    class Meta:
        model = CurrentAffairsCategory
        fields = ['name', 'slug', 'region', 'keywords', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Current Chief Justices'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Auto generated from name if empty'
            }),
            'region': forms.Select(attrs={'class': 'form-input'}),
            'keywords': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'chief justice, supreme court, ajk court'
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 0
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('name') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid category name or slug.')

        qs = CurrentAffairsCategory.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A category with this slug already exists.')
        return slug


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'slug', 'content', 'excerpt', 'thumbnail', 'category', 'tags', 'post_type', 'status', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Post title'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto-generated from title if empty'}),
            'content': forms.Textarea(attrs={'class': 'form-input rich-text-editor', 'rows': 15, 'placeholder': 'Write your post content here...'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Short summary for previews'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-input'}),
            'post_type': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['excerpt'].required = False
        self.fields['thumbnail'].required = False

    def clean_slug(self):
        raw_slug = self.cleaned_data.get('slug') or self.cleaned_data.get('title') or ''
        slug = slugify(raw_slug)
        if not slug:
            raise forms.ValidationError('Please enter a valid title or slug.')
        qs = Post.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A post with this slug already exists.')
        return slug


class MockTestTemplateForm(forms.ModelForm):
    """Edit a mock test; the subject mix is typed as one "subject-slug: count" per line."""

    breakdown_text = forms.CharField(
        label='Questions per subject',
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 7, 'placeholder': 'english: 20\ngeneral-knowledge: 30'}),
        help_text='One subject per line as "subject-slug: number of questions".',
    )

    class Meta:
        model = MockTestTemplate
        fields = ['title', 'slug', 'exam', 'description', 'duration_minutes', 'negative_marking', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ppsc-patwari'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.TextInput(attrs={'class': 'form-input'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'negative_marking': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.05', 'min': 0, 'max': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.breakdown:
            self.fields['breakdown_text'].initial = '\n'.join(f'{k}: {v}' for k, v in self.instance.breakdown.items())

    def clean_breakdown_text(self):
        breakdown, errors = {}, []
        known = set(Subject.objects.values_list('slug', flat=True))
        for line_no, line in enumerate(self.cleaned_data['breakdown_text'].splitlines(), start=1):
            if not line.strip():
                continue
            slug, sep, count = line.partition(':')
            slug = slug.strip()
            if not sep or not count.strip().isdigit() or int(count) <= 0:
                errors.append(f'Line {line_no}: use "subject-slug: number".')
            elif slug not in known:
                errors.append(f'Line {line_no}: unknown subject "{slug}".')
            else:
                breakdown[slug] = int(count)
        if errors:
            raise forms.ValidationError(errors)
        if not breakdown:
            raise forms.ValidationError('Add at least one subject.')
        if sum(breakdown.values()) > 200:
            raise forms.ValidationError('A mock test can have at most 200 questions.')
        return breakdown

    def clean_negative_marking(self):
        value = self.cleaned_data['negative_marking']
        if value < 0 or value > 1:
            raise forms.ValidationError('Use a value between 0 and 1 (e.g. 0.25).')
        return value

    def save(self, commit=True):
        self.instance.breakdown = self.cleaned_data['breakdown_text']
        return super().save(commit)
