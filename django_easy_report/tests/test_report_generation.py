import json
import os
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch, call

from django.contrib.auth import get_user_model
from django.test import TestCase

from django_easy_report.constants import STATUS_CREATED, STATUS_DONE, STATUS_ERROR
from django_easy_report.models import ReportGenerator, ReportQuery, ReportRequester
from django_easy_report.tasks import generate_report, notify_report_done


class ReportBaseTestCase(TestCase):
    fixtures = ['basic_data.json']

    def setUp(self):
        self.report = ReportGenerator.objects.get(name='User_report')
        # noinspection PyPep8Naming
        User = get_user_model()
        self.user = User.objects.create_superuser('admin', 'admin@localhost', 'admin')

    def _create_query(self, report_params, user_params):
        report_params = report_params or {}
        user_params = user_params or {}
        params_hash = ReportQuery.gen_hash(report_params)
        query = ReportQuery.objects.create(
            params_hash=params_hash,
            report=self.report,
            params=json.dumps(report_params)
        )
        ReportRequester.objects.create(
            query=query,
            user=self.user,
            user_params=json.dumps(user_params)
        )
        return query

    def _setup_sender(self, tmp_dirname):
        sender = self.report.sender
        storage_init_params = json.loads(sender.storage_init_params)
        storage_init_params["location"] = tmp_dirname
        sender.storage_init_params = json.dumps(storage_init_params)
        sender.save()
        return sender


class ReportGenerateTestCase(ReportBaseTestCase):

    @patch('django_easy_report.tasks.notify_report_done')
    def test_generate_report(self, mock_notify):
        with TemporaryDirectory() as tmp_dirname:
            self._setup_sender(tmp_dirname)
            query = self._create_query({}, {'email_to': 'admin@host.local'})

            self.assertEqual(query.status, STATUS_CREATED)
            self.assertFalse(query.filename)
            self.assertEqual(query.mimetype, 'application/octet-stream')
            generate_report(query.pk)
            query.refresh_from_db()

            self.assertEqual(query.status, STATUS_DONE)
            self.assertTrue(query.filename)
            self.assertEqual(query.mimetype, 'text/csv')
            local_path = os.path.join(tmp_dirname, query.storage_path_location)
            self.assertTrue(os.path.isfile(local_path))

            self.assertTrue(mock_notify.delay.called)
            requester = query.reportrequester_set.get()
            self.assertTrue(mock_notify.delay.call_args, call(requester.pk))

    @patch('django_easy_report.tasks.notify_report_done')
    def test_generate_report_failing(self, mock_notify):
        self.report.class_name = 'class.not_exists'
        self.report.save()
        query = self._create_query({}, {'email_to': 'admin@host.local'})

        self.assertEqual(query.status, STATUS_CREATED)
        with self.assertRaises(ImportError):
            generate_report(query.pk)
        query.refresh_from_db()

        self.assertEqual(query.status, STATUS_ERROR)
        self.assertTrue(mock_notify.delay.called)
        requester = query.reportrequester_set.get()
        self.assertTrue(mock_notify.delay.call_args, call(requester.pk))

    def test_report_content(self):
        get_user_model().objects.create_user(
            'user', 'user@localhost', '$3Cre7', first_name='User name', last_name='Last name'
        )
        with TemporaryDirectory() as tmp_dirname:
            sender = self._setup_sender(tmp_dirname)
            query = self._create_query({}, {})

            generate_report(query.pk)
            query.refresh_from_db()

            storage = sender.get_storage()
            self.assertTrue(storage.exists(query.storage_path_location))
            with query.get_file(True) as f:
                content = f.read()
            lines = content.split('\n')

            self.assertEqual(lines[0], 'username,email,first_name,last_name,is_staff,is_superuser')
            self.assertIn('admin,admin@localhost,,,True,True', lines)
            self.assertIn('user,user@localhost,User name,Last name,False,False', lines)


class ReportNotifiedTestCase(ReportBaseTestCase):

    def _save_example_report(self, query, content=None, size=0, filename=None, mimetype=None):
        storage = self.report.sender.get_storage()
        buffer = StringIO()
        if content:
            buffer.write('Header\ncontent')
        elif size:
            buffer.write('A' * size)
        buffer.seek(0)
        if filename:
            query.filename = filename
        else:
            query.filename = 'test.csv'
        if mimetype:
            query.mimetype = mimetype
        query.storage_path_location = storage.save(query.filename, buffer)
        query.status = STATUS_DONE
        query.save()

    @patch('django_easy_report.tasks.EmailMessage')
    def test_send_with_attachment(self, email_msg_mock):
        with TemporaryDirectory() as tmp_dirname:
            self._setup_sender(tmp_dirname)
            query = self._create_query({}, {})
            self._save_example_report(query, 'File content',
                                      filename='report.txt', mimetype='text/plain')
            request = ReportRequester.objects.create(
                query=query,
                user=self.user,
                user_params=json.dumps({}),
            )

            notify_report_done([request.id])
            request.refresh_from_db()

            self.assertTrue(request.notified)
            self.assertTrue(email_msg_mock.called)
            email_cls = email_msg_mock.return_value
            self.assertTrue(email_cls.attach.called)
            self.assertTrue(email_cls.attach.call_args, call('report.txt', 'File content', 'text/plain'))
            self.assertTrue(email_cls.send.called)

    @patch('django_easy_report.tasks.EmailMessage')
    def test_send_without_attachment(self, email_msg_mock):
        with TemporaryDirectory() as tmp_dirname:
            sender = self._setup_sender(tmp_dirname)
            query = self._create_query({}, {})
            self._save_example_report(query, size=sender.size_to_attach, filename='report.dat')
            request = ReportRequester.objects.create(
                query=query,
                user=self.user,
                user_params=json.dumps({}),
            )

            notify_report_done([request.id])
            request.refresh_from_db()

            self.assertTrue(request.notified)
            self.assertTrue(email_msg_mock.called)
            subject, body, email_from, email_to = email_msg_mock.call_args[0]
            self.assertEqual(body, 'Report completed. Download from <a href="/report.dat">here<a/>')
            email_cls = email_msg_mock.return_value
            self.assertFalse(email_cls.attach.called)
            self.assertTrue(email_cls.send.called)

    @patch('django_easy_report.tasks.EmailMessage')
    def test_fail_send_message(self, email_msg_mock):
        with TemporaryDirectory() as tmp_dirname:
            self._setup_sender(tmp_dirname)
            query = self._create_query({}, {})
            email_cls = email_msg_mock.return_value
            email_cls.send.side_effect = RuntimeError('Test it')
            self._save_example_report(query)
            request = ReportRequester.objects.create(
                query=query,
                user=self.user,
                user_params=json.dumps({}),
            )

            notify_report_done([request.id])

            request.refresh_from_db()
            self.assertFalse(request.notified)
            self.assertTrue(email_msg_mock.called)

    @patch('django_easy_report.tasks.EmailMessage')
    def test_send_error_report(self, email_msg_mock):
        query = self._create_query({}, {})
        query.status = STATUS_ERROR
        query.save()
        request = ReportRequester.objects.create(
            query=query,
            user=self.user,
            user_params=json.dumps({}),
        )

        notify_report_done([request.id])

        self.assertTrue(email_msg_mock.called)
        subject, body, email_from, email_to = email_msg_mock.call_args[0]
        self.assertEqual(body, 'Something was wrong')

    @patch('django_easy_report.tasks.EmailMessage')
    def test_send_invalid_status_report(self, email_msg_mock):
        query = self._create_query({}, {})
        query.status = 1000
        query.save()
        request = ReportRequester.objects.create(
            query=query,
            user=self.user,
            user_params=json.dumps({}),
        )

        notify_report_done([request.id])

        self.assertTrue(email_msg_mock.called)
        subject, body, email_from, email_to = email_msg_mock.call_args[0]
        self.assertEqual(body, 'Invalid status (1000)')

    @patch('django_easy_report.tasks.EmailMessage')
    def test_send_invalid_status_report_with_name(self, email_msg_mock):
        query = self._create_query({}, {})
        request = ReportRequester.objects.create(
            query=query,
            user=self.user,
            user_params=json.dumps({}),
        )

        notify_report_done([request.id])

        self.assertTrue(email_msg_mock.called)
        subject, body, email_from, email_to = email_msg_mock.call_args[0]
        self.assertEqual(body, 'Invalid status (Created)')

    @patch('django_easy_report.tasks.EmailMessage')
    def test_without_elements(self, email_msg_mock):
        notify_report_done([])
        self.assertFalse(email_msg_mock.called)

    @patch('django_easy_report.tasks.EmailMessage')
    def test_mix_queries(self, email_msg_mock):
        request1 = ReportRequester.objects.create(
            query=self._create_query({}, {}),
            user=self.user,
            user_params=json.dumps({}),
        )
        request2 = ReportRequester.objects.create(
            query=self._create_query({}, {}),
            user=self.user,
            user_params=json.dumps({}),
        )

        with self.assertRaises(ValueError) as error_context:
            notify_report_done([request1.pk, request2.pk])

        self.assertFalse(email_msg_mock.called)
        self.assertGreaterEqual(len(error_context.exception.args), 1)
        message = error_context.exception.args[0]
        self.assertTrue(message.startswith('All requesters must be from the same query'))
