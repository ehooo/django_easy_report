import datetime
import json
import os
from csv import DictWriter
from gettext import gettext as _

from django.core.exceptions import ValidationError
from django.forms.utils import ErrorDict

from django_easy_report.constants import STATUS_DONE, STATUS_ERROR, STATUS_OPTIONS
from django_easy_report.exceptions import DoNotSend
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
    binary = True
    using = None

    def __init__(self, **kwargs):
        self.setup_params = {}
        self.report_model = None
        self.form = None
        self.reset()

    def reset(self):
        """
        Clean internal attributes
        :return: None
        """
        self.setup_params = {}
        self.report_model = None
        self.form = None

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
        :return: email from requester
        :rtype: str
        """
        return getattr(requester.user, requester.user.get_email_field_name())

    def get_form(self, data):
        """
        :param data: data used on from_class call
        :type data: dict
        :return: None or Form instance
        :rtype: None|django.forms.Form
        """
        if not self.form and self.form_class:
            self.form = self.form_class(data)
        return self.form

    def validate(self, data):
        """
        :param data: data used to use on form
        :type data: dict
        :return: None or form.errors
        :rtype: None|dict
        """
        form = self.get_form(data)
        if form and not form.is_valid():
            return form.errors

    def get_params(self, data):  # pragma: no cover
        """
        :param data:
        :type data: dict
        :return: user_params, report_params
        :rtype: (dict, dict)
        """
        return {}, data

    def get_filename(self):  # pragma: no cover
        """
        :return: string with filename
        :rtype: str
        """
        raise NotImplementedError()

    def get_mimetype(self):
        """
        :return: string with mimetype
        :rtype: str
        """
        return self.mimetype

    def generate(self, buffer, tmp_dir):  # pragma: no cover
        """
        :param buffer: Buffer where write the report
        :param tmp_dir: Path were temporal files could be created
        :return: None
        """
        raise NotImplementedError()

    def get_remote_path(self):
        """
        :return: path used on remote storage
        :rtype: str
        """
        path_parts = [
            self.report_model.report.name,
            self.report_model.created_at.strftime("%Y%m%d-%H%M"),
            self.report_model.filename
        ]
        return os.path.join(*path_parts)

    def save(self, buffer):
        """
        Save buffer on remote storage
        :param buffer: Buffer with the report
        :return: path saved on remote storage
        :rtype: str
        """
        filepath = self.get_remote_path()
        storage = self.report_model.report.sender.get_storage()
        name = storage.save(filepath, buffer)
        return name

    def get_subject(self, requester):
        """
        :param requester: requester
        :type requester: django_easy_report.models.ReportRequester
        :return: Subject for email
        :rtype: str
        """
        return '{}'.format(self.__class__.__name__)

    def get_message(self, report_status, requester, attachment=None, link=None):
        """
        :param report_status: item on the list: django_easy_report.constants.STATUS_OPTIONS
        :type report_status: int
        :param requester:
        :type requester: django_easy_report.models.ReportRequester
        :param attachment: If the message have attachment file
        :type attachment: bool
        :param link: The link point to remote file
        :type link: str
        :return: Message body
        :rtype: str
        """
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
        """
        :return: Message used when error happen
        :rtype: str
        """
        return _('Something was wrong')

    def get_done_message(self, requester=None, attachment=None, url=None):
        """
        :param requester:
        :type requester: django_easy_report.models.ReportRequester
        :param attachment: If the message have attachment file
        :type attachment: bool
        :param link: The link point to remote file
        :type link: str
        :return: Message body
        :rtype: str
        """
        msg = _('Report completed.')
        if attachment:
            return _('{msg} See attachments').format(msg=msg)
        link = '<a href="{url}">{here}<a/>'.format(url=url, here=_('here'))
        return _('{msg} Download from {link}').format(msg=msg, link=link)


class ReportModelGenerator(ReportBaseGenerator):
    binary = False
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

    def generate(self, buffer, tmp_dir):
        reader = DictWriter(buffer, self.fields)
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
        return super(ReportModelGenerator, self).get_email(requester)

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


class AdminReportGenerator(ReportBaseGenerator):
    binary = False
    mimetype = 'text/csv'

    def __init__(self, **kwargs):
        super(AdminReportGenerator, self).__init__(**kwargs)
        self.fields = []
        self.admin_class = None
        self.model_class = None
        self.sql = None
        self.using = kwargs.get('using', None)
        self.send_email = kwargs.get('send_email', True)

    def get_filename(self):
        utc_now = datetime.datetime.utcnow()
        return "{}_{}.csv".format(
            self.admin_class.__name__, utc_now.strftime('%Y%m%d-%M%S')
        )

    def validate(self, data):
        return {'__all__': ValidationError(_('This report is only valid for Admin page'))}

    def get_message(self, *args, **kwargs):
        if self.send_email:
            return super(AdminReportGenerator, self).get_message(*args, **kwargs)
        raise DoNotSend()

    def setup(self, report_model, **kwargs):
        self.setup_params = kwargs
        self.report_model = report_model
        self.fields = kwargs.get('fields', [])
        self.sql = kwargs.get('sql', '')
        admin_class = kwargs.get('admin_class')
        try:
            self.admin_class = import_class(admin_class)
        except ValueError:
            raise ImportError('Cannot import admin "{}"'.format(admin_class))
        model_class = kwargs.get('model_class')
        try:
            self.model_class = import_class(model_class)
        except ValueError:
            raise ImportError('Cannot import model "{}"'.format(model_class))

    def get_queryset(self):
        qs = self.model_class.objects.raw(self.sql)
        if self.using:
            qs = qs.using(self.using)
        return qs

    def get_row(self, item):
        row = {}
        for field in self.fields:
            if hasattr(item, field):
                row[field] = getattr(item, field)
            else:
                function = getattr(self.admin_class, field)
                row[field] = function(None, item)
        return row

    def generate(self, buffer, tmp_dir):
        reader = DictWriter(buffer, self.fields)
        reader.writeheader()
        for item in self.get_queryset():
            row = self.get_row(item)
            reader.writerow(row)
