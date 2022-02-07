# coding: utf-8
from django.urls import path

from integration_utils.its_utils.app_gitpull.views import view_gitpull, view_make_system_checks

urlpatterns = [
    path('gitpull/', view_gitpull, name='gitpull'),
    path('gitpull/system_checks/', view_make_system_checks, name='make_system_checks'),
]
