import json
from unittest.mock import patch, call

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from django_easy_report.models import ReportGenerator, ReportQuery, ReportRequester


class ReportSenderTestCase(TestCase):
    fixtures = ['basic_data.json']

    def setUp(self):
        self.report = ReportGenerator.objects.get(name='User_report')
        self.url = reverse('django_easy_report:report_generator', kwargs={'report_name': 'User_report'})
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

    def check_creation_and_get_user_params(self, response):
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('created', body)
        self.assertTrue(ReportQuery.objects.filter(pk=body.get('created')).exists())
        query = ReportQuery.objects.get(pk=body.get('created'))
        self.assertEqual(query.reportrequester_set.count(), 1)
        requester = query.reportrequester_set.get()
        self.assertEqual(requester.user, self.user)
        user_params = json.loads(requester.user_params)
        return user_params

    @patch('django_easy_report.views.generate_report')
    def test_create_request_without_form(self, mock_generator):
        self.login()
        init_params = json.loads(self.report.init_params)
        init_params["user_fields"] = ["email"]
        self.report.init_params = json.dumps(init_params)
        self.report.save()
        response = self.client.post(self.url, data={'email': 'test@localhost'},
                                    HTTP_HOST='localhost', SERVER_PORT=8000)
        user_params = self.check_creation_and_get_user_params(response)
        self.assertIn('domain', user_params)
        self.assertEqual(user_params.get('domain'), 'localhost')
        self.assertIn('port', user_params)
        self.assertEqual(user_params.get('port'), '8000')
        self.assertIn('protocol', user_params)
        self.assertEqual(user_params.get('protocol'), 'http')
        self.assertIn('email', user_params)
        self.assertEqual(user_params.get('email'), 'test@localhost')
        body = response.json()
        self.assertTrue(mock_generator.delay.called)
        self.assertTrue(mock_generator.delay.call_args, call(body.get('created')))

    def set_form(self, drop_params=None, set_params=None):
        init_params = json.loads(self.report.init_params)
        init_params.update({
            "form_class_name": "django_easy_report.forms.SendEmailForm",
            'email_field': 'send_to'
        })
        if drop_params:
            for param in drop_params:
                init_params.pop(param)
        if set_params:
            init_params.update(set_params)
        self.report.init_params = json.dumps(init_params)
        self.report.save()

    @patch('django_easy_report.views.generate_report')
    def test_create_request_with_form(self, mock_generator):
        self.set_form()
        self.login()
        response = self.client.post(self.url, data={'send_to': 'test@localhost'})
        user_params = self.check_creation_and_get_user_params(response)
        self.assertIn('send_to', user_params)
        self.assertEqual(user_params.get('send_to'), 'test@localhost')
        body = response.json()
        self.assertTrue(mock_generator.delay.called)
        self.assertTrue(mock_generator.delay.call_args, call(body.get('created')))

    def test_create_request_with_form_failing(self):
        self.set_form(set_params={"user_fields": []})
        self.login()
        response = self.client.post(self.url, data={'send_to': 'This is invalid email'})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('error', body)
        self.assertIn('send_to', body['error'])
        self.assertEqual(body['error']['send_to'], ['Enter a valid email address.'])

    def test_create_request_with_unexpected_fields(self):
        self.login()
        self.set_form(set_params={"user_fields": []})
        self.login()
        response = self.client.post(self.url, data={
            'send_to': 'test@localhost',
            'invalid': 'parameter'
        })
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('error', body)
        self.assertIn('invalid', body['error'])
        self.assertEqual(body['error']['invalid'], ['Invalid field invalid'])

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

    @patch('django_easy_report.views.generate_report')
    def test_request_exists_report_force_generate(self, mock_generator):
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
        self.assertTrue(mock_generator.delay.called)
        self.assertTrue(mock_generator.delay.call_args, call(body.get('created')))

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

    @patch('django_easy_report.views.notify_report_done')
    def test_notify_report(self, mock_notify):
        self.assertEqual(ReportRequester.objects.count(), 0)
        response = self.get_notify_report()

        body = response.json()
        self.assertEqual(ReportRequester.objects.count(), 1)
        self.assertEqual(response.status_code, 202)
        self.assertIn('accepted', body)
        self.assertTrue(ReportRequester.objects.filter(pk=body.get('accepted')).exists())
        self.assertTrue(mock_notify.delay.called)
        self.assertTrue(mock_notify.delay.call_args, call(body.get('accepted')))
