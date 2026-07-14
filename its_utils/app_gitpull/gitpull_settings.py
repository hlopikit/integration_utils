# coding: utf-8
import os
import re

from django.conf import settings
from integration_utils.its_utils import its_settings

ITS_UTILS_GITPULL = getattr(settings, 'ITS_UTILS_GITPULL', {
    'GIT_DIR': settings.BASE_DIR,
    'GIT_HTTP_PROXY': '',
    'GIT_SSH_COMMAND': '',
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


def get_git_env():
    git_http_proxy = str(ITS_UTILS_GITPULL.get('GIT_HTTP_PROXY', '')).strip()
    git_ssh_command = str(ITS_UTILS_GITPULL.get('GIT_SSH_COMMAND', '')).strip()

    if not git_http_proxy and not git_ssh_command:
        return None

    env = os.environ.copy()

    if git_http_proxy:
        http_proxy_url = git_http_proxy if '://' in git_http_proxy else f'http://{git_http_proxy}'
        env.update({
            'http_proxy': http_proxy_url,
            'https_proxy': http_proxy_url,
            'HTTP_PROXY': http_proxy_url,
            'HTTPS_PROXY': http_proxy_url,
        })

    if git_ssh_command:
        env['GIT_SSH_COMMAND'] = git_ssh_command

    return env
