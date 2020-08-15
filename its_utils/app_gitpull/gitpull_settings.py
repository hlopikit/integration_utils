# coding: utf-8
import re

from django.conf import settings
from integration_utils.its_utils import its_settings

ITS_UTILS_GITPULL = getattr(settings, 'ITS_UTILS_GITPULL', {
    'GIT_DIR': settings.BASE_DIR,
    'ONLY_SUPER': True,
    'UPDATE_SUBMODULES': True,
    'TEST_BEFORE_TOUCH_RESTART': True,
})

try:
    PATH_TO_PYTHON = settings.PATH_TO_PYTHON
    PATH_TO_ENV = settings.PATH_TO_PYTHON[:-6]
except AttributeError:
    PATH_TO_PYTHON = 'python'
    PATH_TO_ENV = '/'

    # https://ts.it-solution.ru/#/ticket/53448/
    # если путь "/home/attendance/attendance/", то PATH_TO_PYTHON = "/home/attendance/env_attendance/bin/python"
    match = re.match('/home/(.+)/(.+)/?', settings.BASE_DIR)
    if match:
        project, project_ = match.groups()
        if project == project_:
            PATH_TO_ENV = '/home/{0}/env_{0}/bin/'.format(project)
            PATH_TO_PYTHON = '{}python'.format(PATH_TO_ENV)

ITS_UTILS_PATH = its_settings.ITS_UTILS_PATH

# Настройки для django launch checks

APPS_TO_EXCLUDE = {
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'mptt',
}.union(getattr(settings, 'APPS_TO_EXCLUDE', set()))

# We do not hurry, right?
APPS_TO_CHECK = tuple(set(settings.INSTALLED_APPS) - APPS_TO_EXCLUDE)
