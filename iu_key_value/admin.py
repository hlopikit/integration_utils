from django.contrib import admin
from .models import KeyValue


@admin.register(KeyValue)
class KeyValueAdmin(admin.ModelAdmin):
    list_display = ['key', 'json_value', 'comment']
    search_fields = ['key', 'comment']
