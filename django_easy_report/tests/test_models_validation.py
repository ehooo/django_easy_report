import json

from django.core.exceptions import ValidationError
from django.test import TestCase

from django_easy_report.models import ReportSender, ReportGenerator, ReportRequester, ReportQuery


class ReportSenderValidationTestCase(TestCase):
    def test_no_data(self):
        sender = ReportSender(name='No data test')
        self.assertRaisesMessage(
            ValidationError,
            'Email or Storage class must be entered',
            sender.clean
        )

    def test_storage_class_not_exist(self):
        sender = ReportSender(
            name='class NotExistFileSystemStorage not exist',
            storage_class_name='django.core.files.storage.NotExistFileSystemStorage'
        )

        with self.assertRaises(ValidationError) as error_context:
            sender.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'storage_class_name': [
                    ValidationError('Class "django.core.files.storage.NotExistFileSystemStorage" cannot be imported')
                ]
            }
        )

    def test_storage_class_module_not_exist(self):
        sender = ReportSender(
            name='storage_class_name not exists',
            storage_class_name='module_not_exists.class_name'
        )

        with self.assertRaises(ValidationError) as error_context:
            sender.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'storage_class_name': [
                    ValidationError('Class "module_not_exists.class_name" cannot be imported')
                ]
            }
        )

    def test_storage_class_wrong_class(self):
        sender = ReportSender(
            name='wrong storage_class_name class type',
            storage_class_name='datetime.datetime'
        )

        with self.assertRaises(ValidationError) as error_context:
            sender.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'storage_class_name': [
                    ValidationError('Invalid class "datetime.datetime", must be instance of Storage')
                ]
            }
        )

    def test_init_params_wrong_json(self):
        sender = ReportSender(
            name='wrong json',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='no json'
        )

        with self.assertRaises(ValidationError) as error_context:
            sender.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'storage_init_params': [
                    ValidationError('Invalid JSON')
                ]
            }
        )

    def test_init_params_wrong_params(self):
        sender = ReportSender(
            name='wrong init params',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"param_not_exist": null}'
        )

        with self.assertRaises(ValidationError) as error_context:
            sender.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'storage_init_params': [
                    ValidationError("__init__() got an unexpected keyword argument 'param_not_exist'")
                ]
            }
        )

    def test_all_fine(self):
        sender = ReportSender(
            name='local storage',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"location": "test"}',
            email_from='test@localhost'
        )
        try:
            sender.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))


class ReportGeneratorValidationTestCase(TestCase):

    def test_no_data(self):
        report = ReportGenerator(
            name='empty report',
            class_name='',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'class_name': [
                    ValidationError('Class "" cannot be imported')
                ]
            }
        )

    def test_class_not_exist(self):
        report = ReportGenerator(
            name='not exist report',
            class_name='django_easy_report.reports.NotExistReportModelGenerator',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {'class_name': [
                ValidationError('Class "django_easy_report.reports.NotExistReportModelGenerator" cannot be imported')
            ]}
        )

    def test_class_name_module_not_exist(self):
        report = ReportGenerator(
            name='not exist module report',
            class_name='module_not_exists.class_name',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'class_name': [
                    ValidationError('Class "module_not_exists.class_name" cannot be imported')
                ]
            }
        )

    def test_wrong_class_name(self):
        report = ReportGenerator(
            name='wrong class type',
            class_name='datetime.datetime',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'class_name': [
                    ValidationError('Invalid class "datetime.datetime", must be instance of ReportBaseGenerator')
                ]
            }
        )

    def test_init_params_wrong_json(self):
        report = ReportGenerator(
            name='wrong json',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params='no json',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'init_params': [
                    ValidationError('Invalid JSON')
                ]
            }
        )

    def test_init_params_wrong_params(self):
        report = ReportGenerator(
            name='Wrong init params',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params='{}',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'init_params': [
                    ValidationError("__init__() missing 2 required positional arguments: 'model' and 'fields'")
                ]
            }
        )

    def test_init_params_wrong_values(self):
        report = ReportGenerator(
            name='Wrong init params',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params='{"model": null, "fields": []}',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertIn('init_params', error_context.exception.error_dict)
        errors = error_context.exception.error_dict['init_params']
        self.assertEqual(1, len(errors))
        self.assertIn('Error creating report class: ', errors[0].message,)

    def test_not_exist_content_type(self):
        report = ReportGenerator(
            name='wrong permission report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            permissions='not_exist.permission'
        )
        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'permissions': [
                    ValidationError('Unknown content type for permission: "not_exist.permission"')
                ]
            }
        )

    def test_not_exist_permission(self):
        report = ReportGenerator(
            name='wrong permission report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            permissions='auth.not_exist_permission'
        )
        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'permissions': [
                    ValidationError('Unknown code name for permission: "auth.not_exist_permission"')
                ]
            }
        )

    def test_invalid_permission_format(self):
        report = ReportGenerator(
            name='wrong permission report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            permissions='auth.user.view_user'
        )
        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'permissions': [
                    ValidationError('Invalid permission: "auth.user.view_user"')
                ]
            }
        )

    def test_all_fine(self):
        report = ReportGenerator(
            name='Good report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            permissions='auth.view_user'
        )
        try:
            report.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))


class ReportQueryValidationTestCase(TestCase):

    def test_user_params_wrong_json(self):
        query = ReportQuery(
            filename='report.csv',
            params='no json',
            params_hash=ReportQuery.gen_hash(None),
        )

        with self.assertRaises(ValidationError) as error_context:
            query.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'params': [
                    ValidationError('Invalid JSON')
                ]
            }
        )

    def test_all_fine(self):
        query = ReportQuery(
            filename='users.csv',
            mimetype='text/csv',
            params='{}',
            params_hash=ReportQuery.gen_hash({}),
        )
        try:
            query.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))


class ReportRequesterValidationTestCase(TestCase):
    def test_user_params_wrong_json(self):
        requester = ReportRequester(
            user_params='no json',
        )

        with self.assertRaises(ValidationError) as error_context:
            requester.clean()

        self.assertEqual(
            error_context.exception.error_dict,
            {
                'user_params': [
                    ValidationError('Invalid JSON')
                ]
            }
        )

    def test_all_fine(self):
        requester = ReportRequester(
            user_params='{}',
        )
        try:
            requester.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))
