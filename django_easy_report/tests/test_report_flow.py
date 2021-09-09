import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from django_easy_report.models import ReportSender, ReportGenerator, ReportQuery, ReportRequester


class ReportSenderTestCase(TestCase):
    def setUp(self):
        self.sender = ReportSender.objects.create(
            name='local storage',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"location": "test_storage"}',
            email_from='test@localhost'
        )
        self.report = ReportGenerator.objects.create(
            name='users',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
                "model": "django.contrib.auth.models.User",
                "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"],
                "user_fields": ["email"]
            }),
            sender=self.sender,
            permissions='auth.view_user',
        )
        self.url = reverse('django_easy_report:report_generator', kwargs={'report_name': 'users'})
        self.user = User.objects.create_superuser('admin', 'admin@localhost', 'admin')

    def login(self):
        if hasattr(self.client, 'force_login'):  # pragma: no cover
            self.client.force_login(user=self.user)
        else:  # pragma: no cover
            self.client.login(username='admin', password='admin')  # nosec

    def test_invalid_report_name(self):
        url = reverse('django_easy_report:report_generator', kwargs={'report_name': 'dont_exists'})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'error': 'report not found'})

    def test_without_permissions(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'error': 'forbidden'})

    def test_create_request_without_form(self):
        self.login()
        response = self.client.post(self.url, data={'email': 'test@localhost'},
                                    HTTP_HOST='localhost', SERVER_PORT=8000)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('created', body)
        self.assertTrue(ReportQuery.objects.filter(pk=body.get('created')).exists())
        query = ReportQuery.objects.get(pk=body.get('created'))
        self.assertEqual(query.reportrequester_set.count(), 1)
        requester = query.reportrequester_set.get()
        self.assertEqual(requester.user, self.user)
        user_params = json.loads(requester.user_params)
        self.assertIn('domain', user_params)
        self.assertEqual(user_params.get('domain'), 'localhost')
        self.assertIn('port', user_params)
        self.assertEqual(user_params.get('port'), '8000')
        self.assertIn('protocol', user_params)
        self.assertEqual(user_params.get('protocol'), 'http')
        self.assertIn('email', user_params)
        self.assertEqual(user_params.get('email'), 'test@localhost')

    def test_create_request_with_form(self):
        raise NotImplementedError()  # TODO

    def test_create_request_with_form_failing(self):
        raise NotImplementedError()  # TODO

    def test_create_request_with_unexpected_fields(self):
        raise NotImplementedError()  # TODO

    def test_request_exists_report(self):
        query = ReportQuery.objects.create(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report
        )
        self.login()
        response = self.client.post(self.url, data={})
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('created', body)
        self.assertIn('find', body)
        self.assertEqual(body.get('find'), query.pk)

    def test_request_exists_report_force_generate(self):
        query = ReportQuery.objects.create(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report
        )
        self.login()
        response = self.client.post(self.url + '?generate=true', data={})
        body = response.json()

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('find', body)
        self.assertIn('created', body)
        self.assertNotEqual(body.get('created'), query.pk)
        self.assertEqual(ReportQuery.objects.filter(
            params_hash=query.params_hash
        ).count(), 2)

    def test_notify_unknown_report(self):
        self.login()
        response = self.client.post(self.url + '?notify=-1', data={})
        body = response.json()

        self.assertEqual(response.status_code, 404)
        self.assertIn('error', body)
        self.assertEqual(body.get('error'), 'query not found')

    def get_notify_report(self):
        query = ReportQuery.objects.create(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report
        )
        self.login()
        self.assertEqual(ReportRequester.objects.count(), 0)
        return self.client.post(self.url + '?notify={}&generate=true'.format(query.pk), data={})

    def test_notify_report(self):
        self.assertEqual(ReportRequester.objects.count(), 0)
        response = self.get_notify_report()

        body = response.json()
        self.assertEqual(ReportRequester.objects.count(), 1)
        self.assertEqual(response.status_code, 202)
        self.assertIn('accepted', body)
        self.assertTrue(ReportRequester.objects.filter(pk=body.get('accepted')).exists())

    def test_notify_report_completed_without_storage(self):
        self.sender.storage_class_name = ''
        self.sender.save()
        response = self.get_notify_report()

        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', body)
        self.assertEqual(body.get('error'), 'sender cannot storage files')
