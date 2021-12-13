import json

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from django_easy_report.forms import ReportSenderForm
from django_easy_report.models import ReportSender, ReportGenerator, ReportRequester, ReportQuery


class BaseValidationTestCase(TestCase):
    def assertValidation(self, error_context, key, message):
        self.assertIn(key, error_context.exception.error_dict)
        error = error_context.exception.error_dict[key]
        if isinstance(error, list):
            self.assertEqual(len(error), 1)
            error = error[0]
        self.assertEqual(error.message, message)


class ReportSenderValidationTestCase(BaseValidationTestCase):
    def test_storage_class_not_exist(self):
        sender = ReportSenderForm(data={
            'name': 'class NotExistFileSystemStorage not exist',
            'storage_class_name': 'django.core.files.storage.NotExistFileSystemStorage'
        })

        self.assertFalse(sender.is_valid())
        self.assertIn('storage_class_name', sender.errors)
        error = sender.errors.get('storage_class_name')
        self.assertEqual(len(error.data), 1)

        message = 'Class "django.core.files.storage.NotExistFileSystemStorage" cannot be imported'
        self.assertEqual(error.data[0].message, message)

    def test_storage_class_module_not_exist(self):
        sender = ReportSenderForm(data={
            'name': 'storage_class_name not exists',
            'storage_class_name': 'module_not_exists.class_name'
        })

        self.assertFalse(sender.is_valid())
        self.assertIn('storage_class_name', sender.errors)
        error = sender.errors.get('storage_class_name')
        self.assertEqual(len(error.data), 1)

        message = 'Class "module_not_exists.class_name" cannot be imported'
        self.assertEqual(error.data[0].message, message)

    def test_storage_class_wrong_class(self):
        sender = ReportSenderForm(data={
            'name': 'wrong storage_class_name class type',
            'storage_class_name': 'datetime.datetime'
        })

        self.assertFalse(sender.is_valid())
        self.assertIn('storage_class_name', sender.errors)
        error = sender.errors.get('storage_class_name')
        self.assertEqual(len(error.data), 1)

        message = 'Invalid class "datetime.datetime", must be instance of Storage'
        self.assertEqual(error.data[0].message, message)

    def test_init_params_wrong_json(self):
        sender = ReportSenderForm(data={
            'name': 'wrong json',
            'storage_class_name': 'django.core.files.storage.FileSystemStorage',
            'storage_init_params': 'no json',
        })

        self.assertFalse(sender.is_valid())
        self.assertIn('storage_init_params', sender.errors)
        error = sender.errors.get('storage_init_params')
        self.assertEqual(len(error.data), 1)
        self.assertEqual(error.data[0].message, 'Invalid JSON')

    def test_init_params_wrong_params(self):
        sender = ReportSenderForm({
            'name': 'wrong init params',
            'storage_class_name': 'django.core.files.storage.FileSystemStorage',
            'storage_init_params': '{"param_not_exist": null}'
        })

        self.assertFalse(sender.is_valid())
        self.assertIn('storage_init_params', sender.errors)
        error = sender.errors.get('storage_init_params')
        self.assertEqual(len(error.data), 1)
        message = "__init__() got an unexpected keyword argument 'param_not_exist'"
        self.assertEqual(error.data[0].message, message)

    @staticmethod
    def get_fs_sender():
        return ReportSender(
            name='local storage',
            storage_class_name='django.core.files.storage.FileSystemStorage',
            storage_init_params='{"location": "test"}',
            email_from='test@localhost'
        )

    def test_all_fine(self):
        sender = self.get_fs_sender()
        try:
            sender.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))

    @override_settings(SENDER_CLASSES=[
        'django.core.files.storage.FileSystemStorage',
    ])
    def test_fine_class_filter_settings(self):
        sender = self.get_fs_sender()
        try:
            sender.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))

    @override_settings(SENDER_CLASSES=[])
    def test_wrong_class_filter_settings(self):
        sender = self.get_fs_sender()
        with self.assertRaises(ValidationError) as error_context:
            sender.clean()
        message = 'Invalid class "django.core.files.storage.FileSystemStorage" must be added on SENDER_CLASSES'
        self.assertValidation(error_context, 'storage_class_name', message)


class ReportGeneratorValidationTestCase(BaseValidationTestCase):

    def test_no_data(self):
        report = ReportGenerator(
            name='empty report',
            class_name='',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        message = 'Class "" cannot be imported'
        self.assertValidation(error_context, 'class_name', message)

    def test_class_not_exist(self):
        report = ReportGenerator(
            name='not exist report',
            class_name='django_easy_report.reports.NotExistReportModelGenerator',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()
        message = 'Class "django_easy_report.reports.NotExistReportModelGenerator" cannot be imported'
        self.assertValidation(error_context, 'class_name', message)

    def test_class_name_module_not_exist(self):
        report = ReportGenerator(
            name='not exist module report',
            class_name='module_not_exists.class_name',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        message = 'Class "module_not_exists.class_name" cannot be imported'
        self.assertValidation(error_context, 'class_name', message)

    def test_wrong_class_name(self):
        report = ReportGenerator(
            name='wrong class type',
            class_name='datetime.datetime',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        message = 'Invalid class "datetime.datetime", must be instance of ReportBaseGenerator'
        self.assertValidation(error_context, 'class_name', message)

    def test_init_params_wrong_json(self):
        report = ReportGenerator(
            name='wrong json',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params='no json',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        self.assertValidation(error_context, 'init_params', 'Invalid JSON')

    def test_init_params_wrong_params(self):
        report = ReportGenerator(
            name='Wrong init params',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params='{}',
        )

        with self.assertRaises(ValidationError) as error_context:
            report.clean()

        message = "__init__() missing 2 required positional arguments: 'model' and 'fields'"
        self.assertValidation(error_context, 'init_params', message)

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
        self.assertIn('Error creating report class: ', errors[0].message)

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

        message = 'Unknown content type for permission: "not_exist.permission"'
        self.assertValidation(error_context, 'permissions', message)

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

        message = 'Unknown code name for permission: "auth.not_exist_permission"'
        self.assertValidation(error_context, 'permissions', message)

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

        message = 'Invalid permission: "auth.user.view_user"'
        self.assertValidation(error_context, 'permissions', message)

    @staticmethod
    def get_good_report():
        return ReportGenerator(
            name='Good report',
            class_name='django_easy_report.reports.ReportModelGenerator',
            init_params=json.dumps({
              "model": "django.contrib.auth.models.User",
              "fields": ["username", "email", "first_name", "last_name", "is_staff", "is_superuser"]
            }),
            permissions='auth.view_user'
        )

    def test_all_fine(self):
        report = self.get_good_report()
        try:
            report.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))

    @override_settings(REPORT_CLASSES=[
        'django_easy_report.reports.ReportModelGenerator',
    ])
    def test_fine_class_filter_settings(self):
        report = self.get_good_report()
        try:
            report.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))

    @override_settings(REPORT_CLASSES=[])
    def test_wrong_class_filter_settings(self):
        report = self.get_good_report()
        with self.assertRaises(ValidationError) as error_context:
            report.clean()
        message = 'Invalid class "django_easy_report.reports.ReportModelGenerator" must be added on REPORT_CLASSES'
        self.assertValidation(error_context, 'class_name', message)


class ReportQueryValidationTestCase(BaseValidationTestCase):

    def test_user_params_wrong_json(self):
        query = ReportQuery(
            filename='report.csv',
            params='no json',
            params_hash=ReportQuery.gen_hash(None),
        )

        with self.assertRaises(ValidationError) as error_context:
            query.clean()

        self.assertValidation(error_context, 'params', 'Invalid JSON')

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


class ReportRequesterValidationTestCase(BaseValidationTestCase):
    def test_user_params_wrong_json(self):
        requester = ReportRequester(
            user_params='no json',
        )

        with self.assertRaises(ValidationError) as error_context:
            requester.clean()

        self.assertValidation(error_context, 'user_params', 'Invalid JSON')

    def test_all_fine(self):
        requester = ReportRequester(
            user_params='{}',
        )
        try:
            requester.clean()
        except Exception as ex:  # pragma: no cover
            self.fail('Unexpected exception {}'.format(ex))
