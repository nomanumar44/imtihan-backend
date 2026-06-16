"""Job eligibility matching system for ImtihanHub."""

from datetime import date
from django.contrib.auth.models import User
from .models import JobListing, UserProfile, UserEducation, UserExperience

# Education hierarchy (higher index = higher qualification)
EDUCATION_ORDER = [
    'matric',
    'intermediate',
    'graduation',
    'masters',
    'mphil',
    'phd',
]


def get_user_highest_education(user: User):
    """Return the highest education level string for a user."""
    educations = user.educations.all()
    highest = None
    highest_idx = -1
    for edu in educations:
        idx = EDUCATION_ORDER.index(edu.level) if edu.level in EDUCATION_ORDER else -1
        if idx > highest_idx:
            highest_idx = idx
            highest = edu.level
    return highest, highest_idx


def get_user_total_experience_years(user: User) -> int:
    """Calculate total years of experience across all entries."""
    total_days = 0
    for exp in user.experiences.all():
        from_date = exp.from_date
        to_date = exp.to_date or date.today()
        if from_date and to_date:
            delta = (to_date - from_date).days
            if delta > 0:
                total_days += delta
    return round(total_days / 365)


def check_eligibility(user: User, job: JobListing) -> dict:
    """
    Check if a user is eligible for a job posting.

    Returns:
        {
            "is_eligible": bool,
            "reasons": [str],          # passed checks
            "failed_reasons": [str],   # failed checks
            "missing_info": [str],     # fields needed to determine
        }
    """
    reasons = []
    failed_reasons = []
    missing_info = []

    # ─── Fetch user profile ───
    try:
        profile = user.job_profile
    except UserProfile.DoesNotExist:
        profile = None

    # ─── Age check ───
    if job.min_age or job.max_age:
        if profile and profile.dob:
            age = (date.today() - profile.dob).days // 365
            age_pass = True
            if job.min_age and age < job.min_age:
                age_pass = False
                failed_reasons.append(
                    f"Age requirement: minimum {job.min_age} years (you are {age})"
                )
            if job.max_age and age > job.max_age:
                age_pass = False
                failed_reasons.append(
                    f"Age requirement: maximum {job.max_age} years (you are {age})"
                )
            if age_pass:
                reasons.append(f"Age: {age} years ✓")
        else:
            missing_info.append("Date of birth")
            if job.min_age and job.max_age:
                failed_reasons.append(
                    f"Age requirement: {job.min_age}-{job.max_age} years (missing DOB)"
                )
            elif job.min_age:
                failed_reasons.append(
                    f"Age requirement: minimum {job.min_age} years (missing DOB)"
                )
            elif job.max_age:
                failed_reasons.append(
                    f"Age requirement: maximum {job.max_age} years (missing DOB)"
                )

    # ─── Education check ───
    if job.min_education:
        highest_level, highest_idx = get_user_highest_education(user)
        job_idx = EDUCATION_ORDER.index(job.min_education) if job.min_education in EDUCATION_ORDER else -1
        if highest_level is not None:
            if highest_idx >= job_idx:
                reasons.append(
                    f"Education: {highest_level.title()} meets required {job.min_education.title()} ✓"
                )
            else:
                failed_reasons.append(
                    f"Education: requires {job.min_education.title()} (you have {highest_level.title()})"
                )
        else:
            missing_info.append("Education details")
            failed_reasons.append(
                f"Education: requires {job.min_education.title()} (no education added)"
            )

    # ─── Domicile check ───
    if job.domicile_requirement:
        if profile and profile.domicile:
            if profile.domicile == job.domicile_requirement:
                reasons.append(
                    f"Domicile: {profile.get_domicile_display()} ✓"
                )
            else:
                failed_reasons.append(
                    f"Domicile: requires {dict(UserProfile.Domicile.choices).get(job.domicile_requirement, job.domicile_requirement)} "
                    f"(you have {profile.get_domicile_display()})"
                )
        else:
            missing_info.append("Domicile")
            failed_reasons.append(
                f"Domicile: requires {dict(UserProfile.Domicile.choices).get(job.domicile_requirement, job.domicile_requirement)} (missing)"
            )

    # ─── Gender check ───
    if job.gender_requirement:
        if profile and profile.gender:
            if profile.gender == job.gender_requirement:
                reasons.append(
                    f"Gender: {profile.get_gender_display()} ✓"
                )
            else:
                failed_reasons.append(
                    f"Gender: requires {dict(UserProfile.Gender.choices).get(job.gender_requirement, job.gender_requirement)} "
                    f"(you are {profile.get_gender_display()})"
                )
        else:
            missing_info.append("Gender")
            failed_reasons.append(
                f"Gender: requires {dict(UserProfile.Gender.choices).get(job.gender_requirement, job.gender_requirement)} (missing)"
            )

    # ─── Experience check ───
    if job.min_experience_years is not None:
        user_years = get_user_total_experience_years(user)
        if user_years >= job.min_experience_years:
            reasons.append(
                f"Experience: {user_years} years (requires {job.min_experience_years}) ✓"
            )
        else:
            failed_reasons.append(
                f"Experience: requires {job.min_experience_years} years (you have {user_years})"
            )

    # ─── Overall eligibility ───
    is_eligible = len(failed_reasons) == 0 and len(missing_info) == 0

    # If we have no requirements set on the job, default to eligible
    has_requirements = any([
        job.min_age, job.max_age, job.min_education,
        job.domicile_requirement, job.gender_requirement,
        job.min_experience_years is not None,
    ])
    if not has_requirements:
        is_eligible = True
        reasons.append("No specific eligibility requirements set for this job ✓")

    return {
        "is_eligible": is_eligible,
        "reasons": reasons,
        "failed_reasons": failed_reasons,
        "missing_info": missing_info,
    }


def find_eligible_jobs(user: User):
    """
    Check all active jobs and return eligible ones + full eligibility details.
    Called after profile completion to notify user of matches.
    """
    from .models import JobListing
    jobs = JobListing.objects.filter(status=JobListing.Status.ACTIVE)
    results = []
    for job in jobs:
        result = check_eligibility(user, job)
        result['job_id'] = job.id
        result['job_title'] = job.title
        result['job_department'] = job.department
        result['job_location'] = job.location
        results.append(result)
    return results


def get_eligibility_badge(user: User, job: JobListing) -> dict:
    """
    Quick badge info for frontend display.
    Returns: { badge: 'eligible' | 'not_eligible' | 'incomplete', text: str }
    """
    result = check_eligibility(user, job)
    if result['missing_info']:
        return {
            'badge': 'incomplete',
            'text': 'Complete profile to check eligibility',
            'missing': result['missing_info'],
        }
    if result['is_eligible']:
        return {
            'badge': 'eligible',
            'text': 'You are Eligible',
            'reasons': result['reasons'],
        }
    return {
        'badge': 'not_eligible',
        'text': 'Not Eligible',
        'reasons': result['failed_reasons'],
    }
