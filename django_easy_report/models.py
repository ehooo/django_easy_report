import hashlib
import json

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from django_easy_report.reports import ReportBaseGenerator
from django_easy_report.utils import create_class, import_class


class ReportSender(models.Model):
    """
    Model used for persist the report.
    """
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=32, unique=True, db_index=True)
    email_from = models.EmailField(
        null=True, blank=True,
        help_text=_('If have content email must be send when report is completed.')
    )
    size_to_attach = models.PositiveIntegerField(
        default=0,
        help_text=_('If size is bigger, the file will be upload using storage system, '
                    'otherwise the file will be send as attached on the email.')
    )
    storage_class_name = models.CharField(
        max_length=64, null=True, blank=True,
        help_text=_('Class name for for save the report. '
                    'It must be subclass of django.core.files.storage.Storage')
    )
    storage_init_params = models.TextField(
        blank=True, help_text=_('JSON with init parameters')
    )

    def __str__(self):
        return self.name

    def clean(self):
        super(ReportSender, self).clean()

        errors = {}
        if self.storage_init_params:
            try:
                json.loads(self.storage_init_params)
            except json.JSONDecodeError:
                errors.update({
                    'storage_init_params': _('Invalid JSON')
                })

        if self.storage_class_name:
            try:
                cls = import_class(self.storage_class_name)
                if not issubclass(cls, Storage):
                    errors.update({
                        'storage_class_name': 'Invalid class "{}", must be instance of Storage'.format(
                            self.storage_class_name
                        )
                    })
            except (ImportError, ValueError):
                errors.update({
                    'storage_class_name': _('Class "{}" cannot be imported').format(
                        self.storage_class_name
                    )
                })
            if 'storage_init_params' not in errors:
                try:
                    self.get_storage()
                except TypeError as type_error:
                    errors.update({
                        'storage_init_params': str(type_error)
                    })
                except Exception as ex:
                    errors.update({
                        'storage_init_params': _('Error creating storage class: "{}"').format(ex)
                    })

        if not any([self.email_from, self.storage_class_name]):
            errors.update(
                _('Email or Storage class must be entered')
            )

        if errors:
            raise ValidationError(errors)

    def get_storage(self):
        if not self.storage_class_name:
            return
        cls = create_class(self.storage_class_name, self.storage_init_params)
        if not isinstance(cls, Storage):
            raise ImportError('Only Storage classes are allowed')
        return cls


class ReportGenerator(models.Model):
    """
    Model for Report object creation information.
    What is the report class, construction params, sender information and so on.
    """
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(
        max_length=32, unique=True, db_index=True,
        validators=[
            RegexValidator(
                regex=r'[\w-]+',
                message='Only valid characters (a-zA-Z0-9_-)',
            )
        ]
    )
    class_name = models.CharField(
        max_length=64,
        help_text=_('Class name for for generate the report. '
                    'It must be subclass of django_easy_report.reports.ReportBaseGenerator')
    )
    init_params = models.TextField(blank=True, help_text=_('JSON with init parameters'))
    sender = models.ForeignKey(ReportSender, on_delete=models.PROTECT)
    permissions = models.CharField(
        max_length=1024, blank=True, null=True,
        help_text=_(
            'Comma separated permission list. Permission formatted as: {}'
        ).format(
            '&lt;content_type.app_label&gt;.&lt;content_type.model&gt;.&lt;permission.codename&gt;'
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

    def __str__(self):
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

        if self.class_name:
            try:
                cls = import_class(self.class_name)
                if not issubclass(cls, ReportBaseGenerator):
                    errors.update({
                        'class_name': _('Invalid class "{}", must be instance of ReportBaseGenerator').format(
                            self.class_name
                        )
                    })
            except (ImportError, ValueError):
                errors.update({
                    'class_name': _('Class "{}" cannot be imported').format(
                        self.class_name
                    )
                })
            if 'init_params' not in errors:
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

        if self.permissions:
            perm_errors = []
            for permission in self.get_permissions_list():
                try:
                    app_label, model, codename = permission.split('.')
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                    Permission.objects.get(content_type=ct, codename=codename)
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

    def get_permissions_list(self):
        permissions = []
        if self.permissions:
            permissions = [p.strip() for p in self.permissions.split(',')]
        return permissions

    def get_report(self):
        cls = create_class(self.class_name, self.init_params)
        if not isinstance(cls, ReportBaseGenerator):
            raise ImportError('Only ReportBaseGenerator classes are allowed')
        return cls


class ReportQuery(models.Model):
    """
    Model with Report information, only the information required for generate it.
    All information related to generation, nothing related to sender.
    """
    STATUS_CREATED = 0
    STATUS_WORKING = 10
    STATUS_DONE = 20
    STATUS_ERROR = 30

    STATUS_OPTIONS = [
        (STATUS_CREATED, _('Created')),
        (STATUS_WORKING, _('Working')),
        (STATUS_DONE, _('Done')),
        (STATUS_ERROR, _('Error'))
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_OPTIONS, default=STATUS_CREATED)
    report = models.ForeignKey(ReportGenerator, on_delete=models.PROTECT)
    filename = models.CharField(max_length=32)
    mimetype = models.CharField(max_length=32, default='application/octet-stream')
    params = models.TextField(blank=True)
    params_hash = models.CharField(max_length=128)
    storage_path_location = models.CharField(max_length=512, blank=True, null=True)

    class Meta:
        ordering = ('created_at', )

    @staticmethod
    def gen_hash(data_dict):
        sha = hashlib.sha1()
        for key in sorted(data_dict.keys()):
            sha.update(key.encode())
            value = data_dict.get(key)
            if isinstance(value, dict):
                value = ReportQuery.gen_hash(**value)
            sha.update(str(value).encode())
        return sha.hexdigest()

    def get_report(self):
        report = self.report.get_report()
        kwargs = {}
        if self.params:
            kwargs = json.loads(self.params)
        return report.setup(self, **kwargs)

    def get_file(self):
        storage = self.report.sender.get_storage()
        if not self.report.always_download:
            try:
                return redirect(storage.url(self.storage_path_location))
            except NotImplementedError:
                pass
        return storage.open(self.storage_path_location, 'r')


@receiver(pre_delete, sender=ReportQuery)
def delete_report_from_storage(sender, instance, **kwargs):
    if instance.storage_path_location and instance.report.preserve_report:
        return
    storage = instance.report.sender.get_storage()
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

    def clean(self):
        super(ReportRequester, self).clean()

        if self.user_params:
            try:
                json.loads(self.user_params)
            except json.JSONDecodeError:
                raise ValidationError({
                    'user_params': _('Invalid JSON')
                })
