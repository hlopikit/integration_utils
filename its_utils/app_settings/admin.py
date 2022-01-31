# -*- coding: UTF-8 -*-


from django.contrib import admin
from .models import KeyValue


@admin.register(KeyValue)
class KeyValueAdmin(admin.ModelAdmin):
    list_display = 'key', 'value', 'comment'
    search_fields = ('key', 'comment')
