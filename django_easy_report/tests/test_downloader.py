import json
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from django_easy_report.constants import STATUS_DONE
from django_easy_report.models import ReportGenerator, ReportQuery, ReportRequester


class DownloaderTestCase(TestCase):
    fixtures = ['basic_data.json']

    def setUp(self):
        self.report = ReportGenerator.objects.get(name='User_report')
        # noinspection PyPep8Naming
        User = get_user_model()
        self.user = User.objects.create_superuser('admin', 'admin@localhost', 'admin')

        report_params = {}
        user_params = {}
        params_hash = ReportQuery.gen_hash(report_params)
        self.query = ReportQuery.objects.create(
            filename='test.csv',
            mimetype='text/csv',
            params_hash=params_hash,
            report=self.report,
            params=json.dumps(report_params)
        )
        ReportRequester.objects.create(
            query=self.query,
            user=self.user,
            user_params=json.dumps(user_params)
        )
        self.url = reverse('django_easy_report:report_download', kwargs={
            'report_name': self.report.name,
            'query_pk': self.query.pk,
        })

    def _setup_sender(self, tmp_dirname):
        sender = self.report.sender
        storage_init_params = json.loads(sender.storage_init_params)
        storage_init_params["location"] = tmp_dirname
        sender.storage_init_params = json.dumps(storage_init_params)
        sender.save()
        return sender

    def _save_example_report(self, content):
        storage = self.report.sender.get_storage()
        buffer = StringIO()
        buffer.write(content)
        buffer.seek(0)
        self.query.storage_path_location = storage.save(self.query.filename, buffer)
        self.query.status = STATUS_DONE
        self.query.save()

    def test_report_do_not_match_with_query(self):
        self.client.force_login(self.user)
        report = ReportGenerator.objects.create(
            name="other_report",
            class_name=self.report.class_name,
            init_params=self.report.init_params,
            sender=self.report.sender,
        )
        url = reverse('django_easy_report:report_download', kwargs={
            'report_name': report.name,
            'query_pk': self.query.pk,
        })
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_without_permissions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_without_file(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_with_redirection(self):
        self.client.force_login(self.user)
        with TemporaryDirectory() as tmp_dirname:
            self._setup_sender(tmp_dirname)
            self._save_example_report('File content')
            self.report.always_download = False
            self.report.save()

            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 302)
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Location', headers)
            self.assertTrue(headers['Location'].endswith('test.csv'))

    def test_direct_download(self):
        self.client.force_login(self.user)
        with TemporaryDirectory() as tmp_dirname:
            self._setup_sender(tmp_dirname)
            self._save_example_report('Just a test')
            self.report.always_download = True
            self.report.save()

            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'Just a test')
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Content-Type', headers)
            self.assertEqual(headers['Content-Type'], 'text/csv')
            self.assertIn('Content-Disposition', headers)
            self.assertEqual(
                headers['Content-Disposition'],
                'attachment; filename=test.csv'
            )
