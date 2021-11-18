from django.contrib import admin

from django_easy_report.models import (
    ReportSender,
    ReportGenerator,
    ReportQuery,
    ReportRequester, SecretKey, SecretReplace
)
from forms import ReportSenderForm


@admin.register(SecretKey)
class SecretKeyAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_filter = ('mode', )
    list_display = ('name', 'mode')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super(SecretKeyAdmin, self).get_readonly_fields(request, obj=obj)
        if obj:
            readonly_fields += ('mode', 'value', 'key', )
        return readonly_fields


class SecretReplaceInline(admin.TabularInline):
    model = SecretReplace
    extra = 1


@admin.register(ReportSender)
class ReportSenderAdmin(admin.ModelAdmin):
    readonly_fields = ('updated_at',)
    search_fields = ('name', )
    list_display = ('name', 'email_from', 'storage_class_name')
    fieldsets = (
        (None, {
            'fields': ('name', ),
        }),
        ('Email', {
            'classes': ('collapse',),
            'fields': ('email_from', 'size_to_attach'),
        }),
        ('Storage', {
            'classes': ('collapse',),
            'fields': ('storage_class_name', 'storage_init_params'),
        }),
    )
    inlines = [
        SecretReplaceInline,
    ]
    form = ReportSenderForm


@admin.register(ReportGenerator)
class ReportGeneratorAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_filter = (
        'always_generate',
        'always_download',
        'preserve_report',
    )
    list_display = ('name', 'class_name', 'sender')


@admin.register(ReportQuery)
class ReportQueryAdmin(admin.ModelAdmin):
    list_display = ('status', 'report')

    def has_add_permission(self, request):  # pragma: no cover
        return False

    def has_change_permission(self, request, obj=None):  # pragma: no cover
        return False


@admin.register(ReportRequester)
class ReportRequesterAdmin(admin.ModelAdmin):
    list_display = ('user', 'query')

    def has_add_permission(self, request):  # pragma: no cover
        return False

    def has_change_permission(self, request, obj=None):  # pragma: no cover
        return False
