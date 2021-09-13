from django.conf.urls import url
import django_easy_report.views as views

urlpatterns = [
    url(r'^(?P<report_name>[\w-]+)/$',
        views.GenerateReport.as_view(), name='report_generator'),
    url(r'^(?P<report_name>[\w-]+)/(?P<query_pk>[\w-]+)/$',
        views.DownloadReport.as_view(), name='report_download'),
]
