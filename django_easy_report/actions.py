import json

from django.contrib import messages
from django.utils.translation import gettext

from django_easy_report.models import ReportQuery, ReportRequester, ReportGenerator
from django_easy_report.tasks import generate_report as generate_report_task


REPORT_CLASS_NAME = 'django_easy_report.reports.AdminReportGenerator'


def generate_report(modeladmin, request, queryset):
    reports = ReportGenerator.objects.filter(class_name=REPORT_CLASS_NAME)
    report_count = reports.count()
    if report_count == 0:
        modeladmin.message_user(
            request, gettext('Admin report ({}) not found.'.format(REPORT_CLASS_NAME)), messages.ERROR
        )
    elif report_count > 1:
        modeladmin.message_user(request, gettext('Detected more than one admin report.'), messages.ERROR)
    else:
        report_params = {
            'sql': str(queryset.query),
            'fields': modeladmin.list_display,
            'admin_class': "{}.{}".format(modeladmin.__class__.__module__, modeladmin.__class__.__name__),
            'model_class': "{}.{}".format(modeladmin.model.__module__, modeladmin.model.__name__),
        }
        params_hash = ReportQuery.gen_hash(report_params)

        query = ReportQuery.objects.create(
            params_hash=params_hash,
            report=reports.get(),
            params=json.dumps(report_params)
        )
        ReportRequester.objects.create(
            query=query,
            user=request.user,
            user_params=json.dumps({})
        )
        generate_report_task.delay(query.pk)

        modeladmin.message_user(request, gettext('Report queued ({}).').format(query.pk), messages.SUCCESS)
