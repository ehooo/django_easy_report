import json
import os

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse, HttpResponse, Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_easy_report.models import ReportGenerator, ReportQuery, ReportRequester
from django_easy_report.serializers import DjangoEasyReportJSONEncoder
from django_easy_report.tasks import generate_report, notify_report_done


class BaseReportingView(View):
    def __init__(self, **kwargs):
        super(BaseReportingView, self).__init__(**kwargs)
        self.report = None

    def check_permissions(self):
        permissions = []
        if self.report and self.report.permissions:
            permissions = self.report.get_permissions()
        if not self.request.user.has_perms(permissions):
            raise PermissionDenied()


@method_decorator(csrf_exempt, name='dispatch')
class GenerateReport(BaseReportingView):

    def validate(self):
        if not self.report:
            raise ValidationError('Invalid report')

        report_generator = self.report.get_report()
        errors = report_generator.validate(self.request.POST)
        if errors:
            raise ValidationError(errors)

        data = self.request.POST
        if report_generator.form:
            data = report_generator.form.cleaned_data

        return report_generator.get_params(data)

    def is_force_generate(self):
        if self.report and self.report.always_generate:
            return True

        force_generate = self.request.GET.get('generate')
        if isinstance(force_generate, str):
            force_generate = force_generate.lower() in ['on', 'true', '1']
        else:
            force_generate = bool(force_generate)
        return force_generate

    def post(self, request, report_name):
        try:
            self.report = ReportGenerator.objects.get(name=report_name)
        except ReportGenerator.DoesNotExist:
            return JsonResponse({'error': 'report not found'}, status=404)

        try:
            self.check_permissions()
        except PermissionDenied:
            return JsonResponse({'error': 'forbidden'}, status=403)

        try:
            user_params, report_params = self.validate()
        except ValidationError as ex:
            if ex.error_dict:
                return JsonResponse({'error': ex.error_dict}, encoder=DjangoEasyReportJSONEncoder, status=400)
            if ex.error_list:
                return JsonResponse({'error': {'__all__': ex.error_list}},
                                    encoder=DjangoEasyReportJSONEncoder, status=400)
            return JsonResponse({'error': {'__all__': ex.message}}, status=400)
        user_params.update({
            'domain': request.get_host(),
            'port': request.get_port(),
            'protocol': 'https' if request.is_secure() else 'http',
        })

        params_hash = ReportQuery.gen_hash(report_params)
        if not self.is_force_generate():
            previous = ReportQuery.objects.filter(params_hash=params_hash).last()
            if previous:
                return JsonResponse({
                    'find': previous.pk,
                    'created_at': previous.created_at,
                    'updated_at': previous.updated_at,
                    'status ': {
                        'code': previous.status,
                        'name': previous.get_status_display()
                    },
                }, status=200)

        query_pk = request.GET.get('notify')
        if query_pk:
            if ReportQuery.objects.filter(params_hash=params_hash, pk=query_pk).exists():
                requester = ReportRequester.objects.create(
                    query_id=query_pk,
                    user=request.user,
                    user_params=json.dumps(user_params)
                )
                notify_report_done.delay([requester.pk])
                return JsonResponse({
                    'accepted': query_pk,
                }, status=202)
            else:
                return JsonResponse({'error': 'query not found'}, status=404)

        query = ReportQuery.objects.create(
            params_hash=params_hash,
            report=self.report,
            params=json.dumps(report_params)
        )
        ReportRequester.objects.create(
            query=query,
            user=request.user,
            user_params=json.dumps(user_params)
        )
        generate_report.delay(query.pk)

        return JsonResponse({
            'created': query.pk,
        }, status=201)


class DownloadReport(BaseReportingView):
    def get(self, request, report_name, query_pk):
        try:
            self.report = ReportGenerator.objects.get(name=report_name)
            query = ReportQuery.objects.get(report=self.report, pk=query_pk)
        except (ReportGenerator.DoesNotExist, ReportQuery.DoesNotExist):
            raise Http404()
        self.check_permissions()

        try:
            f = query.get_file()
        except FileNotFoundError:
            raise Http404()
        if isinstance(f, HttpResponse):
            return f
        response = HttpResponse(f, mimetype=query.mimetype)
        filename = os.path.basename(query.filename)
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        return response
