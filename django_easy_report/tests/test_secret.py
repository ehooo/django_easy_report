import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from django_easy_report.choices import (
    MODE_ENVIRONMENT,
    MODE_DJANGO_SETTINGS,
    MODE_CRYPTOGRAPHY,
    MODE_CRYPTOGRAPHY_ENVIRONMENT,
    MODE_CRYPTOGRAPHY_DJANGO,
)
from django_easy_report.models import SecretKey
from django_easy_report.tests.test_models_validation import BaseValidationTestCase
from django_easy_report import utils


class SecretKeyModelTestCase(TestCase):

    def test_env(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        secret = SecretKey(
            mode=MODE_ENVIRONMENT,
            name='Env secret',
            value='SECRET_ENV',
        )
        self.assertIsNone(secret.get_key())
        plain = secret.get_secret()
        self.assertEqual(plain, '3nv1R0nM3t_$3cRe7')

    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_django(self):
        secret = SecretKey(
            mode=MODE_DJANGO_SETTINGS,
            name='Env secret',
            value='DJ_SETTING',
        )
        self.assertIsNone(secret.get_key())
        plain = secret.get_secret()
        self.assertEqual(plain, 'Djang0_$3cRe7')

    def test_crypto(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY,
            name='Env secret',
            value='gAAAAABhlEIfjOMlecHFkxeVg-vik9UU89kuwPiopAcV266PpAOC8J1d9Igi_p-'
                  'B0oOAt3qSuKGHFPtuUr5Fi0qMwG7fONwAqrHdTYhgZ6AAEI4KbZB10ME=',
            key='$3cRe7_K3y',
        )
        self.assertEqual(secret.get_key(), b'0000000000000000000000$3cRe7_K3y')
        plain = secret.get_secret()
        self.assertEqual(plain, 'encrypted secret')

    def test_gen_crypto(self):
        secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY,
            name='Env secret',
            value='new secret',
            key='$3cRe7_K3y',
        )
        self.assertEqual(secret.get_secret(), 'new secret')

    def test_crypto_env(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_ENVIRONMENT,
            name='Env secret',
            value='gAAAAABhlERd6FH27JrVpf_zOETqZ-8EMZqFRJ7K4vCbDlkNNzSZND2pAseZ7OFXVWVZWLE-'
                  '8F8hYDGedbiyzZdurU_kptyNQkiPyhLEIhe_4CSWSpl_jn4=',
            key='SECRET_ENV',
        )
        self.assertEqual(secret.get_key(), b'0000000000000003nv1R0nM3t_$3cRe7')
        plain = secret.get_secret()
        self.assertEqual(plain, 'encrypted secret')

    def test_gen_crypto_env(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY_ENVIRONMENT,
            name='Env secret',
            value='new secret',
            key='SECRET_ENV',
        )
        self.assertEqual(secret.get_secret(), 'new secret')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_crypto_django(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='Env secret',
            value='gAAAAABhlEP6XGoYB2iIVXsTAKOUPaxrZjPwMLuXTf5aW0ubqU49Hetjmo3I4X6WVG3HhkyZkbCo_'
                  'BQ0zJjqlcgnjkuV82ZMn8oZJYOUQW0DyATEEOoTs0o=',
            key='DJ_SETTING',
        )
        self.assertEqual(secret.get_key(), b'0000000000000000000Djang0_$3cRe7')
        plain = secret.get_secret()
        self.assertEqual(plain, 'encrypted secret')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_gen_crypto_django(self):
        secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='Env secret',
            value='new secret',
            key='DJ_SETTING',
        )
        self.assertEqual(secret.get_secret(), 'new secret')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_crypto_django_settings(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='Env secret',
            value='gAAAAABhlSvJmAHL-g7KLvDLqOuvXRkb_ZQ4v0arLQ_ZFlo5-B1CQl-'
                  '6uR6ARQ86FlpeJq4ZuzgS2zLV4w4S9ByoojKKU2YaCJDiyPLYvVAUA6Kclrp5l0w='
        )
        self.assertEqual(secret.get_key(), b'django-insecure-h@er^@nmxpjxxv$(')
        plain = secret.get_secret()
        self.assertEqual(plain, 'encrypted secret')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_gen_crypto_django_settings(self):
        secret = SecretKey.objects.create_secret(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='Env secret',
            value='new secret',
        )
        self.assertEqual(secret.get_secret(), 'new secret')


class SecretKeyValidationTestCase(BaseValidationTestCase):

    def test_invalid_environment(self):
        secret = SecretKey(
            mode=MODE_ENVIRONMENT,
            name='Env secret',
            value='NOT_EXISTS_ENV',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Environment "NOT_EXISTS_ENV" not found.'
        self.assertValidation(error_context, 'value', message)

    def test_environment_with_key(self):
        secret = SecretKey(
            mode=MODE_ENVIRONMENT,
            name='Env secret',
            value='NOT_EXISTS_ENV',
            key='invalid'
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Key only valid for cryptography mode.'
        self.assertValidation(error_context, 'key', message)

    def test_invalid_crypto_environment(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_ENVIRONMENT,
            name='Env crypto secret',
            value='-',
            key='NOT_EXISTS_ENV',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Environment "NOT_EXISTS_ENV" not found.'
        self.assertValidation(error_context, 'key', message)

    def test_crypto_environment_without_key(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_ENVIRONMENT,
            name='Env crypto secret',
            value='-',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'This field is required.'
        self.assertValidation(error_context, 'key', message)

    def test_invalid_settings(self):
        secret = SecretKey(
            mode=MODE_DJANGO_SETTINGS,
            name='django setting',
            value='NOT_EXISTS_SET',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Setting "NOT_EXISTS_SET" not found.'
        self.assertValidation(error_context, 'value', message)

    def test_settings_with_key(self):
        secret = SecretKey(
            mode=MODE_DJANGO_SETTINGS,
            name='django setting',
            value='NOT_EXISTS_SET',
            key='invalid'
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Key only valid for cryptography mode.'
        self.assertValidation(error_context, 'key', message)

    @override_settings(ARRAY_SETTING=[1, 2])
    def test_settings_with_no_str(self):
        secret = SecretKey(
            mode=MODE_DJANGO_SETTINGS,
            name='django setting',
            value='ARRAY_SETTING',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Invalid type for setting "ARRAY_SETTING", only str is allowed.'
        self.assertValidation(error_context, 'value', message)

    def test_invalid_crypto_settings(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='django setting',
            value='-',
            key='NOT_EXISTS_SET',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Setting "NOT_EXISTS_SET" not found.'
        self.assertValidation(error_context, 'key', message)

    @override_settings(ARRAY_SETTING=[1, 2])
    def test_invalid_crypto_settings_with_no_str(self):
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY_DJANGO,
            name='django setting',
            value='-',
            key='ARRAY_SETTING',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Invalid type for setting "ARRAY_SETTING", only str is allowed.'
        self.assertValidation(error_context, 'key', message)


class WithoutCryptoSupportTestCase(BaseValidationTestCase):
    @patch('django_easy_report.models.Fernet')
    def test_secret_key_clean(self, fernet_mock):
        fernet_mock.__bool__.return_value = False
        secret = SecretKey(
            mode=MODE_CRYPTOGRAPHY,
            name='crypto',
            value='-',
            key='secret',
        )

        with self.assertRaises(ValidationError) as error_context:
            secret.clean()

        message = 'Invalid mode, cryptography not supported.'
        self.assertValidation(error_context, 'mode', message)

    @patch('django_easy_report.models.Fernet')
    def test_secret_key_create(self, fernet_mock):
        fernet_mock.__bool__.return_value = False

        with self.assertRaises(ValidationError) as error_context:
            SecretKey.objects.create_secret(
                mode=MODE_CRYPTOGRAPHY,
                name='crypto',
                value='-',
                key='secret',
            )

        self.assertTrue(hasattr(error_context, 'exception'))
        message = 'Invalid mode, "cryptography.fernet.Fernet" cannot be imported.'
        self.assertEqual(message, error_context.exception.message)

    @patch('django_easy_report.utils.Fernet')
    def test_encrypt(self, fernet_mock):
        fernet_mock.__bool__.return_value = False
        with self.assertRaises(ImportError) as error_context:
            utils.encrypt('key', 'plain')
        self.assertTrue(hasattr(error_context, 'exception'))
        message = 'Cannot import cryptography.fernet.Fernet'
        self.assertEqual(message, error_context.exception.msg)


class TestClass(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class ReplaceSecretTestCase(BaseValidationTestCase):
    def test_create_class_with_replace(self):
        json_params = """{
            "direct": ${secret},
            "in_obj": {"key": ${secret}}
        }"""
        replace = {'secret': '\'$ECRET\\"'}
        cls = utils.create_class('django_easy_report.tests.test_secret.TestClass', json_params, replace=replace)
        self.assertEqual(cls.kwargs.get('direct'), '\'$ECRET\\"')
        self.assertEqual(cls.kwargs.get('in_obj', {}).get('key'), '\'$ECRET\\"')

    @override_settings(SECRET_KEY='django-insecure-h@er^@nmxpjxxv$(id7wfeo(1ca$0)2i+w3+ox0z391h%i84&1')
    @override_settings(DJ_SETTING='Djang0_$3cRe7')
    def test_model_with_secrets(self):
        os.environ.setdefault('SECRET_ENV', '3nv1R0nM3t_$3cRe7')
        raise NotImplementedError()
