# coding: utf-8

from django.conf.urls import url
from integration_utils.its_utils.app_gitpull.views import view_gitpull, view_make_system_checks

urlpatterns = [
    url('^gitpull/$', view_gitpull, name='gitpull'),
    url('^gitpull/system_checks/$', view_make_system_checks, name='make_system_checks'),
]
