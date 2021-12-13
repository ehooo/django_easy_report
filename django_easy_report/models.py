import base64
import hashlib
import json
import os

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from django_easy_report.choices import MODE_ENVIRONMENT, MODE_DJANGO_SETTINGS, MODE_CRYPTOGRAPHY, \
    MODE_CRYPTOGRAPHY_ENVIRONMENT, MODE_CRYPTOGRAPHY_DJANGO
from django_easy_report.constants import STATUS_CREATED, STATUS_OPTIONS
from django_easy_report.reports import ReportBaseGenerator
from django_easy_report.utils import create_class, import_class, get_key, encrypt

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception


class SecretKeyManager(models.Manager):
    def create_secret(self, **kwargs):
        mode = kwargs.get('mode')
        if mode & MODE_CRYPTOGRAPHY:
            if not Fernet:
                raise ValidationError('Invalid mode, "cryptography.fernet.Fernet" cannot be imported.')
            key = get_key(mode, kwargs.get('key'))
            kwargs['value'] = encrypt(key, kwargs.pop('value'))
        return self.create(**kwargs)


class SecretKey(models.Model):
    MODE_CHOICES = [
        (MODE_ENVIRONMENT, _('Environment')),
        (MODE_DJANGO_SETTINGS, _('Django Settings')),
    ]
    if Fernet:
        MODE_CHOICES.extend([
            (MODE_CRYPTOGRAPHY, _('Cryptography')),
            (MODE_CRYPTOGRAPHY_ENVIRONMENT, _('Cryptography from Environment key')),
            (MODE_CRYPTOGRAPHY_DJANGO, _('Cryptography from Django secret')),
        ])
    mode = models.PositiveSmallIntegerField(choices=MODE_CHOICES)
    name = models.CharField(max_length=64, unique=True)
    value = models.CharField(
        max_length=512,
        help_text=_('Environment key, Django setting name or with Cryptography mode encrypted value')
    )
    key = models.CharField(
        max_length=32, blank=True, null=True,
        help_text=_('With Cryptography: Environment key, Django setting name or Secret key')
    )

    objects = SecretKeyManager()

    def __str__(self):  # pragma: no cover
        return self.name

    def get_key(self):
        if Fernet and self.mode & MODE_CRYPTOGRAPHY:
            return get_key(self.mode, self.key)

    def get_secret(self):
        if self.mode == MODE_ENVIRONMENT:
            return os.environ.get(self.value)
        elif self.mode == MODE_DJANGO_SETTINGS:
            return getattr(settings, self.value, None)
        elif (
                Fernet and self.mode & MODE_CRYPTOGRAPHY
        ):
            key = base64.urlsafe_b64encode(self.get_key())
            return Fernet(key).decrypt(self.value.encode()).decode()

    def clean(self):
        super(SecretKey, self).clean()

        if not self.mode:
            raise ValidationError({'key': _('Invalid type.')})
        elif self.mode in [MODE_ENVIRONMENT, MODE_DJANGO_SETTINGS] and self.key:
            raise ValidationError({'key': _('Key only valid for cryptography mode.')})
        if not Fernet and self.mode & MODE_CRYPTOGRAPHY:
            raise ValidationError({'mode': _('Invalid mode, cryptography not supported.')})
        self._clean_environment()
        self._clean_django_settings()
        self._clean_cryptography()

    def _clean_environment(self):
        if self.mode & MODE_ENVIRONMENT:
            field = 'value'
            env = self.value
            if self.mode & MODE_CRYPTOGRAPHY:
                if not self.key:
                    raise ValidationError({'key': _('This field is required.')})
                field = 'key'
                env = self.key
            if not env or env not in os.environ:
                raise ValidationError({field: _('Environment "{}" not found.').format(env)})

    def _clean_django_settings(self):
        if self.mode & MODE_DJANGO_SETTINGS:
            if self.mode & MODE_CRYPTOGRAPHY:
                if self.key:
                    if not hasattr(settings, self.key):
                        raise ValidationError({'key': _('Setting "{}" not found.').format(self.key)})
                    elif not isinstance(getattr(settings, self.key), str):
                        raise ValidationError({
                            'key': _('Invalid type for setting "{}", only str is allowed.').format(self.key)
                        })
            elif not hasattr(settings, self.value):
                raise ValidationError({'value': _('Setting "{}" not found.').format(self.value)})
            elif not isinstance(getattr(settings, self.value), str):
                raise ValidationError({
                    'value': _('Invalid type for setting "{}", only str is allowed.').format(self.value)
                })

    def _clean_cryptography(self):
        if self.mode & MODE_CRYPTOGRAPHY:
            try:
                key = self.get_key()
                if key is None:  # pragma: no cover
                    # This never must happen
                    raise ValidationError({
                        'key': _('Invalid value.')
                    })
            except TypeError:
                raise ValidationError({
                    'key': _('Invalid type.')
                })
            try:
                if self.get_secret() is None:  # pragma: no cover
                    # This never must happen
                    raise ValidationError({
                        'value': _('Invalid secret.')
                    })
            except InvalidToken:
                raise ValidationError({
                    'value': _('Invalid secret.')
                })


class ReportSender(models.Model):
    """
    Model used for persist the report.
    """
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=32, unique=True, db_index=True)
    email_from = models.EmailField(
        blank=True, null=True,
        help_text=_('If have content email must be send when report is completed.')
    )
    size_to_attach = models.PositiveIntegerField(
        default=0,
        help_text=_('If size is bigger, the file will be upload using storage system, '
                    'otherwise the file will be send as attached on the email.')
    )
    storage_class_name = models.CharField(
        max_length=64,
        help_text=_('Class name for for save the report. '
                    'It must be subclass of django.core.files.storage.Storage')
    )
    storage_init_params = models.TextField(
        blank=True, null=True, help_text=_('JSON with init parameters')
    )

    def __init__(self, *args, **kwargs):
        super(ReportSender, self).__init__(*args, **kwargs)
        self.__storage = None

    def __str__(self):  # pragma: no cover
        return self.name

    def get_storage(self, force_load=False):
        """
        :return:
        :rtype: Storage
        """
        if self.__storage is None or force_load:
            replace = {}
            for replace_item in self.secretreplace_set.all():
                replace[replace_item.replace_word] = replace_item.secret.get_secret()
            cls = create_class(self.storage_class_name, self.storage_init_params, replace=replace)
            if not isinstance(cls, Storage):
                raise ImportError('Only Storage classes are allowed')
            self.__storage = cls
        return self.__storage

    def clean(self):
        super(ReportSender, self).clean()
        if (
            hasattr(settings, 'SENDER_CLASSES') and
            isinstance(settings.SENDER_CLASSES, (list, tuple)) and
            self.storage_class_name not in settings.SENDER_CLASSES
        ):
            raise ValidationError({
                'storage_class_name': _('Invalid class "{}" must be added on SENDER_CLASSES').format(
                    self.storage_class_name
                )
            })


class SecretReplace(models.Model):
    secret = models.ForeignKey(SecretKey, on_delete=models.PROTECT)
    sender = models.ForeignKey(ReportSender, on_delete=models.CASCADE)
    replace_word = models.SlugField(
        max_length=16,
        help_text=_('Word that will be replaced on "storage init params" field if is market as "${WORD}"')
    )

    class Meta:
        unique_together = (('secret', 'sender'), ('sender', 'replace_word'))


class ReportGenerator(models.Model):
    """
    Model for Report object creation information.
    What is the report class, construction params, sender information and so on.
    """
    updated_at = models.DateTimeField(auto_now=True)
    name = models.SlugField(
        max_length=32, unique=True, db_index=True,
    )
    class_name = models.CharField(
        max_length=64,
        help_text=_('Class name for for generate the report. '
                    'It must be subclass of django_easy_report.reports.ReportBaseGenerator')
    )
    init_params = models.TextField(blank=True, null=True, help_text=_('JSON with init parameters'))
    sender = models.ForeignKey(ReportSender, on_delete=models.PROTECT)
    permissions = models.CharField(
        max_length=1024, blank=True, null=True,
        help_text=_(
            'Comma separated permission list. Permission formatted as: {}'
        ).format(
            '&lt;content_type.app_label&gt;.&lt;permission.codename&gt;'
        )
    )
    always_generate = models.BooleanField(
        default=False,
        help_text=_('Do not search for similar reports previously generated')
    )
    always_download = models.BooleanField(
        default=False,
        help_text=_('Never will redirect to storage URL')
    )
    preserve_report = models.BooleanField(
        default=False,
        help_text=_('If model is deleted, do not remove the file on storage')
    )

    def __init__(self, *args, **kwargs):
        super(ReportGenerator, self).__init__(*args, **kwargs)
        self.__report = None

    def __str__(self):  # pragma: no cover
        return self.name

    def clean(self):
        super(ReportGenerator, self).clean()

        errors = {}
        if self.init_params:
            try:
                json.loads(self.init_params)
            except json.JSONDecodeError:
                errors.update({
                    'init_params': _('Invalid JSON')
                })

        try:
            cls = import_class(self.class_name)
            if not issubclass(cls, ReportBaseGenerator):
                errors.update({
                    'class_name': _('Invalid class "{}", must be instance of ReportBaseGenerator').format(
                        self.class_name
                    )
                })
            elif 'init_params' not in errors:
                try:
                    self.get_report()
                except TypeError as type_error:
                    errors.update({
                        'init_params': str(type_error)
                    })
                except Exception as ex:
                    errors.update({
                        'init_params': _('Error creating report class: "{}"').format(ex)
                    })

        except (ImportError, ValueError):
            errors.update({
                'class_name': _('Class "{}" cannot be imported').format(
                    self.class_name
                )
            })

        if self.permissions:
            perm_errors = []
            for permission in self.get_permissions():
                try:
                    app_label, codename = permission.rsplit('.')
                    ct = ContentType.objects.filter(app_label=app_label)
                    if not ct.exists():
                        raise ContentType.DoesNotExist()
                    Permission.objects.get(content_type__in=ct, codename=codename)
                except Permission.DoesNotExist:
                    perm_errors.append(_('Unknown code name for permission: "{}"').format(permission))
                except ContentType.DoesNotExist:
                    perm_errors.append(_('Unknown content type for permission: "{}"').format(permission))
                except ValueError:
                    perm_errors.append(_('Invalid permission: "{}"').format(permission))
            if perm_errors:
                errors.update({
                    'permissions': perm_errors
                })

        if errors:
            raise ValidationError(errors)

        if (
            hasattr(settings, 'REPORT_CLASSES') and
            isinstance(settings.REPORT_CLASSES, (list, tuple)) and
            self.class_name not in settings.REPORT_CLASSES
        ):
            raise ValidationError({
                'class_name': _('Invalid class "{}" must be added on REPORT_CLASSES').format(
                    self.class_name
                )
            })

    def get_permissions(self):
        permissions = set()
        if self.permissions:
            permissions = set([p.strip() for p in self.permissions.split(',')])
        return permissions

    def get_report(self, force=False):
        if self.__report is None or force:
            cls = create_class(self.class_name, self.init_params)
            if not isinstance(cls, ReportBaseGenerator):
                raise ImportError('Only ReportBaseGenerator classes are allowed')
            self.__report = cls
        return self.__report


class ReportQuery(models.Model):
    """
    Model with Report information, only the information required for generate it.
    All information related to generation, nothing related to sender.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_OPTIONS, default=STATUS_CREATED)
    report = models.ForeignKey(ReportGenerator, on_delete=models.PROTECT)
    filename = models.CharField(max_length=32)
    mimetype = models.CharField(max_length=32, default='application/octet-stream')
    params = models.TextField(blank=True, null=True)
    params_hash = models.CharField(max_length=128)
    storage_path_location = models.CharField(max_length=512, blank=True, null=True)

    class Meta:
        ordering = ('created_at', )

    def __init__(self, *args, **kwargs):
        super(ReportQuery, self).__init__(*args, **kwargs)
        self.__report = None
        self.__params = None

    def refresh_from_db(self, *args, **kwargs):
        super(ReportQuery, self).refresh_from_db(*args, **kwargs)
        self.__report = None
        self.__params = None

    def clean(self):
        super(ReportQuery, self).clean()

        if self.params:
            try:
                json.loads(self.params)
            except json.JSONDecodeError:
                raise ValidationError({
                    'params': _('Invalid JSON')
                })

    @staticmethod
    def gen_hash(data_dict):
        """
        :param data_dict:
        :return:
        :rtype: str
        """
        sha = hashlib.sha1()
        if data_dict:
            has_functions = hasattr(data_dict, 'keys') and hasattr(data_dict, 'get')
            if has_functions and callable(data_dict.keys) and callable(data_dict.get):
                for key in sorted(data_dict.keys()):
                    sha.update(key.encode())
                    value = data_dict.get(key)
                    if isinstance(value, dict):
                        value = ReportQuery.gen_hash(value)
                    elif isinstance(value, models.Model):
                        value = '{}({})'.format(
                            value.__class__.__class__, value.pk
                        )
                    sha.update(str(value).encode())
            else:
                raise TypeError('data_dict must implements keys and get functions')
        return sha.hexdigest()

    def get_report(self, force=False):
        """
        :rtype: ReportBaseGenerator
        """
        if self.__report is None or force:
            self.__report = self.report.get_report()
            self.__report.setup(self, **self.get_params())
        return self.__report

    def get_file_size(self):
        if not self.storage_path_location:
            return 0
        storage = self.report.sender.get_storage()
        return storage.size(self.storage_path_location)

    def get_url(self):
        storage = self.report.sender.get_storage()
        try:
            url = storage.url(self.storage_path_location)
            return url
        except NotImplementedError:  # pragma: no cover
            pass

    def get_file(self, open_file=None):
        storage = self.report.sender.get_storage()
        if open_file is None:
            open_file = self.report.always_download
        if not storage or not self.storage_path_location:
            return
        if not open_file:
            url = self.get_url()
            if url:
                return redirect(url)

        if storage.exists(self.storage_path_location):
            return storage.open(self.storage_path_location, 'r')

    def get_params(self):
        """
        :rtype: dict
        """
        if self.__params is None:
            self.__params = {}
            if self.params:
                self.__params = json.loads(self.params)
        return self.__params


@receiver(pre_delete, sender=ReportQuery)
def delete_report_from_storage(sender, instance, **kwargs):
    if instance.storage_path_location and instance.report.preserve_report:  # pragma: no cover
        return
    storage = instance.report.sender.get_storage()
    if storage:
        storage.delete(instance.storage_path_location)


class ReportRequester(models.Model):
    """
    Model with requester information.
    All information related to requester, for example, email to send the report, webhook, ... .
    """
    request_at = models.DateTimeField(auto_now_add=True)
    query = models.ForeignKey(ReportQuery, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_params = models.TextField(blank=True, null=True)
    notified = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super(ReportRequester, self).__init__(*args, **kwargs)
        self.__params = None

    def refresh_from_db(self, *args, **kwargs):
        super(ReportRequester, self).refresh_from_db(*args, **kwargs)
        self.__params = None

    def clean(self):
        super(ReportRequester, self).clean()

        if self.user_params:
            try:
                json.loads(self.user_params)
            except json.JSONDecodeError:
                raise ValidationError({
                    'user_params': _('Invalid JSON')
                })

    def get_params(self):
        """
        :rtype: dict
        """
        if self.__params is None:
            self.__params = {}
            if self.user_params:
                self.__params = json.loads(self.user_params)
        return self.__params
