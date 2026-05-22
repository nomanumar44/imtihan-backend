"""
Custom admin views for bulk MCQ upload.
"""

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction

from .models import Exam, Subject, MCQ
from .mcq_parser import parse_mcq_text


@staff_member_required
def bulk_upload_mcq(request):
    exams = Exam.objects.all()
    subjects = Subject.objects.all()

    if request.method == 'POST':
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        raw_text = request.POST.get('raw_text', '').strip()
        status = request.POST.get('status', 'draft')
        source_url = request.POST.get('source_url', '').strip()

        if not exam_id or not subject_id:
            messages.error(request, "Please select Exam and Subject.")
            return render(request, 'admin/bulk_upload_mcq.html', {
                'exams': exams, 'subjects': subjects,
                'raw_text': raw_text, 'source_url': source_url,
                'status': status,
            })

        exam = Exam.objects.filter(pk=exam_id).first()
        subject = Subject.objects.filter(pk=subject_id).first()
        if not exam or not subject:
            messages.error(request, "Invalid Exam or Subject selected.")
            return render(request, 'admin/bulk_upload_mcq.html', {
                'exams': exams, 'subjects': subjects,
                'raw_text': raw_text, 'source_url': source_url,
                'status': status,
            })

        text = raw_text
        if not text:
            messages.error(request, "Please paste MCQ text.")
            return render(request, 'admin/bulk_upload_mcq.html', {
                'exams': exams, 'subjects': subjects,
                'raw_text': raw_text, 'source_url': source_url,
                'status': status,
            })

        parsed = parse_mcq_text(text)
        if not parsed:
            messages.warning(request, "No questions could be parsed from the input. Check formatting.")
            return render(request, 'admin/bulk_upload_mcq.html', {
                'exams': exams, 'subjects': subjects,
                'raw_text': raw_text, 'source_url': source_url,
                'status': status,
            })

        created_count = 0
        with transaction.atomic():
            for item in parsed:
                MCQ.objects.create(
                    question_text=item['question_text'],
                    option_a=item['option_a'],
                    option_b=item['option_b'],
                    option_c=item['option_c'],
                    option_d=item['option_d'],
                    correct_option=item['correct_option'] or 'A',
                    explanation=item['explanation'],
                    exam=exam,
                    subject=subject,
                    status=status,
                    source_url=source_url,
                    created_by=request.user,
                )
                created_count += 1

        messages.success(request, f"Successfully imported {created_count} MCQs.")
        return redirect(reverse('admin:core_mcq_changelist'))

    return render(request, 'admin/bulk_upload_mcq.html', {
        'exams': exams,
        'subjects': subjects,
    })
