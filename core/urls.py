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
]
