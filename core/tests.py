import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import resolve
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .gamification import compute_streak, level_for_xp
from .models import MCQ, DailyPracticeLog, Exam, Student, Subject, TestResult


def make_mcq(exam, subject, status='published', correct='B', text='Q'):
    return MCQ.objects.create(
        question_text=text, option_a='a', option_b='b', option_c='c', option_d='d',
        correct_option=correct, exam=exam, subject=subject, status=status,
    )


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='imtihan-test-media-')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BaseAPITest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.exam = Exam.objects.create(name='PPSC', slug='ppsc')
        self.subject = Subject.objects.create(name='English', slug='english')
        self.user = User.objects.create_user('student', 'student@example.com', 'pass12345')
        Student.objects.create(user=self.user, phone='03001234567')
        self.staff = User.objects.create_user('staff', 'staff@example.com', 'pass12345', is_staff=True)
        self.anon = APIClient()
        self.client_user = APIClient()
        self.client_user.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')
        self.client_staff = APIClient()
        self.client_staff.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.staff).key}')


class RouterPermissionTests(BaseAPITest):
    def test_public_can_read_but_not_write(self):
        self.assertEqual(self.anon.get('/api/exams/').status_code, 200)
        self.assertIn(self.anon.post('/api/exams/', {'name': 'X', 'slug': 'x'}).status_code, (401, 403))
        self.assertIn(self.client_user.delete('/api/exams/ppsc/').status_code, (401, 403))
        self.assertTrue(Exam.objects.filter(slug='ppsc').exists())

    def test_staff_can_write(self):
        mcq = make_mcq(self.exam, self.subject)
        res = self.client_staff.patch(f'/api/mcqs/{mcq.id}/', {'status': 'flagged'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_student_and_result_endpoints_are_staff_only(self):
        for url in ('/api/students/', '/api/test-results/', '/api/activity-log/', '/api/dashboard/stats/'):
            self.assertIn(self.anon.get(url).status_code, (401, 403), url)
            self.assertIn(self.client_user.get(url).status_code, (401, 403), url)
            self.assertEqual(self.client_staff.get(url).status_code, 200, url)

    def test_drafts_hidden_from_public(self):
        published = make_mcq(self.exam, self.subject, text='live')
        draft = make_mcq(self.exam, self.subject, status='draft', text='draft')
        ids = [m['id'] for m in self.anon.get('/api/mcqs/').json()['results']]
        self.assertIn(published.id, ids)
        self.assertNotIn(draft.id, ids)
        self.assertEqual(self.anon.get(f'/api/mcqs/{draft.id}/').status_code, 404)
        self.assertEqual(self.client_staff.get(f'/api/mcqs/{draft.id}/').status_code, 200)


class BulkUploadTests(BaseAPITest):
    def payload(self, **row):
        question = {'question_text': 'Capital?', 'option_a': 'x', 'option_b': 'y', 'option_c': 'z',
                    'option_d': '', 'correct_answer': 'Option B'}
        question.update(row)
        return {'board': 'ppsc', 'subject': 'english', 'status': 'published', 'questions': [question]}

    def test_route_is_not_shadowed_by_router(self):
        self.assertEqual(resolve('/api/mcqs/bulk-upload/').url_name, 'bulk-upload-mcqs')

    def test_requires_staff(self):
        self.assertIn(self.anon.post('/api/mcqs/bulk-upload/', self.payload(), format='json').status_code, (401, 403))
        self.assertIn(self.client_user.post('/api/mcqs/bulk-upload/', self.payload(), format='json').status_code, (401, 403))

    def test_creates_mcqs_and_reuses_subject(self):
        res = self.client_staff.post('/api/mcqs/bulk-upload/', self.payload(), format='json')
        self.assertEqual(res.status_code, 200, res.content)
        mcq = MCQ.objects.get(question_text='Capital?')
        self.assertEqual(mcq.correct_option, 'B')
        self.assertEqual(mcq.subject, self.subject)
        self.assertEqual(Subject.objects.count(), 1)

    def test_rejects_answer_pointing_at_empty_option(self):
        res = self.client_staff.post('/api/mcqs/bulk-upload/', self.payload(correct_answer='D'), format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(MCQ.objects.exists())


class ProfileTests(BaseAPITest):
    def test_client_cannot_set_xp_or_level(self):
        res = self.client_user.put('/api/user/profile/', {'xp_points': 99999, 'level': 50, 'city': 'Lahore'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        student = Student.objects.get(user=self.user)
        self.assertEqual((student.xp_points, student.level, student.city), (0, 1, 'Lahore'))


class SubmitTestTests(BaseAPITest):
    def submit(self, answers, **extra):
        body = {'answers': answers, 'correct_answers': 999, 'score_percent': 100, 'time_taken_seconds': 60}
        body.update(extra)
        return self.client_user.post('/api/user/tests/submit/', body, format='json')

    def test_score_is_computed_on_server(self):
        q1, q2 = make_mcq(self.exam, self.subject, correct='B'), make_mcq(self.exam, self.subject, correct='C')
        res = self.submit([
            {'question_id': q1.id, 'selected_option': 'B', 'is_correct': True},
            {'question_id': q2.id, 'selected_option': 'A', 'is_correct': True, 'correct_option': 'A'},
            {'question_id': q2.id, 'selected_option': 'C'},  # duplicate is ignored
        ])
        self.assertEqual(res.status_code, 200, res.content)
        result = TestResult.objects.get(id=res.json()['test_id'])
        self.assertEqual((result.total_questions, result.correct_answers, result.wrong_answers), (2, 1, 1))
        self.assertEqual(float(result.score_percent), 50.0)
        self.assertEqual(result.answers.get(question_id=q2.id).correct_option, 'C')
        # exam/subject inferred from the questions
        self.assertEqual((result.exam, result.subject), (self.exam, self.subject))

    def test_xp_awarded_once(self):
        q = make_mcq(self.exam, self.subject, correct='A')
        self.submit([{'question_id': q.id, 'selected_option': 'A'}])
        student = Student.objects.get(user=self.user)
        # 1 correct * 10 + test 10 + perfect 20 + first test of the day 5
        self.assertEqual(student.xp_points, 45)
        self.assertEqual((student.mcqs_today, student.tests_today, student.streak_days), (1, 1, 1))
        log = DailyPracticeLog.objects.get(user=self.user)
        self.assertEqual((log.mcqs_answered, log.tests_completed, log.xp_earned), (1, 1, 45))

    def test_empty_submission_rejected(self):
        self.assertEqual(self.submit([]).status_code, 400)


class AuthTests(BaseAPITest):
    def test_signup_enforces_password_rules_and_unique_email(self):
        base = {'email': 'New@Example.com', 'accept_terms': True}
        weak = self.anon.post('/api/auth/signup/', {**base, 'password': '123456', 'confirm_password': '123456'}, format='json')
        self.assertEqual(weak.status_code, 400)
        ok = self.anon.post('/api/auth/signup/', {**base, 'password': 'Lahore-2026!', 'confirm_password': 'Lahore-2026!'}, format='json')
        self.assertEqual(ok.status_code, 201, ok.content)
        dup = self.anon.post('/api/auth/signup/', {**base, 'email': 'new@example.com', 'password': 'Lahore-2026!', 'confirm_password': 'Lahore-2026!'}, format='json')
        self.assertEqual(dup.status_code, 400)
        taken = self.anon.post('/api/auth/signup/', {'email': 'x@example.com', 'username': 'student', 'accept_terms': True,
                                                      'password': 'Lahore-2026!', 'confirm_password': 'Lahore-2026!'}, format='json')
        self.assertEqual(taken.status_code, 400)

    def test_login_with_email_is_case_insensitive(self):
        res = self.anon.post('/api/auth/login/', {'username': 'STUDENT@example.com', 'password': 'pass12345'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_change_password_rotates_token(self):
        old_key = Token.objects.get(user=self.user).key
        res = self.client_user.post('/api/user/change-password/', {
            'current_password': 'pass12345', 'new_password': 'Karachi-2026!', 'confirm_password': 'Karachi-2026!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertNotEqual(res.json()['token'], old_key)
        self.assertFalse(Token.objects.filter(key=old_key).exists())

    def test_google_only_user_has_no_usable_password(self):
        google_user = User.objects.create_user('guser', 'g@example.com', password=None)
        Student.objects.create(user=google_user, google_id='123')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=google_user).key}')
        self.assertFalse(client.get('/api/user/profile/').json()['has_password'])
        # An empty password must not log in
        self.assertEqual(self.anon.post('/api/auth/login/', {'username': 'guser', 'password': ''}, format='json').status_code, 400)
        # They can set a first password without a current one
        res = client.post('/api/user/change-password/', {'new_password': 'Quetta-2026!', 'confirm_password': 'Quetta-2026!'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        google_user.refresh_from_db()
        self.assertTrue(google_user.check_password('Quetta-2026!'))

    def test_passwordless_account_delete_needs_confirmation(self):
        google_user = User.objects.create_user('guser2', 'g2@example.com', password=None)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=google_user).key}')
        self.assertEqual(client.post('/api/user/delete-account/', {}, format='json').status_code, 400)
        self.assertEqual(client.post('/api/user/delete-account/', {'confirm_text': 'delete'}, format='json').status_code, 200)
        self.assertFalse(User.objects.filter(username='guser2').exists())


def png_upload(name='proof.png'):
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (2, 2)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class CommentTests(BaseAPITest):
    def test_only_approved_comments_are_public_and_email_is_kept(self):
        from .models import Category, Comment, Post
        category = Category.objects.create(name='News', slug='news')
        post = Post.objects.create(title='T', slug='t', content='c', author=self.staff, category=category, status='published')
        Comment.objects.create(post=post, name='ok', email='a@b.c', content='visible', is_approved=True)
        Comment.objects.create(post=post, name='spam', email='a@b.c', content='hidden', is_approved=False)
        names = [c['name'] for c in self.anon.get('/api/posts/t/').json()['comments']]
        self.assertEqual(names, ['ok'])
        res = self.anon.post('/api/posts/t/comments/create/', {'name': 'N', 'email': 'n@example.com', 'content': 'hi'}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Comment.objects.get(name='N').email, 'n@example.com')


class DashboardAccessTests(BaseAPITest):
    def test_non_staff_session_is_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/dashboard/').status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)

    def test_subscription_approval_requires_post(self):
        from .models import AISubscription
        sub = AISubscription.objects.create(user=self.user, plan='pro', status='pending')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f'/dashboard/ai-subscriptions/{sub.pk}/approve/').status_code, 405)
        self.client.post(f'/dashboard/ai-subscriptions/{sub.pk}/approve/')
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'active')
        self.assertIsNotNone(sub.expires_at)


class QuickPostTests(BaseAPITest):
    def test_disabled_without_secret(self):
        with self.settings(QUICK_POST_SECRET=''):
            res = self.anon.get('/api/admin/quick-post/recent/', HTTP_X_ADMIN_TOKEN='')
            self.assertEqual(res.status_code, 403)

    def test_requires_matching_secret(self):
        with self.settings(QUICK_POST_SECRET='s3cret'):
            self.assertEqual(self.anon.get('/api/admin/quick-post/recent/', HTTP_X_ADMIN_TOKEN='nope').status_code, 403)
            self.assertEqual(self.anon.get('/api/admin/quick-post/recent/', HTTP_X_ADMIN_TOKEN='s3cret').status_code, 200)


class PaymentValidationTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        from .models import JobListing, ServicePlan
        self.job = JobListing.objects.create(title='Clerk', description='d', exam=self.exam)
        self.plan = ServicePlan.objects.create(name='Single', price='300.00', applications_included=1)

    def request_body(self, **extra):
        body = {'job': self.job.id, 'plan': self.plan.id, 'payment_method': 'jazzcash',
                'payment_reference': 'TX1', 'payment_amount': '1'}
        body.update(extra)
        return body

    def test_amount_comes_from_plan_and_screenshot_is_saved(self):
        res = self.client_user.post('/api/service/request/', {**self.request_body(), 'payment_screenshot': png_upload()}, format='multipart')
        self.assertEqual(res.status_code, 201, res.content)
        from .models import ApplicationRequest
        req = ApplicationRequest.objects.get()
        self.assertEqual(str(req.payment_amount), '300.00')
        self.assertTrue(req.payment_screenshot)
        self.assertEqual(req.request_status, 'payment_verification')

    def test_rejects_bad_method_and_reused_reference(self):
        self.assertEqual(self.client_user.post('/api/service/request/', self.request_body(payment_method='bitcoin'), format='json').status_code, 400)
        self.assertEqual(self.client_user.post('/api/service/request/', self.request_body(), format='json').status_code, 201)
        job2 = type(self.job).objects.create(title='Other', description='d')
        self.assertEqual(self.client_user.post('/api/service/request/', self.request_body(job=job2.id), format='json').status_code, 400)

    def test_failed_request_does_not_block_retry(self):
        self.client_user.post('/api/service/request/', self.request_body(), format='json')
        from .models import ApplicationRequest
        ApplicationRequest.objects.update(request_status='failed')
        res = self.client_user.post('/api/service/request/', self.request_body(payment_reference='TX2'), format='json')
        self.assertEqual(res.status_code, 201, res.content)

    def test_admin_update_validates_status(self):
        self.client_user.post('/api/service/request/', self.request_body(), format='json')
        from .models import ApplicationRequest
        req = ApplicationRequest.objects.get()
        self.assertEqual(self.client_staff.put(f'/api/admin/requests/{req.id}/', {'request_status': 'bogus'}, format='json').status_code, 400)
        res = self.client_staff.put(f'/api/admin/requests/{req.id}/', {'submission_screenshot': png_upload()}, format='multipart')
        self.assertEqual(res.status_code, 200, res.content)
        req.refresh_from_db()
        self.assertTrue(req.submission_screenshot)

    def test_active_ai_plan_is_not_reset_to_pending(self):
        from django.utils import timezone
        from .models import AISubscription
        AISubscription.objects.create(user=self.user, plan='pro', status='active', expires_at=timezone.now() + timedelta(days=20))
        res = self.client_user.post('/api/ai/subscribe/', {
            'plan': 'premium', 'payment_method': 'jazzcash', 'phone': '03001234567',
            'payment_reference': 'AI-1', 'payment_screenshot': png_upload(),
        }, format='multipart')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(AISubscription.objects.get(user=self.user).status, 'active')

    def test_ai_subscribe_rejects_non_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        res = self.client_user.post('/api/ai/subscribe/', {
            'plan': 'pro', 'payment_method': 'jazzcash', 'phone': '03001234567', 'payment_reference': 'AI-2',
            'payment_screenshot': SimpleUploadedFile('x.png', b'not an image', content_type='image/png'),
        }, format='multipart')
        self.assertEqual(res.status_code, 400)


class ContentEndpointTests(BaseAPITest):
    def test_home_jobs_link_by_id_and_detail_resolves(self):
        from .models import JobListing
        job = JobListing.objects.create(title='Inspector Customs', description='d', exam=self.exam)
        make_mcq(self.exam, self.subject)
        cache.delete('frontend_home')
        jobs = self.anon.get('/api/frontend/home/').json()['jobs']
        self.assertEqual(jobs[0]['slug'], str(job.id))
        self.assertEqual(self.anon.get(f"/api/jobs/{jobs[0]['slug']}/").status_code, 200)
        self.assertEqual(self.anon.get(f'/api/frontend/mcq-tests/mock/{job.id}/').json()['title'], 'Inspector Customs Mock Test')

    def test_past_paper_pdf_handles_unicode(self):
        from .models import PastPaper
        paper = PastPaper.objects.create(title='پنجاب Paper', slug='punjab-paper', exam=self.exam, year=2024, status='published')
        mcq = make_mcq(self.exam, self.subject, text='سوال: Capital?')
        mcq.past_paper = paper
        mcq.save()
        res = self.anon.get('/api/frontend/past-papers/punjab-paper/pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_current_affairs_daily_and_month_validation(self):
        ca = Subject.objects.create(name='Current Affairs', slug='current-affairs')
        make_mcq(self.exam, ca, text='Daily q')
        from django.utils import timezone
        today = timezone.localdate()
        res = self.anon.get(f'/api/frontend/current-affairs/daily/{today:%Y-%m-%d}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(sum(len(c['questions']) for c in res.json()['categories']), 1)
        self.assertEqual(self.anon.get('/api/frontend/current-affairs/daily/not-a-date/').status_code, 400)
        self.assertEqual(self.anon.get(f'/api/frontend/current-affairs/{today.year}/smarch/').status_code, 404)
        months = self.anon.get('/api/frontend/current-affairs/').json()
        self.assertEqual(months[str(today.year)][0]['count'], 1)

    def test_months_endpoint_is_empty_without_data(self):
        self.assertEqual(self.anon.get('/api/frontend/current-affairs/').json(), {})


class LeaderboardTests(BaseAPITest):
    def test_rank_uses_one_xp_source_and_includes_current_user(self):
        q = make_mcq(self.exam, self.subject, correct='A')
        self.client_user.post('/api/user/tests/submit/', {'answers': [{'question_id': q.id, 'selected_option': 'A'}]}, format='json')
        data = self.client_user.get('/api/leaderboard/?period=all_time').json()
        self.assertEqual(data['leaderboard'][0]['username'], 'student')
        self.assertEqual(data['leaderboard'][0]['xp_points'], Student.objects.get(user=self.user).xp_points)
        self.assertEqual(data['user_rank']['rank'], 1)
        weekly = self.client_user.get('/api/leaderboard/?period=weekly').json()
        self.assertEqual(weekly['leaderboard'][0]['xp_points'], 45)


class AIChatTests(BaseAPITest):
    def test_failed_answer_does_not_use_quota(self):
        from unittest import mock
        from .ai_service import GENERIC_ERROR_MSG
        from .models import AIUsage, ChatSession
        with mock.patch('core.ai_service.get_ai_response', return_value=GENERIC_ERROR_MSG):
            res = self.client_user.post('/api/ai/chat/', {'message': 'hi'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['failed'])
        self.assertEqual(AIUsage.objects.get(user=self.user).questions_used, 0)
        self.assertFalse(ChatSession.objects.exists())

        with mock.patch('core.ai_service.get_ai_response', return_value='An answer'):
            res = self.client_user.post('/api/ai/chat/', {'message': 'hi'}, format='json')
        self.assertFalse(res.json()['failed'])
        self.assertEqual(AIUsage.objects.get(user=self.user).questions_used, 1)

    def test_quota_enforced_and_bad_session_is_404(self):
        from unittest import mock
        from .models import AIUsage
        from django.utils import timezone
        AIUsage.objects.create(user=self.user, date=timezone.localdate(), questions_used=5, max_questions=5)
        with mock.patch('core.ai_service.get_ai_response', return_value='An answer'):
            self.assertEqual(self.client_user.post('/api/ai/chat/', {'message': 'hi'}, format='json').status_code, 403)
            self.assertEqual(self.client_user.post('/api/ai/chat/', {'message': 'hi', 'session_id': 'nope'}, format='json').status_code, 404)


class JobProfileTests(BaseAPITest):
    def test_education_can_be_updated_in_place(self):
        res = self.client_user.post('/api/user/education/', {'level': 'matric', 'board_university': 'BISE'}, format='json')
        edu_id = res.json()['id']
        res = self.client_user.put(f'/api/user/education/{edu_id}/', {'grade': 'A+'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self.client_user.get('/api/user/education/').json()[0]['grade'], 'A+')
        self.assertEqual(len(self.client_user.get('/api/user/education/').json()), 1)

    def test_document_upload_validates_type_and_uses_random_name(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile('cnic.exe', b'MZ', content_type='application/octet-stream')
        self.assertEqual(self.client_user.post('/api/user/documents/', {'doc_type': 'cnic_front', 'file': bad}, format='multipart').status_code, 400)
        res = self.client_user.post('/api/user/documents/', {'doc_type': 'intermediate_certificate', 'file': png_upload('cnic_front.png')}, format='multipart')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertNotIn('cnic_front', res.json()['file'])
        from .models import UserDocument
        UserDocument.objects.get().file.delete(save=False)


class ScrapeStoreTests(BaseAPITest):
    def fields(self, **extra):
        data = {'option_a': 'Lahore', 'option_b': 'Karachi', 'option_c': 'Quetta', 'option_d': '',
                'correct_option': 'A', 'exam': self.exam, 'subject': self.subject, 'status': 'published'}
        data.update(extra)
        return data

    def test_paper_slug_and_status_survive_rescrape(self):
        from .models import PastPaper
        from .utils.scrape_store import save_scraped_paper
        paper, created = save_scraped_paper('https://example.com/papers/1', 'PPSC Paper 2024', self.exam, self.subject, 2024)
        self.assertTrue(created)
        PastPaper.objects.filter(pk=paper.pk).update(status='draft')
        again, created = save_scraped_paper('https://example.com/papers/1', 'PPSC Paper 2024', self.exam, self.subject, 2024)
        self.assertFalse(created)
        self.assertEqual((again.slug, again.status), (paper.slug, 'draft'))

    def test_existing_mcq_is_not_overwritten_but_gets_linked(self):
        from .models import PastPaper
        from .utils.scrape_store import save_scraped_mcq
        mcq, _ = save_scraped_mcq('Capital of Punjab?', self.fields())
        MCQ.objects.filter(pk=mcq.pk).update(explanation='staff note', correct_option='A')
        paper = PastPaper.objects.create(title='P', slug='p', exam=self.exam, status='published')
        _, created = save_scraped_mcq('Capital of Punjab?', self.fields(correct_option='B'), past_paper=paper)
        mcq.refresh_from_db()
        self.assertFalse(created)
        self.assertEqual((mcq.correct_option, mcq.explanation, mcq.past_paper_id), ('A', 'staff note', paper.id))

    def test_placeholder_questions_are_drafts(self):
        from .utils.scrape_store import save_scraped_mcq
        mcq, _ = save_scraped_mcq('Q1', self.fields(option_a='Option A', option_b='Option B', option_c='Option C'))
        self.assertEqual(mcq.status, 'draft')
        mcq, _ = save_scraped_mcq('Q2', self.fields(correct_option='D'))  # D is empty
        self.assertEqual(mcq.status, 'draft')
        mcq, _ = save_scraped_mcq('Q3', self.fields())
        self.assertEqual(mcq.status, 'published')


class MaintenanceCommandTests(BaseAPITest):
    def test_deadline_reminders_run(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        from .models import ApplicationRequest, JobListing, Notification
        job = JobListing.objects.create(title='Clerk', description='d', last_date=timezone.localdate())
        ApplicationRequest.objects.create(user=self.user, job=job, request_status='queued')
        Notification.objects.all().delete()
        out = StringIO()
        call_command('send_deadline_reminders', stdout=out)
        self.assertIn('Total reminders sent: 1', out.getvalue())

    def test_news_digest_matches_board_by_category_slug(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        from .models import Category, NewsSubscriber, Post
        cat = Category.objects.create(name='PPSC', slug='ppsc', type='news')
        Post.objects.create(title='Result announced', slug='r', content='c', author=self.staff, category=cat,
                            post_type='news', status='published', published_at=timezone.now())
        sub = NewsSubscriber.objects.create(email='s@example.com')
        sub.boards.add(self.exam)
        out = StringIO()
        call_command('send_news_digest', '--dry-run', stdout=out)
        self.assertIn('Would send to s@example.com', out.getvalue())


class JobExpiryTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from .models import JobListing
        today = timezone.localdate()
        self.expired = JobListing.objects.create(title='Old', description='d', exam=self.exam, last_date=today - timedelta(days=1))
        self.open = JobListing.objects.create(title='Open', description='d', exam=self.exam, last_date=today + timedelta(days=20))
        self.undated = JobListing.objects.create(title='Undated', description='d', exam=self.exam)
        cache.delete('frontend_home')

    def test_home_hides_expired_and_does_not_invent_details(self):
        jobs = {j['title']: j for j in self.anon.get('/api/frontend/home/').json()['jobs']}
        self.assertNotIn('Old', jobs)
        self.assertEqual(jobs['Undated']['date'], '')       # no "Closing Soon" guess
        self.assertEqual(jobs['Undated']['bps'], '')        # no default "BPS-14"
        self.assertNotEqual(jobs['Undated']['status'], 'Closing')

    def test_api_reports_expired_job_as_closed(self):
        self.assertEqual(self.anon.get(f'/api/jobs/{self.expired.id}/').json()['status'], 'closed')
        active_ids = [j['id'] for j in self.anon.get('/api/jobs/?status=active').json()['results']]
        self.assertNotIn(self.expired.id, active_ids)
        self.assertIn(self.open.id, active_ids)

    def test_close_expired_jobs_command(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('close_expired_jobs', stdout=out)
        self.expired.refresh_from_db()
        self.open.refresh_from_db()
        self.assertEqual((self.expired.status, self.open.status), ('closed', 'active'))


class AccountDeletionTests(BaseAPITest):
    def test_uploaded_files_are_removed_with_the_account(self):
        import os
        from django.conf import settings
        res = self.client_user.post('/api/user/documents/', {'doc_type': 'cnic_front', 'file': png_upload()}, format='multipart')
        self.assertEqual(res.status_code, 201, res.content)
        from .models import UserDocument
        path = UserDocument.objects.get().file.path
        self.assertTrue(path.startswith(settings.MEDIA_ROOT) and os.path.exists(path))
        self.assertEqual(self.client_user.post('/api/user/delete-account/', {'password': 'pass12345'}, format='json').status_code, 200)
        self.assertFalse(os.path.exists(path))


class GamificationRuleTests(TestCase):
    def test_streak_breaks_after_a_missed_day(self):
        today = date(2026, 10, 15)
        days = [today - timedelta(days=n) for n in (2, 3, 4)]
        self.assertEqual(compute_streak(days, today), 0)
        self.assertEqual(compute_streak(days + [today - timedelta(days=1)], today), 4)
        self.assertEqual(compute_streak([today], today), 1)

    def test_level_is_derived_from_cumulative_xp(self):
        self.assertEqual([level_for_xp(x) for x in (0, 499, 500, 1499)], [1, 1, 2, 3])
