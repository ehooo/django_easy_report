import json
import string

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.utils.translation import gettext as _

from django_easy_report.choices import MODE_CRYPTOGRAPHY
from django_easy_report.models import ReportSender, SecretKey
from django_easy_report.utils import create_class, import_class, encrypt


class SendEmailForm(forms.Form):
    send_to = forms.EmailField()


class SecretKeyForm(forms.ModelForm):
    class Meta:
        model = SecretKey
        fields = '__all__'

    def clean(self):
        super(SecretKeyForm, self).clean()
        key = self.cleaned_data.get('key')
        mode = self.cleaned_data.get('mode')
        if not self.instance.id and mode and mode & MODE_CRYPTOGRAPHY:
            secret = SecretKey(mode=mode, key=key)
            try:
                key = secret.get_key()
                if not key:
                    raise ValidationError({'key': _('This field is required.')})
            except TypeError:
                return self.cleaned_data
            self.cleaned_data['value'] = encrypt(key, self.cleaned_data.get('value'))
        return self.cleaned_data

class ReportSenderForm(forms.ModelForm):
    class Meta:
        model = ReportSender
        fields = '__all__'

    def clean(self):
        errors = {}
        replace = {}
        if self.cleaned_data.get('storage_init_params'):
            try:
                # Get secret replace information
                replace_data = {}
                for key, value in self.data.items():
                    parts = key.split('-')
                    if len(parts) == 3 and parts[0] == 'secretreplace_set':
                        pos = parts[1]
                        if pos not in replace_data:
                            replace_data[pos] = {}
                        key = parts[2]
                        replace_data[pos][key] = value
                # Get values for secrets
                for data in replace_data.values():
                    if data.get('DELETE'):
                        continue
                    if data.get('secret') and data.get('replace_word'):
                        try:
                            secret = SecretKey.objects.get(id=data.get('secret'))
                            replace[data.get('replace_word')] = json.dumps(secret.get_secret())
                        except SecretKey.DoesNotExist:
                            pass

                # Replace secrets
                storage_init_params = self.cleaned_data.get('storage_init_params')
                template = string.Template(storage_init_params)
                json_params = template.safe_substitute(**replace)
                # Check Json
                json.loads(json_params)
            except json.JSONDecodeError:
                errors.update({
                    'storage_init_params': _('Invalid JSON')
                })

        storage_class_name = self.cleaned_data.get('storage_class_name')
        try:
            cls = import_class(storage_class_name)
            if not issubclass(cls, Storage):
                errors.update({
                    'storage_class_name': 'Invalid class "{}", must be instance of Storage'.format(
                        storage_class_name
                    )
                })
            elif 'storage_init_params' not in errors:
                try:
                    cls = create_class(storage_class_name,
                                       self.cleaned_data.get('storage_init_params'),
                                       replace=replace)
                    if not isinstance(cls, Storage):
                        raise ImportError('Only Storage classes are allowed')
                except TypeError as type_error:
                    errors.update({
                        'storage_init_params': str(type_error)
                    })
                except Exception as ex:
                    errors.update({
                        'storage_init_params': _('Error creating storage class: "{}"').format(ex)
                    })

        except (ImportError, ValueError):
            errors.update({
                'storage_class_name': _('Class "{}" cannot be imported').format(
                    storage_class_name
                )
            })

        if errors:
            raise ValidationError(errors)
