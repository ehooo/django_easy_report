import base64
import json
import os
import string

from django.conf import settings

from django_easy_report.choices import (
    MODE_CRYPTOGRAPHY,
    MODE_DJANGO_SETTINGS,
    MODE_ENVIRONMENT,
)

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    Fernet = None


def import_class(class_name):
    mod_name, cls_name = class_name.rsplit('.', 1)
    module = __import__(mod_name, fromlist=[cls_name])
    try:
        return getattr(module, cls_name)
    except AttributeError:
        raise ImportError('Cannot import class {}'.format(class_name))


def create_class(class_name, json_params, replace=None):
    cls = import_class(class_name)
    kwargs = {}
    if json_params:
        if isinstance(replace, dict):
            safe_replace = {}
            for key, value in replace.items():
                safe_replace[key] = json.dumps(value)
            template = string.Template(json_params)
            json_params = template.safe_substitute(**safe_replace)
        kwargs = json.loads(json_params)
    return cls(**kwargs)


def get_key(mode, key=None):
    if mode & MODE_CRYPTOGRAPHY:
        final_key = settings.SECRET_KEY
        if mode == MODE_CRYPTOGRAPHY:
            final_key = key
        elif mode & MODE_ENVIRONMENT:
            final_key = os.environ.get(key, '')
        elif (
                mode & MODE_DJANGO_SETTINGS and
                key and hasattr(settings, key)
        ):
            final_key = getattr(settings, key)
        if not isinstance(final_key, str):
            raise TypeError('Invalid key type "{}" is not allowed, only str is valid'.format(
                type(final_key).__name__)
            )
        size = len(final_key)
        if size >= 32:
            final_key = final_key[:32]
        else:
            final_key = final_key.zfill(32)
        return final_key.encode()


def encrypt(key, plain):
    if not Fernet:
        raise ImportError('Cannot import cryptography.fernet.Fernet')

    key = base64.urlsafe_b64encode(key)
    return Fernet(key).encrypt(plain.encode()).decode()
