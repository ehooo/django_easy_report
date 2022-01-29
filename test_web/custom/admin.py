from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from django_easy_report.actions import generate_report


class UserAdmin(DjangoUserAdmin):
    actions = [generate_report]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
