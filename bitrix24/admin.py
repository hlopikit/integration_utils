# coding=utf-8

from __future__ import unicode_literals

from django.contrib import admin
from django.utils.safestring import mark_safe

import django
if django.VERSION[0] >= 4:
    from django.db.models import JSONField
else:
    from django.contrib.postgres.fields import JSONField

from prettyjson import PrettyJSONWidget

from integration_utils.bitrix24.models import BitrixUserToken, BitrixUser


class JsonInfoAdmin(admin.ModelAdmin):
    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget}
    }


class Bitrix24UserTokenAdminInline(admin.TabularInline):
    model = BitrixUserToken
    extra = 0
    fields = ['id', 'name', 'is_active', 'refresh_error']
    readonly_fields = fields

    def name(self, obj):
        return mark_safe('<a href="/admin/{}/{}/{}/change/" target="_blank">{}</a>'.format(
            obj._meta.app_label, obj._meta.model_name, obj.id, obj.application
        ))


@admin.register(BitrixUser)
class Bitrix24UserAdmin(admin.ModelAdmin):
    list_display = 'id', '__str__', 'bitrix_id', 'email', 'is_admin', 'user_is_active'
    list_display_links = list_display
    list_filter = 'user_is_active', 'is_admin'
    search_fields = 'first_name', 'last_name', 'bitrix_id'

    inlines = [Bitrix24UserTokenAdminInline]



@admin.register(BitrixUserToken)
class Bitrix24UserTokenAdmin(JsonInfoAdmin):
    readonly_fields = ['id']
    list_display = 'id', 'user', 'auth_token', 'is_active', 'refresh_error'
    list_display_links = list_display
    list_filter = 'is_active', 'refresh_error'
    search_fields = ['user__first_name', 'user__last_name']
    date_hierarchy = 'auth_token_date'
    raw_id_fields = ['user']
    actions = ['refresh']
