import datetime
import json
import os
from csv import DictWriter
from gettext import gettext as _
from io import BytesIO, StringIO

from django.core.exceptions import ValidationError
from django.forms.utils import ErrorDict

from django_easy_report.constants import STATUS_DONE, STATUS_ERROR, STATUS_OPTIONS
from django_easy_report.utils import import_class


class ReportBaseGenerator(object):
    XLS_MAX_ROWS = 65536
    XLS_MAX_COLUMNS = 256

    XLSX_MAX_ROWS = 1048576
    XLSX_MAX_COLUMNS = 16384

    ODS_MAX_ROWS = 1048576
    ODS_MAX_COLUMNS = 1024

    mimetype = 'application/octet-stream'
    form_class = None
    using = None

    def __init__(self, **kwargs):
        self.setup_params = {}
        self.report_model = None
        self.form = None
        self.buffer = BytesIO()
        self.reset()

    def reset(self):
        self.setup_params = {}
        self.report_model = None
        self.form = None
        self.buffer = BytesIO()

    def setup(self, report_model, **kwargs):
        """
        :param report_model:
        :type report_model: django_easy_report.models.ReportQuery
        :param kwargs: setup_params
        :return: None
        """
        self.setup_params = kwargs
        self.report_model = report_model

    def get_email(self, requester):
        """
        :type requester: django_easy_report.models.ReportRequester
        :return:
        """
        return getattr(requester.user, requester.user.get_email_field_name())

    def get_form(self, data):
        if not self.form and self.form_class:
            self.form = self.form_class(data)
        return self.form

    def validate(self, data):
        form = self.get_form(data)
        if form and not form.is_valid():
            return form.errors

    def get_params(self, data):  # pragma: no cover
        """
        :param data:
        :type data: dict
        :return: user_params, report_params
        """
        return {}, data

    def get_filename(self):  # pragma: no cover
        raise NotImplementedError()

    def get_mimetype(self):
        return self.mimetype

    def generate(self):  # pragma: no cover
        raise NotImplementedError()

    def get_remote_path(self):
        path_parts = [
            self.report_model.report.name,
            self.report_model.params_hash,
            self.report_model.created_at.strftime("%Y%m%d-%H%M"),
            self.report_model.filename
        ]
        return os.path.join(*path_parts)

    def save(self):
        self.buffer.seek(0)
        filepath = self.get_remote_path()
        storage = self.report_model.report.sender.get_storage()
        name = storage.save(filepath, self.buffer)
        return name

    def get_subject(self, requester):
        return '{}'.format(self.__class__.__name__)

    def get_message(self, report_status, requester, attachment=None, link=None):
        if report_status == STATUS_DONE:
            return self.get_done_message(requester, attachment, link)
        elif report_status == STATUS_ERROR:
            return self.get_error_message()
        status = report_status
        status_options = dict(STATUS_OPTIONS)
        if report_status in status_options:
            status = status_options[report_status]
        return _('Invalid status ({})').format(status)

    def get_error_message(self):
        return _('Something was wrong')

    def get_done_message(self, requester=None, attachment=None, url=None):
        msg = _('Report completed.')
        if attachment:
            return _('{msg} See attachments').format(msg=msg)
        link = '<a href="{url}">{here}<a/>'.format(url=url, here=_('here'))
        return _('{msg} Download from {link}').format(msg=msg, link=link)


class ReportModelGenerator(ReportBaseGenerator):
    mimetype = 'text/csv'

    def __init__(self, model, fields,
                 form_class_name=None,
                 user_fields=None,
                 email_field=None,
                 **kwargs):
        super(ReportModelGenerator, self).__init__(**kwargs)
        try:
            self.model_cls = import_class(model)
        except ValueError:
            raise ImportError('Cannot import model "{}"'.format(model))
        # Check fields are valid
        self.model_cls.objects.only(*fields).last()
        self.fields = fields
        self.form_class = None
        if form_class_name:
            self.form_class = import_class(form_class_name)
        self.email_field = email_field or ''
        self.user_fields = user_fields or []

    def reset(self):
        super(ReportModelGenerator, self).reset()
        self.buffer = StringIO()

    def validate(self, data):
        errors = super(ReportModelGenerator, self).validate(data)
        if self.form:
            if not errors:
                errors = ErrorDict()
            for key, value in data.items():
                if not (key in self.user_fields or key in self.form.fields):
                    errors[key] = ValidationError(_('Invalid field {}').format(key))
        return errors

    def get_params(self, data):
        user_params, report_params = {}, {}
        for key, value in data.items():
            if key == self.email_field or key in self.user_fields:
                user_params[key] = value
            else:
                report_params[key] = value
        return user_params, report_params

    def get_queryset(self):
        items = self.model_cls.objects.all()
        if self.using:
            items = items.using(self.using)
        return items.only(*self.fields)

    def get_filename(self):
        utc_now = datetime.datetime.utcnow()
        return "{}_{}.csv".format(
            self.model_cls.__class__.__name__,
            utc_now.strftime('%Y%m%d-%M%S')
        )

    def generate(self):
        reader = DictWriter(self.buffer, self.fields)
        reader.writeheader()
        for item in self.get_queryset():
            row = self.get_row(item)
            reader.writerow(row)

    def get_email(self, requester):
        """
        :type requester: django_easy_report.models.ReportRequester
        :return: email
        :rtype: str
        """
        if self.email_field:
            user_params = json.loads(requester.user_params)
            if self.email_field in user_params:
                return user_params[self.email_field]
        return getattr(requester.user, requester.user.get_email_field_name())

    def get_row(self, obj, default=''):
        """
        :param obj: Object model instance
        :param default: Default value
        :type default: str
        :return: row
        :rtype: dict
        """
        row = {}
        for header in self.fields:
            row[header] = getattr(obj, header, default)
        return row
