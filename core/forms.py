from django import forms
from django.utils.text import slugify
from .models import JobListing, Syllabus, PastPaper, Exam, Subject, CurrentAffairsCategory, MCQ, Announcement, SectionContent


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


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'slug', 'description', 'icon', 'badge_color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., PPSC'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto generated from name if empty'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab Public Service Commission'}),
            'icon': forms.Select(attrs={'class': 'form-input'}),
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
        fields = ['name', 'slug', 'icon', 'badge_color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., General Knowledge'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Auto generated from name if empty'}),
            'icon': forms.Select(attrs={'class': 'form-input'}),
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
            'last_date', 'apply_link', 'status'
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
        fields = ['title', 'slug', 'exam', 'subject', 'year', 'source_url', 'pdf_file', 'status']
        widgets = {
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
            'correct_option', 'explanation', 'exam', 'subject', 'past_paper',
            'current_affairs_category', 'status'
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
            'status': forms.Select(attrs={'class': 'form-input'}),
        }


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
