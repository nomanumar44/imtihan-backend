from django import forms
from .models import JobListing, Syllabus, PastPaper, Exam, Subject, MCQ

class JobListingForm(forms.ModelForm):
    class Meta:
        model = JobListing
        fields = [
            'title', 'exam', 'department', 'location', 
            'bps_grade', 'description', 'qualifications', 
            'last_date', 'apply_link', 'status'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'department': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab Police'}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Punjab'}),
            'bps_grade': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., BPS-14'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Job description and details...'}),
            'qualifications': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Required qualifications...'}),
            'last_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'apply_link': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }


class SyllabusForm(forms.ModelForm):
    class Meta:
        model = Syllabus
        fields = ['title', 'exam', 'post_name', 'content', 'pdf_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector Syllabus'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'post_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Sub Inspector'}),
            'content': forms.Textarea(attrs={'class': 'form-input', 'rows': 6, 'placeholder': 'Syllabus topics and distribution...'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-input'}),
        }


class PastPaperForm(forms.ModelForm):
    class Meta:
        model = PastPaper
        fields = ['title', 'exam', 'subject', 'year', 'pdf_file', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., PPSC GK Past Paper 2024'}),
            'exam': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 2024'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }


class MCQForm(forms.ModelForm):
    class Meta:
        model = MCQ
        fields = [
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'explanation', 'exam', 'subject', 'status'
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
            'status': forms.Select(attrs={'class': 'form-input'}),
        }

