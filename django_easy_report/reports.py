from django.forms.utils import ErrorDict

from django_easy_report.utils import import_class


class ReportBaseGenerator(object):
    XLS_MAX_ROWS = 65536
    XLS_MAX_COLUMNS = 256

    XLSX_MAX_ROWS = 1048576
    XLSX_MAX_COLUMNS = 16384

    mimetype = 'application/octet-stream'
    form_class = None
    using = None

    def __init__(self, **kwargs):
        self.setup_params = {}
        self.report_model = None
        self.form = None

    def reset(self):  # pragma: no cover
        self.setup_params = {}
        self.report_model = None
        self.form = None

    def setup(self, report_model, **kwargs):
        self.setup_params = kwargs
        self.report_model = report_model

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

    def generate(self):  # pragma: no cover
        raise NotImplementedError()


class ReportModelGenerator(ReportBaseGenerator):
    def __init__(self, model, fields,
                 form_class_name=None,
                 user_fields=None,
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
        self.user_fields = user_fields

    def validate(self, data):
        errors = super(ReportModelGenerator, self).validate(data)
        if self.form:
            if not errors:
                errors = ErrorDict()
            # TODO check form fields and user_fields
            # If there is fields not in form nor in user_fields raise validate error
            pass
        return errors

    def get_params(self, data):
        user_params, report_params = {}, {}
        for key, value in data.items():
            if key in self.user_fields:
                user_params[key] = value
            elif self.form_class:
                pass  # TODO check fields from form class
            else:
                report_params[key] = value
        return user_params, report_params

    def generate(self):
        header = self.fields
        for item in self.get_queryset():
            row = self.get_row(item)
        # TODO
        raise NotImplementedError()

    def get_queryset(self):
        items = self.model_cls.objects.all()
        if self.using:
            items = items.using(self.using)
        return items

    def get_row(self, obj, default=''):
        row = []
        for header in self.fields:
            row.append(getattr(obj, header, default))
        return row
