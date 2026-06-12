"""Application Package PDF generator for ImtihanHub Job Application Assistant."""

import io
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, Image, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from django.contrib.auth.models import User
from .models import JobListing, JobApplication, UserProfile, UserEducation, UserExperience, UserDocument


def generate_application_package(user: User, job: JobListing) -> bytes:
    """
    Generate a PDF application package checklist for a user and job.
    Returns the PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#0B2A3C'),
        spaceAfter=18,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#10b981'),
        spaceAfter=10,
        spaceBefore=16,
        fontName='Helvetica-Bold',
    )
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#0B2A3C'),
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        alignment=TA_LEFT,
    )
    warning_style = ParagraphStyle(
        'WarningStyle',
        parent=styles['BodyText'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#dc2626'),
        backColor=colors.HexColor('#fef2f2'),
        borderColor=colors.HexColor('#fecaca'),
        borderWidth=1,
        borderPadding=8,
        alignment=TA_JUSTIFY,
    )
    info_box_style = ParagraphStyle(
        'InfoBox',
        parent=styles['BodyText'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#92400e'),
        backColor=colors.HexColor('#fffbeb'),
        borderColor=colors.HexColor('#fcd34d'),
        borderWidth=1,
        borderPadding=8,
        alignment=TA_JUSTIFY,
    )
    checklist_style = ParagraphStyle(
        'Checklist',
        parent=styles['BodyText'],
        fontSize=10,
        leading=16,
        textColor=colors.HexColor('#334155'),
        leftIndent=20,
    )

    story = []

    # ─── HEADER ───
    story.append(Paragraph('<b>ImtihanHub</b>', ParagraphStyle(
        'Brand', fontSize=10, textColor=colors.HexColor('#10b981'),
        alignment=TA_CENTER, spaceAfter=4,
    )))
    story.append(Paragraph('Government Job Application Package', title_style))
    story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#10b981'), spaceAfter=12))

    # ─── JOB DETAILS BOX ───
    job_data = [
        ['<b>Job Title:</b>', job.title],
        ['<b>Department:</b>', job.department or '—'],
        ['<b>Location:</b>', job.location or '—'],
        ['<b>BPS Grade:</b>', job.bps_grade or '—'],
        ['<b>Vacancies:</b>', str(job.vacancies) if job.vacancies else '—'],
        ['<b>Last Date to Apply:</b>', str(job.last_date) if job.last_date else '—'],
        ['<b>Salary Range:</b>', job.salary_range or '—'],
    ]
    job_table = Table(job_data, colWidths=[5 * cm, 10 * cm])
    job_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0B2A3C')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#334155')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('ROUNDNAME', (0, 0), (-1, -1), 6),
    ]))
    story.append(job_table)
    story.append(Spacer(1, 14))

    # ─── USER PROFILE ───
    story.append(Paragraph('Applicant Information', heading_style))

    try:
        profile = user.job_profile
        profile_data = [
            ['<b>Full Name:</b>', profile.full_name or '—'],
            ["<b>Father's Name:</b>", profile.father_name or '—'],
            ['<b>CNIC:</b>', profile.cnic or '—'],
            ['<b>Date of Birth:</b>', str(profile.dob) if profile.dob else '—'],
            ['<b>Gender:</b>', profile.get_gender_display() if profile.gender else '—'],
            ['<b>Religion:</b>', profile.get_religion_display() if profile.religion else '—'],
            ['<b>Domicile:</b>', profile.get_domicile_display() if profile.domicile else '—'],
            ['<b>Phone:</b>', profile.phone or '—'],
            ['<b>WhatsApp:</b>', profile.whatsapp_number or '—'],
            ['<b>Permanent Address:</b>', profile.permanent_address or '—'],
            ['<b>Current Address:</b>', profile.current_address or '—'],
        ]
    except UserProfile.DoesNotExist:
        profile_data = [
            ['<b>Full Name:</b>', user.get_full_name() or user.username],
            ['<b>Status:</b>', '<font color="#dc2626">Profile not completed. Please complete your profile first.</font>'],
        ]

    profile_table = Table(profile_data, colWidths=[5 * cm, 10 * cm])
    profile_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0B2A3C')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#334155')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(profile_table)
    story.append(Spacer(1, 14))

    # ─── EDUCATION ───
    story.append(Paragraph('Education', heading_style))
    educations = list(user.educations.all())
    if educations:
        edu_headers = ['Level', 'Board / University', 'Year', 'Marks', 'Grade']
        edu_rows = [edu_headers]
        for edu in educations:
            edu_rows.append([
                edu.get_level_display(),
                edu.board_university or '—',
                str(edu.passing_year) if edu.passing_year else '—',
                f"{edu.obtained_marks or '—'} / {edu.total_marks or '—'}" if edu.obtained_marks and edu.total_marks else '—',
                edu.grade or '—',
            ])
        edu_table = Table(edu_rows, colWidths=[3 * cm, 5.5 * cm, 2 * cm, 2.5 * cm, 2 * cm])
        edu_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(edu_table)
    else:
        story.append(Paragraph('<i>No education records found.</i>', body_style))
    story.append(Spacer(1, 14))

    # ─── EXPERIENCE ───
    experiences = list(user.experiences.all())
    if experiences:
        story.append(Paragraph('Work Experience', heading_style))
        exp_headers = ['Organization', 'Designation', 'From', 'To', 'Current']
        exp_rows = [exp_headers]
        for exp in experiences:
            exp_rows.append([
                exp.organization,
                exp.designation,
                str(exp.from_date),
                str(exp.to_date) if exp.to_date else 'Present',
                'Yes' if exp.is_current else 'No',
            ])
        exp_table = Table(exp_rows, colWidths=[4.5 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm, 1.5 * cm])
        exp_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(exp_table)
        story.append(Spacer(1, 14))

    # ─── DOCUMENT CHECKLIST ───
    story.append(Paragraph('Required Documents Checklist', heading_style))

    # Determine which documents are needed based on job requirements
    doc_checklist = []

    # Always required
    doc_checklist.append(('☐ CNIC (Front & Back Copy)', True, 'Required for all applications'))
    doc_checklist.append(('☐ Recent Passport Size Photographs', True, 'Usually 2-4 photos required'))

    # Domicile check
    if job.domicile_requirement:
        doc_checklist.append((
            f"☐ Domicile Certificate ({dict(UserProfile.Domicile.choices).get(job.domicile_requirement, job.domicile_requirement)})",
            True,
            'Required for this job posting',
        ))
    else:
        doc_checklist.append(('☐ Domicile Certificate', False, 'Recommended if applicable'))

    # Education documents
    if job.min_education:
        doc_checklist.append((
            f"☐ Education Certificates ({dict(UserEducation.Level.choices).get(job.min_education, job.min_education)} or higher)",
            True,
            'Minimum education proof required',
        ))

    # Experience documents
    if job.min_experience_years is not None and job.min_experience_years > 0:
        doc_checklist.append((
            f"☐ Experience Certificates ({job.min_experience_years}+ years)",
            True,
            'Experience letters from previous employers required',
        ))

    # Additional common docs
    doc_checklist.append(('☐ Character Certificate', False, 'May be required'))
    doc_checklist.append(('☐ NOC (if already employed)', False, 'Required for government servants'))

    # Build checklist table
    checklist_data = []
    for doc_text, is_required, note in doc_checklist:
        checkbox = '☒' if is_required else '☐'
        color = '#dc2626' if is_required else '#64748b'
        checklist_data.append([
            Paragraph(f'<font color="{color}"><b>{checkbox}</b></font> {doc_text}', body_style),
            Paragraph(f'<i>{note}</i>', ParagraphStyle('Note', fontSize=8, textColor=colors.HexColor('#94a3b8'))),
        ])

    for row in checklist_data:
        story.append(row[0])
        story.append(row[1])
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 10))

    # ─── USER UPLOADED DOCUMENTS ───
    user_docs = list(user.job_documents.all())
    if user_docs:
        story.append(Paragraph('Your Uploaded Documents', subheading_style))
        for doc in user_docs:
            status = '✓ Uploaded' if doc.file else '✗ Missing'
            color = '#10b981' if doc.file else '#dc2626'
            story.append(Paragraph(
                f'<font color="{color}"><b>{status}</b></font> {doc.get_doc_type_display()}',
                body_style,
            ))
        story.append(Spacer(1, 10))

    # ─── INSTRUCTIONS ───
    story.append(Paragraph('Application Instructions', heading_style))
    instructions = []
    if job.how_to_apply and isinstance(job.how_to_apply, list):
        for step in job.how_to_apply:
            instructions.append(f'• {step}')
    else:
        instructions = [
            '• Read the official advertisement carefully before applying.',
            '• Fill the application form as per the given format.',
            '• Attach all required documents in the specified order.',
            '• Pay the application fee through the prescribed challan form.',
            '• Submit the application before the last date.',
            '• Keep a photocopy of the complete application for your record.',
        ]

    for instr in instructions:
        story.append(Paragraph(instr, body_style))
    story.append(Spacer(1, 10))

    # Fee / submission details
    if job.apply_link:
        story.append(Paragraph(
            f'<b>Apply Online:</b> <a href="{job.apply_link}" color="blue">{job.apply_link}</a>',
            body_style,
        ))
    story.append(Spacer(1, 10))

    # ─── DISCLAIMER BOXES ───
    story.append(Paragraph(
        '<b>⚠️ IMPORTANT DISCLAIMER:</b> Verify all information before submission. '
        'ImtihanHub provides this checklist as a helper tool only. We are not responsible for '
        'errors, omissions, or missed deadlines. You are solely responsible for submitting your '
        'application correctly and on time. Always refer to the official job advertisement.',
        warning_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        '<b>ℹ️ Helper Checklist Only:</b> This document is generated automatically from your profile. '
        'Please cross-check every detail with your original documents and the official job notice. '
        'Requirements may change — visit the official website for the latest instructions.',
        info_box_style,
    ))
    story.append(Spacer(1, 10))

    # ─── FOOTER ───
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceBefore=10, spaceAfter=6))
    story.append(Paragraph(
        f'<font size="8" color="#94a3b8">Generated by ImtihanHub on {date.today().strftime("%d %B %Y")} '
        f'| Job Application Assistant | imtihanhub.com</font>',
        ParagraphStyle('Footer', alignment=TA_CENTER, fontSize=8, textColor=colors.HexColor('#94a3b8')),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
