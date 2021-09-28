import json
import os
from collections import OrderedDict
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.test import TestCase

from django_easy_report.models import ReportSender, ReportGenerator, ReportQuery
from django_easy_report.reports import ReportModelGenerator


class ReportSenderTestCase(TestCase):

    def test_get_storage_class_not_exist(self):
        sender = ReportSender(
            name='class NotExistFileSystemStorage not exist',
            storage_class_name='django.core.files.storage.NotExistFileSystemStorage'
        )

        with self.assertRaises(ImportError) as error_context:
            sender.get_storage()

        self.assertEqual(
            error_context.exception.msg,
            'Cannot import class django.core.files.storage.NotExistFileSystemStorage'
        )

    def test_get_storage_class_module_not_exist(self):
        sender = ReportSender(
            name='storage_class_name not exists',
            storage_class_name='module_not_exists.class_name'
        )

        with self.assertRaises(ImportError) as error_context:
            sender.get_storage()

        self.assertEqual(error_context.exception.msg, "No module named 'module_not_exists'")

    def test_get_storage_class_wrong_class(self):
        sender = ReportSender(
            name='wrong storage_class_name class type',
            storage_class_name='datetime.datetime',
            storage_init_params='{"year": 2020, "month": 1, "day": 1}'
        )

        with self.assertRaises(ImportError) as error_context:
            sender.get_storage()

        self.assertEqual(error_context.exception.msg, 'Only Storage classes are allowed')


class ReportGeneratorTestCase(TestCase):
    def test_get_permissions_list_without_permission(self):
        self.assertEqual(ReportGenerator().get_permissions(), set())

    def test_get_permissions_list_with_same_permission(self):
        report = ReportGenerator(
            permissions='auth.view_user,auth.view_user'
        )
        self.assertEqual(report.get_permissions(), {'auth.view_user'})

    def test_get_permissions_list_with_multi_permissions(self):
        report = ReportGenerator(
            permissions='auth.view_user ,auth.delete_user, auth.change_user'
        )
        self.assertEqual(
            report.get_permissions(),
            {'auth.view_user', 'auth.delete_user', 'auth.change_user'}
        )
        report.get_permissions()

    def test_get_report_class_not_exist(self):
        report = ReportGenerator(
            name='not exist report',
            class_name='django_easy_report.reports.NotExistReportModelGenerator',
        )

        with self.assertRaises(ImportError) as error_context:
            report.get_report()

        self.assertEqual(
            error_context.exception.msg,
            'Cannot import class django_easy_report.reports.NotExistReportModelGenerator'
        )

    def test_get_report_class_module_not_exist(self):
        report = ReportGenerator(
            name='not exist module report',
            class_name='module_not_exists.class_name',
        )

        with self.assertRaises(ImportError) as error_context:
            report.get_report()

        self.assertEqual(error_context.exception.msg, "No module named 'module_not_exists'")

    def test_get_report_class_wrong_class(self):
        report = ReportGenerator(
            name='wrong class type',
            class_name='datetime.datetime',
            init_params='{"year": 2020, "month": 1, "day": 1}'
        )

        with self.assertRaises(ImportError) as error_context:
            report.get_report()

        self.assertEqual(error_context.exception.msg, 'Only ReportBaseGenerator classes are allowed')


class ReportQueryGenHashTestCase(TestCase):
    def test_empty_items(self):
        hash1 = ReportQuery.gen_hash({})
        hash2 = ReportQuery.gen_hash([])
        hash3 = ReportQuery.gen_hash(None)
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)

    def test_invalid_object(self):
        with self.assertRaises(TypeError) as error_context:
            ReportQuery.gen_hash(str)
        self.assertEqual(error_context.exception.args[0], 'data_dict must implements keys and get functions')

    def test_same_dict_different_order(self):
        hash1 = ReportQuery.gen_hash({'a': 'a', 'b': 'b'})
        hash2 = ReportQuery.gen_hash({'b': 'b', 'a': 'a'})
        self.assertEqual(hash1, hash2)

    def test_same_ordered_dict_different_order(self):
        orderdict1 = OrderedDict()
        orderdict1['a'] = 'a'
        orderdict1['b'] = 'b'
        orderdict2 = OrderedDict()
        orderdict2['b'] = 'b'
        orderdict2['a'] = 'a'
        hash1 = ReportQuery.gen_hash(orderdict1)
        hash2 = ReportQuery.gen_hash(orderdict2)
        self.assertEqual(hash1, hash2)

    def test_same_with_order_dict_as_value(self):
        orderdict1 = OrderedDict()
        orderdict1['a'] = 'a'
        orderdict1['b'] = 'b'
        orderdict2 = OrderedDict()
        orderdict2['b'] = 'b'
        orderdict2['a'] = 'a'
        hash1 = ReportQuery.gen_hash({'order': orderdict1, 'a': 'a'})
        hash2 = ReportQuery.gen_hash({'a': 'a', 'order': orderdict2})
        self.assertEqual(hash1, hash2)

    def test_same_dict_and_order_dict(self):
        hash1 = ReportQuery.gen_hash({'a': 'a', 'b': 'b'})
        orderdict = OrderedDict()
        orderdict['b'] = 'b'
        orderdict['a'] = 'a'
        hash2 = ReportQuery.gen_hash(orderdict)
        self.assertEqual(hash1, hash2)

    def test_gen_hash_different(self):
        hash1 = ReportQuery.gen_hash({'a': ['b', 'a']})
        hash2 = ReportQuery.gen_hash({'a': ['a', 'b']})
        self.assertNotEqual(hash1, hash2)

    def test_gen_hash_with_model(self):
        sender = ReportSender.objects.create(
            name='email sender',
            email_from='test@localhost'
        )
        hash1 = ReportQuery.gen_hash({'model': sender})
        hash2 = ReportQuery.gen_hash({'model': 'django_easy_report.models.ReportSender({})'.format(sender.pk)})
        self.assertNotEqual(hash1, hash2)


class ReportQueryTestCase(TestCase):
    def setUp(self):
        self.sender = ReportSender(
            name='local storage',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"location": "test_storage"}',
            email_from='test@localhost'
        )
        self.report = ReportGenerator(
            name='Good report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            sender=self.sender,
            permissions='auth.view_user',
        )

    def test_get_report_check_constructor(self):
        query = ReportQuery(
            filename='report.csv',
            params='',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report
        )
        report = query.get_report()
        self.assertIsInstance(report, ReportModelGenerator)
        self.assertEqual(report.model_cls, User)
        self.assertEqual(
            report.fields,
            ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
        )

    def test_get_report_with_check_setup(self):
        params = {'parm': 1}
        query = ReportQuery(
            filename='report.csv',
            params=json.dumps(params),
            params_hash=ReportQuery.gen_hash(params),
            report=self.report
        )
        report = query.get_report()
        self.assertIsInstance(report, ReportModelGenerator)
        self.assertEqual(report.report_model, query)
        self.assertEqual(report.setup_params, params)

    def test_get_file_without_storage_path_location(self):
        query = ReportQuery(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report
        )
        self.assertIsNone(query.get_file())

    def test_get_file_with_storage_path_location(self):
        query = ReportQuery(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report,
            storage_path_location='tmp/report.csv'
        )
        response = query.get_file()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/tmp/report.csv')

    def test_get_file_open_file_not_found(self):
        self.sender.save()
        self.report.sender = self.sender
        self.report.always_download = True
        self.report.save()
        query = ReportQuery(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report,
            storage_path_location='tmp/report.csv'
        )

        with self.assertRaises(FileNotFoundError) as error_context:
            query.get_file()

        self.assertEqual(error_context.exception.args, (2, 'No such file or directory'))

    def _prepare_storage_file(self, tmpdirname):
        self.sender.storage_init_params = json.dumps({"location": tmpdirname})
        self.sender.save()
        self.report.sender = self.sender
        self.report.save()
        query = ReportQuery.objects.create(
            filename='report.csv',
            params_hash=ReportQuery.gen_hash(None),
            report=self.report,
            storage_path_location='tmp/report.csv'
        )

        # Save test file on storage
        storage = query.report.sender.get_storage()
        buffer = StringIO()
        buffer.write('test content')
        buffer.seek(0)
        storage.save(query.storage_path_location, buffer)
        return query

    def test_delete_object(self):
        with TemporaryDirectory() as tmp_dirname:
            query = self._prepare_storage_file(tmp_dirname)
            # Check file exist
            self.assertTrue(os.path.isfile('{}/tmp/report.csv'.format(tmp_dirname)))
            query.delete()
            # Check file was removed with the object
            self.assertFalse(os.path.isfile('{}/tmp/report.csv'.format(tmp_dirname)))

    def test_delete_filter(self):
        with TemporaryDirectory() as tmp_dirname:
            self._prepare_storage_file(tmp_dirname)
            # Check file exist
            self.assertTrue(os.path.isfile('{}/tmp/report.csv'.format(tmp_dirname)))
            ReportQuery.objects.all().delete()
            # Check file was removed with the object
            self.assertFalse(os.path.isfile('{}/tmp/report.csv'.format(tmp_dirname)))
