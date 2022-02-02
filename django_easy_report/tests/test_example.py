################
# Example code #
################
import datetime
from unittest.mock import patch

from django_easy_report.reports import ReportBaseGenerator
from django_easy_report.exceptions import DoNotSend

from django import forms


class MyForm(forms.Form):
    format = forms.ChoiceField(choices=[
        ('csv', 'csv'),
        ('ods', 'ods'),
        ('xls', 'xls'),
        ('xlsx', 'xlsx'),
    ])
    webhook = forms.CharField()


class MyReportGenerator(ReportBaseGenerator):
    form_class = MyForm

    def get_params(self, data):
        user_params = {'webhook': data.pop('webhook')}
        return user_params, data

    def validate(self, data):
        errors = super(MyReportGenerator, self).validate(data)
        if not errors:
            errors = dict()
        report_format = data.get('format')
        num_rows = self.precalculate_rows()
        err_msg = 'The report need {} rows and the format do not support that size'.format(num_rows)
        if report_format == 'xls' and num_rows > self.XLS_MAX_ROWS:
            errors['format'] = err_msg
        elif report_format == 'xlsx' and num_rows > self.XLSX_MAX_ROWS:
            errors['format'] = err_msg
        elif report_format == 'ods' and num_rows > self.ODS_MAX_ROWS:
            errors['format'] = err_msg
        return errors

    def get_filename(self):
        report_format = self.setup_params.get('format')
        utc_now = datetime.datetime.utcnow()
        return "MyReport_at_{}.{}".format(
            utc_now.strftime('%Y%m%d-%M%S'),
            report_format
        )

    def get_mimetype(self):
        report_format = self.setup_params.get('format')
        if report_format == 'csv':
            return 'text/csv'
        elif report_format == 'ods':
            return 'application/vnd.oasis.opendocument.spreadsheet'
        elif report_format == 'xls':
            return 'application/vnd.ms-excel'
        elif report_format == 'xlsx':
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return self.mimetype

    def generate(self, buffer, tmp_dir):
        buffer.write(b'Your report data')
        # ...

    def get_message(self, report_status, requester, attachment=None, link=None):
        params = requester.get_params()
        if params:
            webhook = params.get('webhook')  # noqa: F841
            # Send information to webhook
            # ...
            raise DoNotSend
        return super(MyReportGenerator, self).get_message(report_status, requester,
                                                          attachment=attachment, link=link)

    def precalculate_rows(self):
        num_rows = 0
        # ...
        return num_rows


#############
# Test code #
#############
import json  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402

from django.contrib.auth.models import User  # noqa: E402
from django.test import TestCase  # noqa: E402
from django.urls import reverse  # noqa: E402

from django_easy_report.models import ReportSender, ReportGenerator  # noqa: E402


class ReportQueryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@localhost', 'admin')
        self.sender = ReportSender.objects.create(
            name='local storage',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"location": "test_storage"}',
            email_from='test@localhost'
        )
        self.report = ReportGenerator.objects.create(
            name='example_report',
            class_name='django_easy_report.tests.test_example.MyReportGenerator',
            init_params=json.dumps({}),
            sender=self.sender,
            always_download=True,
        )
        self.request_url = reverse('django_easy_report:report_generator', kwargs={
            'report_name': self.report.name,
        })
        self.client.force_login(self.user)

    def do_flow(self, file_format, tmp_dirname):
        self.sender.storage_init_params = json.dumps({"location": tmp_dirname})
        self.sender.save()
        # Make query
        response = self.client.post(self.request_url, data={
            'format': file_format,
            'webhook': 'http://webhook',
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('created', data)

        # Download report
        url = reverse('django_easy_report:report_download', kwargs={
            'report_name': self.report.name,
            'query_pk': data.get('created'),
        })
        return self.client.get(url)

    def test_csv(self):
        with TemporaryDirectory() as tmp_dirname:
            response = self.do_flow('csv', tmp_dirname)
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Content-Type', headers)
            self.assertIn(headers['Content-Type'], 'text/csv')
            self.assertEqual(response.content, b'Your report data')

    def test_ods(self):
        with TemporaryDirectory() as tmp_dirname:
            response = self.do_flow('ods', tmp_dirname)
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Content-Type', headers)
            self.assertIn(headers['Content-Type'], 'application/vnd.oasis.opendocument.spreadsheet')
            self.assertEqual(response.content, b'Your report data')

    def test_xls(self):
        with TemporaryDirectory() as tmp_dirname:
            response = self.do_flow('xls', tmp_dirname)
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Content-Type', headers)
            self.assertIn(headers['Content-Type'], 'application/vnd.ms-excel')
            self.assertEqual(response.content, b'Your report data')

    def test_xlsx(self):
        with TemporaryDirectory() as tmp_dirname:
            response = self.do_flow('xlsx', tmp_dirname)
            headers = response
            if hasattr(response, 'headers'):
                headers = response.headers
            self.assertIn('Content-Type', headers)
            self.assertIn(headers['Content-Type'],
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.assertEqual(response.content, b'Your report data')

    def fail_flow(self, file_format, webhook='http://webhook'):
        post_data = {
            'format': file_format,
        }
        if webhook:
            post_data['webhook'] = webhook
        response = self.client.post(self.request_url, data=post_data)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        return data.get('error')

    def test_required_field(self):
        error = self.fail_flow('csv', webhook='')
        self.assertIn('webhook', error)
        self.assertEqual(error.get('webhook'), ['This field is required.'])

    def test_invalid_format(self):
        error = self.fail_flow('raw')
        self.assertIn('format', error)
        self.assertEqual(error.get('format'), ['Select a valid choice. raw is not one of the available choices.'])

    @patch('django_easy_report.tests.test_example.MyReportGenerator.precalculate_rows')
    def test_max_size_ods(self, mock_precalculate_rows):
        mock_precalculate_rows.return_value = 1048577
        err_msg = 'The report need {} rows and the format do not support that size'.format(1048577)
        error = self.fail_flow('ods')
        self.assertIn('format', error)
        self.assertEqual(error.get('format'), [err_msg])

    @patch('django_easy_report.tests.test_example.MyReportGenerator.precalculate_rows')
    def test_max_size_xls(self, mock_precalculate_rows):
        mock_precalculate_rows.return_value = 65537
        err_msg = 'The report need {} rows and the format do not support that size'.format(65537)
        error = self.fail_flow('xls')
        self.assertIn('format', error)
        self.assertEqual(error.get('format'), [err_msg])

    @patch('django_easy_report.tests.test_example.MyReportGenerator.precalculate_rows')
    def test_max_size_xlsx(self, mock_precalculate_rows):
        err_msg = 'The report need {} rows and the format do not support that size'.format(1048577)
        mock_precalculate_rows.return_value = 1048577
        error = self.fail_flow('xlsx')
        self.assertIn('format', error)
        self.assertEqual(error.get('format'), [err_msg])
