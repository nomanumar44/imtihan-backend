from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'exams', views.ExamViewSet)
router.register(r'subjects', views.SubjectViewSet)
router.register(r'mcqs', views.MCQViewSet)
router.register(r'past-papers', views.PastPaperViewSet)
router.register(r'syllabus', views.SyllabusViewSet)
router.register(r'jobs', views.JobListingViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'test-results', views.TestResultViewSet)
router.register(r'activity-log', views.ActivityLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
    path('dashboard/recent-mcqs/', views.recent_mcqs, name='dashboard-recent-mcqs'),
    path('dashboard/recent-activity/', views.recent_activity, name='dashboard-recent-activity'),
    path('mcqs/bulk-upload/', views.bulk_upload_mcqs, name='bulk-upload-mcqs'),
    path('auth/login/', views.student_login, name='api-login'),
    path('auth/signup/', views.student_signup, name='api-signup'),
    path('auth/google/', views.google_login, name='api-google-login'),
    path('user/dashboard/', views.user_dashboard_stats, name='api-user-dashboard'),
    path('user/tests/', views.user_recent_tests, name='api-user-tests'),
    path('user/quick-practice/', views.quick_practice, name='api-quick-practice'),
    path('user/progress/', views.user_progress, name='api-user-progress'),
    path('user/gamification/', views.user_gamification, name='api-user-gamification'),
    path('user/achievements/', views.user_achievements, name='api-user-achievements'),
    path('user/goals/', views.user_goals, name='api-user-goals'),
    path('user/profile/', views.user_profile, name='api-user-profile'),
    path('user/change-password/', views.change_password, name='api-change-password'),
    path('user/delete-account/', views.delete_account, name='api-delete-account'),
    path('notifications/', views.notifications_list, name='api-notifications'),
    path('notifications/mark-read/', views.mark_notifications_read, name='api-mark-notifications-read'),
    path('user/tests/<int:test_id>/', views.test_detail, name='api-test-detail'),
    path('user/tests/submit/', views.submit_test, name='api-submit-test'),
    path('leaderboard/', views.leaderboard, name='api-leaderboard'),
    path('user/bookmarks/', views.user_bookmarks, name='api-user-bookmarks'),
    path('user/bookmarks/<int:bookmark_id>/', views.delete_bookmark, name='api-delete-bookmark'),
    path('subscribe/', views.subscribe_email, name='api-subscribe'),
    path('news-subscribe/', views.news_subscribe, name='api-news-subscribe'),
    path('unsubscribe/<str:token>/', views.news_unsubscribe, name='api-news-unsubscribe'),
    path('search/', views.global_search, name='api-global-search'),
    path('posts/', views.posts_list, name='api-posts-list'),
    path('posts/featured/', views.posts_featured, name='api-posts-featured'),
    path('posts/related/<str:slug>/', views.posts_related, name='api-posts-related'),
    path('posts/<str:slug>/', views.post_detail, name='api-post-detail'),
    path('posts/<str:slug>/comments/', views.post_comments, name='api-post-comments'),
    path('posts/<str:slug>/comments/create/', views.create_comment, name='api-create-comment'),
    path('categories/', views.categories_list, name='api-categories-list'),
    path('frontend/home/', views.frontend_home, name='api-frontend-home'),
    path('frontend/announcements/', views.frontend_announcements, name='api-frontend-announcements'),
    path('frontend/current-affairs/', views.current_affairs_months, name='api-current-affairs-months'),
    path('frontend/current-affairs/topics/', views.frontend_current_affairs_topics, name='api-current-affairs-topics'),
    path('frontend/current-affairs/category/<str:slug>/', views.frontend_current_affairs_category_detail, name='api-current-affairs-category-detail'),
    path('frontend/current-affairs/<str:year>/<str:month>/', views.current_affairs_detail, name='api-current-affairs-detail'),
    path('frontend/mcq-tests/subjects/', views.frontend_mcq_subjects, name='api-frontend-mcq-subjects'),
    path('frontend/mcq-tests/subjects/<str:subject_slug>/', views.frontend_mcq_sets, name='api-frontend-mcq-sets'),
    path('frontend/mcq-tests/subjects/<str:subject_slug>/questions/', views.frontend_mcq_subject_questions, name='api-frontend-mcq-subject-questions'),
    path('frontend/mcq-tests/subjects/<str:subject_slug>/sets/<str:set_id>/', views.frontend_mcq_set_detail, name='api-frontend-mcq-set-detail'),
    path('frontend/mcq-tests/mock/<str:job_slug>/', views.frontend_mock_test, name='api-frontend-mock-test'),
    path('frontend/past-papers/menu/', views.frontend_past_papers_menu, name='api-past-papers-menu'),
    path('frontend/past-papers/', views.frontend_past_papers_list, name='api-past-papers-list'),
    path('frontend/past-papers/<slug:slug>/', views.frontend_past_paper_detail, name='api-past-paper-detail'),
    path('frontend/past-papers/<slug:slug>/pdf/', views.frontend_past_paper_pdf, name='api-past-paper-pdf'),
    path('frontend/syllabus/', views.frontend_syllabus_list, name='api-frontend-syllabus-list'),
    path('frontend/syllabus/<slug:slug>/', views.frontend_syllabus_detail, name='api-frontend-syllabus-detail'),
    path('frontend/contact/', views.frontend_contact, name='api-frontend-contact'),
    path('admin/quick-post/', views.quick_post, name='api-quick-post'),
    path('admin/quick-post/recent/', views.quick_post_recent, name='api-quick-post-recent'),
    path('ai/chat/', views.ai_chat, name='api-ai-chat'),
    path('ai/usage/', views.ai_usage, name='api-ai-usage'),
    path('ai/diagnostic/', views.ai_diagnostic, name='api-ai-diagnostic'),
    path('ai/subscribe/', views.ai_subscribe, name='api-ai-subscribe'),
    path('ai/subscription/', views.ai_subscription_status, name='api-ai-subscription'),
    path('ai/sessions/', views.ai_sessions, name='api-ai-sessions'),
    path('ai/session/<uuid:session_id>/', views.ai_session_detail, name='api-ai-session'),

    # Job Application Assistant
    path('user/job-profile/', views.user_job_profile, name='api-job-profile'),
    path('user/education/', views.user_education, name='api-user-education'),
    path('user/education/<int:pk>/', views.user_education_detail, name='api-user-education-detail'),
    path('user/experience/', views.user_experience, name='api-user-experience'),
    path('user/experience/<int:pk>/', views.user_experience_detail, name='api-user-experience-detail'),
    path('user/documents/', views.user_documents, name='api-user-documents'),
    path('user/documents/<int:pk>/', views.user_document_detail, name='api-user-document-detail'),
    path('applications/', views.user_applications, name='api-user-applications'),
    path('applications/<int:pk>/', views.user_application_detail, name='api-user-application-detail'),
    path('applications/<int:pk>/delete/', views.user_application_delete, name='api-user-application-delete'),
    path('applications/eligible/', views.eligible_jobs, name='api-eligible-jobs'),
    path('jobs/<int:pk>/eligibility/', views.job_eligibility, name='api-job-eligibility'),
    path('applications/<int:pk>/generate-package/', views.generate_application_package, name='api-generate-package'),

    # Paid Application Service
    path('service/plans/', views.service_plans, name='api-service-plans'),
    path('service/request/', views.create_service_request, name='api-service-request'),
    path('service/requests/', views.user_service_requests, name='api-user-service-requests'),
    path('admin/requests/', views.admin_service_requests, name='api-admin-service-requests'),
    path('admin/requests/<int:pk>/', views.admin_update_request, name='api-admin-update-request'),
    path('admin/requests/<int:pk>/note/', views.admin_add_note, name='api-admin-add-note'),
]
