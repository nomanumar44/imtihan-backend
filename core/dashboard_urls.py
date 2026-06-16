from django.urls import path
from . import dashboard_views

urlpatterns = [
    path('', dashboard_views.dashboard_home, name='dashboard_home'),
    path('login/', dashboard_views.dashboard_login, name='dashboard_login'),
    path('logout/', dashboard_views.dashboard_logout, name='dashboard_logout'),
    path('sections/', dashboard_views.dashboard_sections, name='dashboard_sections'),
    path('sections/<int:pk>/edit/', dashboard_views.dashboard_section_edit, name='dashboard_section_edit'),
    path('sections/<int:pk>/delete/', dashboard_views.dashboard_section_delete, name='dashboard_section_delete'),
    path('exams/', dashboard_views.dashboard_exams, name='dashboard_exams'),
    path('exams/<int:pk>/edit/', dashboard_views.dashboard_exam_edit, name='dashboard_exam_edit'),
    path('exams/<int:pk>/delete/', dashboard_views.dashboard_exam_delete, name='dashboard_exam_delete'),
    path('subjects/', dashboard_views.dashboard_subjects, name='dashboard_subjects'),
    path('subjects/<int:pk>/edit/', dashboard_views.dashboard_subject_edit, name='dashboard_subject_edit'),
    path('subjects/<int:pk>/delete/', dashboard_views.dashboard_subject_delete, name='dashboard_subject_delete'),
    path('mcqs/', dashboard_views.dashboard_mcqs, name='dashboard_mcqs'),
    path('mcqs/create/', dashboard_views.dashboard_mcq_create, name='dashboard_mcq_create'),
    path('mcqs/create/for-paper/<int:paper_pk>/', dashboard_views.dashboard_mcq_create_with_paper, name='dashboard_mcq_create_with_paper'),
    path('mcqs/bulk-upload/', dashboard_views.dashboard_mcq_bulk_upload, name='dashboard_mcq_bulk_upload'),
    path('mcqs/<int:pk>/edit/', dashboard_views.dashboard_mcq_edit, name='dashboard_mcq_edit'),
    path('mcqs/export/', dashboard_views.dashboard_mcq_export, name='dashboard_mcq_export'),
    path('mcqs/import/', dashboard_views.dashboard_mcq_import, name='dashboard_mcq_import'),
    path('current-affairs-categories/', dashboard_views.dashboard_current_affairs_categories, name='dashboard_current_affairs_categories'),
    path('current-affairs-categories/<int:pk>/edit/', dashboard_views.dashboard_current_affairs_category_edit, name='dashboard_current_affairs_category_edit'),
    path('current-affairs-categories/<int:pk>/delete/', dashboard_views.dashboard_current_affairs_category_delete, name='dashboard_current_affairs_category_delete'),
    
    path('past-papers/', dashboard_views.dashboard_past_papers, name='dashboard_past_papers'),
    path('past-papers/upload/', dashboard_views.dashboard_past_paper_create, name='dashboard_past_paper_create'),
    path('past-papers/<int:pk>/edit/', dashboard_views.dashboard_past_paper_edit, name='dashboard_past_paper_edit'),
    path('past-papers/<int:paper_pk>/mcqs/', dashboard_views.dashboard_paper_mcqs, name='dashboard_paper_mcqs'),
    
    path('syllabus/', dashboard_views.dashboard_syllabus, name='dashboard_syllabus'),
    path('syllabus/create/', dashboard_views.dashboard_syllabus_create, name='dashboard_syllabus_create'),
    path('syllabus/<int:pk>/edit/', dashboard_views.dashboard_syllabus_edit, name='dashboard_syllabus_edit'),
    
    path('jobs/', dashboard_views.dashboard_jobs, name='dashboard_jobs'),
    path('jobs/create/', dashboard_views.dashboard_job_create, name='dashboard_job_create'),
    path('jobs/<int:pk>/edit/', dashboard_views.dashboard_job_edit, name='dashboard_job_edit'),
    
    path('announcements/', dashboard_views.dashboard_announcements, name='dashboard_announcements'),
    path('announcements/<int:pk>/edit/', dashboard_views.dashboard_announcement_edit, name='dashboard_announcement_edit'),
    path('announcements/<int:pk>/delete/', dashboard_views.dashboard_announcement_delete, name='dashboard_announcement_delete'),

    path('students/', dashboard_views.dashboard_students, name='dashboard_students'),
    path('test-results/', dashboard_views.dashboard_test_results, name='dashboard_test_results'),
    path('settings/', dashboard_views.dashboard_settings, name='dashboard_settings'),
    path('scrape/', dashboard_views.dashboard_trigger_scrape, name='dashboard_trigger_scrape'),
    path('scraper/', dashboard_views.dashboard_scraper, name='dashboard_scraper'),
    path('scraper/status/', dashboard_views.dashboard_scraper_status, name='dashboard_scraper_status'),
    path('contact/', dashboard_views.dashboard_contact_messages, name='dashboard_contact_messages'),
    path('contact/<int:pk>/mark-read/', dashboard_views.dashboard_contact_mark_read, name='dashboard_contact_mark_read'),
    path('contact/<int:pk>/delete/', dashboard_views.dashboard_contact_delete, name='dashboard_contact_delete'),

    # Paid Application Service
    path('service-requests/', dashboard_views.dashboard_service_requests, name='dashboard_service_requests'),
    path('service-requests/<int:pk>/', dashboard_views.dashboard_service_request_detail, name='dashboard_service_request_detail'),

    # Job Profiles
    path('job-profiles/', dashboard_views.dashboard_job_profiles, name='dashboard_job_profiles'),
    path('job-profiles/<int:pk>/', dashboard_views.dashboard_job_profile_detail, name='dashboard_job_profile_detail'),

    # Blog
    path('posts/', dashboard_views.dashboard_posts, name='dashboard_posts'),
    path('posts/create/', dashboard_views.dashboard_post_create, name='dashboard_post_create'),
    path('posts/<int:pk>/edit/', dashboard_views.dashboard_post_edit, name='dashboard_post_edit'),
    path('posts/<int:pk>/', dashboard_views.dashboard_post_detail, name='dashboard_post_detail'),

    # News Subscribers
    path('news-subscribers/', dashboard_views.dashboard_news_subscribers, name='dashboard_news_subscribers'),

    # Service Plans
    path('service-plans/', dashboard_views.dashboard_service_plans, name='dashboard_service_plans'),

    # Comments
    path('comments/', dashboard_views.dashboard_comments, name='dashboard_comments'),

    # Categories
    path('categories/', dashboard_views.dashboard_categories, name='dashboard_categories'),

    # Tags
    path('tags/', dashboard_views.dashboard_tags, name='dashboard_tags'),

    # Activity Logs
    path('activity-logs/', dashboard_views.dashboard_activity_logs, name='dashboard_activity_logs'),

    # AI Usage
    path('ai-usage/', dashboard_views.dashboard_ai_usage, name='dashboard_ai_usage'),

    # Chat Sessions
    path('chat-sessions/', dashboard_views.dashboard_chat_sessions, name='dashboard_chat_sessions'),

    # Chat Messages
    path('chat-messages/', dashboard_views.dashboard_chat_messages, name='dashboard_chat_messages'),

    # Django Users
    path('django-users/', dashboard_views.dashboard_django_users, name='dashboard_django_users'),
]
