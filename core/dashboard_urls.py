from django.urls import path
from . import dashboard_views

urlpatterns = [
    path('', dashboard_views.dashboard_home, name='dashboard_home'),
    path('login/', dashboard_views.dashboard_login, name='dashboard_login'),
    path('logout/', dashboard_views.dashboard_logout, name='dashboard_logout'),
    path('mcqs/', dashboard_views.dashboard_mcqs, name='dashboard_mcqs'),
    path('mcqs/create/', dashboard_views.dashboard_mcq_create, name='dashboard_mcq_create'),
    
    path('past-papers/', dashboard_views.dashboard_past_papers, name='dashboard_past_papers'),
    path('past-papers/upload/', dashboard_views.dashboard_past_paper_create, name='dashboard_past_paper_create'),
    path('past-papers/<int:pk>/edit/', dashboard_views.dashboard_past_paper_edit, name='dashboard_past_paper_edit'),
    
    path('syllabus/', dashboard_views.dashboard_syllabus, name='dashboard_syllabus'),
    path('syllabus/create/', dashboard_views.dashboard_syllabus_create, name='dashboard_syllabus_create'),
    path('syllabus/<int:pk>/edit/', dashboard_views.dashboard_syllabus_edit, name='dashboard_syllabus_edit'),
    
    path('jobs/', dashboard_views.dashboard_jobs, name='dashboard_jobs'),
    path('jobs/create/', dashboard_views.dashboard_job_create, name='dashboard_job_create'),
    path('jobs/<int:pk>/edit/', dashboard_views.dashboard_job_edit, name='dashboard_job_edit'),
    
    path('students/', dashboard_views.dashboard_students, name='dashboard_students'),
    path('test-results/', dashboard_views.dashboard_test_results, name='dashboard_test_results'),
    path('settings/', dashboard_views.dashboard_settings, name='dashboard_settings'),
    path('scrape/', dashboard_views.dashboard_trigger_scrape, name='dashboard_trigger_scrape'),
    path('scraper/', dashboard_views.dashboard_scraper, name='dashboard_scraper'),
    path('scraper/status/', dashboard_views.dashboard_scraper_status, name='dashboard_scraper_status'),
]
