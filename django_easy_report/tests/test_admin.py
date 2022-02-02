import json
import os
from gettext import gettext
from glob import glob
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.admin import helpers
from django.contrib.auth.models import User
from django.core.files.storage import Storage
from django.forms.utils import ErrorList
from django.test import TestCase, override_settings
from django.urls import reverse

from django_easy_report.choices import (
    MODE_ENVIRONMENT,
    MODE_DJANGO_SETTINGS,
    MODE_CRYPTOGRAPHY,
    MODE_CRYPTOGRAPHY_ENVIRONMENT,
    MODE_CRYPTOGRAPHY_DJANGO
)
from django_easy_report.models import (
    SecretKey,
    ReportSender,
    ReportGenerator,
    ReportQuery
)


class AdminTestCase(TestCase):
    ADD_URL = None

    def setUp(self):
        admin = User.objects.create_superuser('admin', 'admin@localhost', 'admin')
        self.client.force_login(admin)
        self.add_url = reverse(self.ADD_URL)

    def assertForm(self, response, key, message):
        self.assertEqual(response.status_code, 200)
        self.assertIn('adminform', response.context_data)
        admin_form = response.context_data.get('adminform')
        self.assertIn(key, admin_form.errors)
        self.assertEqual(admin_form.errors.get(key)[0], message)

    def assertResponseError(self, response, message):
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context_data)
        errors = response.context_data.get('errors')
        str_errors = []
        for error in errors:
            if isinstance(error, str):
                str_errors.append(error)
            elif isinstance(error, ValueError):
                str_errors.extend(error.args)
            elif isinstance(error, ErrorList):
                str_errors.extend(error)
        self.assertIn(message, str_errors)


class SecretKeyAdminTestCase(AdminTestCase):
    ADD_URL = 'admin:django_easy_report_secretkey_add'

    def create_secret(self, data):
        response = self.client.post(self.add_url, data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SecretKey.objects.count(), 1)
        return SecretKey.objects.get()

    def test_encrypt_without_key(self):
        data = {
            'mode': MODE_CRYPTOGRAPHY,
            'name': 'test',
            'value': 'test',
            'key': '',
        }
        response = self.client.post(self.add_url, data=data)
        self.assertForm(response, 'key', 'This field is required.')

    @override_settings(ARRAY_SETTING=[1, 2])
    def test_encrypt_with_wrong_key_type(self):
        data = {
            'mode': MODE_CRYPTOGRAPHY_DJANGO,
            'name': 'test',
            'value': 'test',
            'key': 'ARRAY_SETTING',
        }
        response = self.client.post(self.add_url, data=data)
        self.assertForm(response, 'key', 'Invalid type.')

    @patch('django_easy_report.forms.Fernet')
    def test_encrypt_without_support(self, fernet_mock):
        fernet_mock.__bool__.return_value = False
        data = {
            'mode': MODE_CRYPTOGRAPHY,
            'name': 'test',
            'value': 'test',
            'key': '',
        }
        response = self.client.post(self.add_url, data=data)
        self.assertForm(response, 'mode', 'Not supported cryptography.')

    def test_env(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        data = {
            'mode': MODE_ENVIRONMENT,
            'name': 'Env secret',
            'value': 'SECRET_ENV',
            'key': '',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), '3nv1R0nM3t_$3cRe7')

    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_django(self):
        data = {
            'mode': MODE_DJANGO_SETTINGS,
            'name': 'Env secret',
            'value': 'DJ_SETTING',
            'key': '',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), 'Djang0_$3cRe7')

    def test_gen_crypto(self):
        data = {
            'mode': MODE_CRYPTOGRAPHY,
            'name': 'Env secret',
            'value': 'new secret',
            'key': '$3cRe7_K3y',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), 'new secret')

    def test_gen_crypto_env(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        data = {
            'mode': MODE_CRYPTOGRAPHY_ENVIRONMENT,
            'name': 'Env secret',
            'value': 'new secret',
            'key': 'SECRET_ENV',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), 'new secret')

    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_gen_crypto_django(self):
        data = {
            'mode': MODE_CRYPTOGRAPHY_DJANGO,
            'name': 'Env secret',
            'value': 'new secret',
            'key': 'DJ_SETTING',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), 'new secret')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    def test_gen_crypto_django_settings(self):
        data = {
            'mode': MODE_CRYPTOGRAPHY_DJANGO,
            'name': 'Env secret',
            'value': 'new secret',
        }
        secret = self.create_secret(data)
        self.assertEqual(secret.get_secret(), 'new secret')


class TestClassStorage(Storage):
    def __init__(self, *args, **kwargs):
        if 'raise' in kwargs:
            raise Exception('Error creating storage')
        self.args = args
        self.kwargs = kwargs


class ReportSenderAdminTestCase(AdminTestCase):
    ADD_URL = 'admin:django_easy_report_reportsender_add'

    def setUp(self):
        super(ReportSenderAdminTestCase, self).setUp()
        self.secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY,
            name='test',
            value='secret value',
            key='key',
        )

    def test_error_creating_storage_class(self):
        data = {
            'name': 'test storage',
            'storage_class_name': 'django_easy_report.tests.test_admin.TestClassStorage',
            'storage_init_params': json.dumps({'raise': True}),
            'size_to_attach': 0,
            'secretreplace_set-TOTAL_FORMS': 0,
            'secretreplace_set-INITIAL_FORMS': 0,
            'secretreplace_set-MIN_NUM_FORMS': 0,
            'secretreplace_set-MAX_NUM_FORMS': 1000,
        }
        response = self.client.post(self.add_url, data=data)
        self.assertForm(response, 'storage_init_params',
                        'Error creating storage class: "Error creating storage".')

    def test_replace_key(self):
        data = {
            'name': 'test storage',
            'storage_class_name': 'django_easy_report.tests.test_admin.TestClassStorage',
            'storage_init_params': '{"test": $secret}',
            'size_to_attach': 0,
            'secretreplace_set-TOTAL_FORMS': 1,
            'secretreplace_set-INITIAL_FORMS': 0,
            'secretreplace_set-MIN_NUM_FORMS': 0,
            'secretreplace_set-MAX_NUM_FORMS': 1000,
            'secretreplace_set-0-secret': self.secret.id,
            'secretreplace_set-0-replace_word': 'secret',
        }
        response = self.client.post(self.add_url, data=data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReportSender.objects.count(), 1)
        sender = ReportSender.objects.get()
        storage = sender.get_storage()
        self.assertEqual(storage.kwargs, {'test': 'secret value'})

    def test_fail_replace_key_with_same_replace_word(self):
        secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY,
            name='new key',
            value='new secret',
            key='key',
        )
        data = {
            'name': 'test storage',
            'storage_class_name': 'django_easy_report.tests.test_admin.TestClassStorage',
            'storage_init_params': '{"test": $secret}',
            'size_to_attach': 0,
            'secretreplace_set-TOTAL_FORMS': 2,
            'secretreplace_set-INITIAL_FORMS': 0,
            'secretreplace_set-MIN_NUM_FORMS': 0,
            'secretreplace_set-MAX_NUM_FORMS': 1000,
            'secretreplace_set-0-secret': self.secret.id,
            'secretreplace_set-0-replace_word': 'secret',
            'secretreplace_set-1-secret': secret.id,
            'secretreplace_set-1-replace_word': 'secret',
        }
        response = self.client.post(self.add_url, data=data)
        self.assertResponseError(response, 'Please correct the duplicate data for replace_word.')
        self.assertResponseError(response, 'Please correct the duplicate values below.')


class AdminActionTestCase(AdminTestCase):
    fixtures = ['basic_data.json']
    ADD_URL = 'admin:django_easy_report_reportgenerator_changelist'

    def make_report(self):
        data = {
            'action': 'generate_report',
            'select_across': '1',
            'index': '0',
            helpers.ACTION_CHECKBOX_NAME: ['1']
        }
        return self.client.post(self.add_url, data)

    @patch('django_easy_report.actions.generate_report_task')
    def test_no_report(self, mock_generate_report_task):
        response = self.make_report()
        self.assertFalse(mock_generate_report_task.delay.called)
        self.assertEqual(
            response.wsgi_request._messages._queued_messages[0].message,
            gettext('Admin report (django_easy_report.reports.AdminReportGenerator) not found.')
        )

    @patch('django_easy_report.actions.generate_report_task')
    def test_many_reports(self, mock_generate_report_task):
        sender = ReportSender.objects.get()
        ReportGenerator.objects.create(
            name='admin_report',
            class_name='django_easy_report.reports.AdminReportGenerator',
            init_params=json.dumps({}),
            sender=sender
        )
        ReportGenerator.objects.create(
            name='admin_report_not_send',
            class_name='django_easy_report.reports.AdminReportGenerator',
            init_params=json.dumps({'send_email': False}),
            sender=sender
        )
        response = self.make_report()
        self.assertFalse(mock_generate_report_task.delay.called)
        self.assertEqual(
            response.wsgi_request._messages._queued_messages[0].message,
            gettext('Detected more than one admin report.')
        )

    @patch('django_easy_report.actions.generate_report_task')
    def test_run_report(self, mock_generate_report_task):
        sender = ReportSender.objects.get()
        ReportGenerator.objects.create(
            name='admin_report',
            class_name='django_easy_report.reports.AdminReportGenerator',
            init_params=json.dumps({}),
            sender=sender
        )
        response = self.make_report()
        self.assertTrue(mock_generate_report_task.delay.called)
        self.assertEqual(ReportQuery.objects.count(), 1)
        query = ReportQuery.objects.get()
        self.assertEqual(
            response.wsgi_request._messages._queued_messages[0].message,
            gettext('Report queued ({}).').format(query.pk)
        )
        args_list = mock_generate_report_task.delay.call_args_list
        self.assertTrue(args_list[0], query.pk)
        params = json.loads(query.params)
        for key in ['sql', 'fields', 'admin_class', 'model_class']:
            self.assertIn(key, params.keys())
        self.assertEqual(params['fields'], ['name', 'class_name', 'sender', 'params_keys'])
        self.assertEqual(params['admin_class'], 'django_easy_report.admin.ReportGeneratorAdmin')
        self.assertEqual(params['model_class'], 'django_easy_report.models.ReportGenerator')

    def test_generate_report(self):
        with TemporaryDirectory() as tmp_dirname:
            sender = ReportSender.objects.get()
            storage_init_params = json.loads(sender.storage_init_params)
            storage_init_params['location'] = tmp_dirname
            sender.storage_init_params = json.dumps(storage_init_params)
            sender.save()
            ReportGenerator.objects.create(
                name='admin_report',
                class_name='django_easy_report.reports.AdminReportGenerator',
                init_params=json.dumps({}),
                sender=sender
            )
            response = self.make_report()
            self.assertEqual(ReportQuery.objects.count(), 1)
            query = ReportQuery.objects.get()
            self.assertEqual(
                response.wsgi_request._messages._queued_messages[0].message,
                gettext('Report queued ({}).').format(query.pk)
            )
            self.assertEqual(query.status, 20)
            report_list = list(glob('{}/admin_report/*/*'.format(tmp_dirname)))
            self.assertEqual(len(report_list), 1)
            report = report_list[0]
            with open(report, 'r') as f:
                content = f.read()
            self.assertNotEqual(len(content), 0)
            lines = [line for line in content.split('\n') if line]
            self.assertEqual(lines[0], 'name,class_name,sender,params_keys')
            self.assertEqual(len(lines), ReportGenerator.objects.count() + 1)
