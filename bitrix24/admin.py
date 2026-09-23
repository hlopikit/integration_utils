# coding=utf-8

from __future__ import unicode_literals

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import path, reverse
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

    # noinspection PyMethodMayBeStatic
    def name(self, obj):
        return mark_safe(
            f'<a href="/admin/bitrix24/bitrixusertoken/{obj.id}/change/" target="_blank">{obj.application}</a>'
        )


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
    change_form_template = 'bitrix24/admin/bitrix_user_token_change_form.html'

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/refresh/',
                self.admin_site.admin_view(self.refresh_view),
                name='bitrix24_bitrixusertoken_refresh',
            ),
        ]
        return custom_urls + super().get_urls()

    def refresh(self, request, queryset):
        for instance in queryset:
            if instance.refresh():
                self.message_user(request, '#%s refreshed.' % instance.pk)
            else:
                self.message_user(
                    request,
                    '#%s not refreshed.' % instance.pk,
                    level=messages.WARNING,
                )
    refresh.short_description = 'Refresh tokens'

    def refresh_view(self, request, object_id):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])

        instance = self.get_object(request, object_id)
        if instance is None:
            raise Http404
        if not self.has_change_permission(request, instance):
            raise PermissionDenied

        self.refresh(request, [instance])

        change_url = reverse(
            'admin:bitrix24_bitrixusertoken_change',
            args=[object_id],
            current_app=self.admin_site.name,
        )
        return HttpResponseRedirect(change_url)
