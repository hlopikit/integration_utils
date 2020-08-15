# coding: utf-8

import os
import re
import six

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from integration_utils.its_utils.app_gitpull import gitpull_settings, make_system_checks
from integration_utils.its_utils.functions.sys_call import sys_call


# лучше показать реплейсы, чем просто отбрасывать непонятные символы
DECODE_ERRORS = 'replace' if six.PY2 else 'backslashreplace'


def to_string(s, encodings=('utf8',), fallback_encoding='utf8'):
    # ранее пытались декодировать из ASCII, игнорируя ошибки, зачем??
    if isinstance(s, six.text_type):
        return s
    for encoding in encodings:
        try:
            return s.decode(encoding)
        except UnicodeError:
            continue
    return s.decode(fallback_encoding, errors=DECODE_ERRORS)


_auth_decorator = user_passes_test(lambda u: u.is_superuser) \
    if gitpull_settings.ITS_UTILS_GITPULL['ONLY_SUPER'] \
    else staff_member_required


@_auth_decorator
def do_gitpull(request):
    env = str(os.environ)
    _, sys_call_id = sys_call('id')
    sys_call_id = to_string(sys_call_id)
    warnings = []
    errors = []
    pull_code = pull_output = None
    update_submodules_code = update_submodules_output = None
    touch_code = touch_output = None
    conf = gitpull_settings.ITS_UTILS_GITPULL
    git_dir = conf['GIT_DIR']

    pull_command = 'cd %s && git pull --stat --verbose' % git_dir
    update_submodules_command = 'cd %s && git submodule update' % git_dir
    touch_command = 'touch %s/touch_restart' % git_dir

    pull_code, pull_output = sys_call(pull_command, shell=True)
    pull_output = to_string(pull_output)

    if conf.get('UPDATE_SUBMODULES', True):
        update_submodules_code, update_submodules_output = sys_call(update_submodules_command, shell=True)
        update_submodules_output = to_string(update_submodules_output)

    # После обновления файлов запускаем тестирование
    test_ok = False
    if conf['TEST_BEFORE_TOUCH_RESTART']:
        cmd = u'%s %s' % (
            gitpull_settings.PATH_TO_PYTHON,
            os.path.join(gitpull_settings.ITS_UTILS_PATH, 'app_gitpull/testfile.py'))
        test_code, test_output = sys_call(cmd.encode('utf-8'))
        test_output = u'{}\n\nPATH_TO_PTYHON = {}'.format(
            to_string(test_output), gitpull_settings.PATH_TO_PYTHON
        )

        if int(test_code) == 0:
            test_ok = True
    else:
        test_ok = True

    if test_ok:
        touch_code, touch_output = sys_call(touch_command, shell=True)
        touch_output = to_string(touch_output)

        its_collect_static = getattr(settings, 'ITS_COLLECT_STATIC', False)
        if its_collect_static:
            collect_static_success, collect_static_output = collect_static()

        # messages, test_ok = make_system_checks.make_system_checks()

    return render(request, 'app_gitpull/result.html', locals())


def collect_static():
    try:
        return True, call_command('collectstatic', verbosity=0, interactive=False)

    except Exception as exc:
        return False, u'{}'.format(exc)


def get_repository_info(git_dir):
    _, commit = sys_call('cd %s; git rev-parse HEAD' % git_dir)
    _, origin = sys_call('cd %s; git config --get remote.origin.url' % git_dir)
    _, commit_comment = sys_call('cd %s; git log -1 --pretty=%%B' % git_dir)

    commit = to_string(commit)
    origin = to_string(origin)
    commit_comment = to_string(commit_comment)

    origin = str(origin)
    origin = 'https://%s' % (origin[origin.find('github.com'):-5].replace(':', '/'))
    url = '%s/commit/%s' % (origin, commit)

    return {'origin': origin, 'url': url, 'commit': commit, 'commit_comment': commit_comment}


@_auth_decorator
@csrf_exempt
def view_gitpull(request):
    if request.method == 'GET':

        git_dir = gitpull_settings.ITS_UTILS_GITPULL['GIT_DIR']
        env = gitpull_settings.PATH_TO_ENV

        code, pip_freeze = sys_call('%spip freeze -l' % env)
        pip_freeze = to_string(pip_freeze)
        # debug_info = [pip_freeze,
        #                 env,
        #                 sys_call('%spip freeze -l' % env)[1]]

        if code != 0:
            pip_freeze = to_string(sys_call('pip freeze')[1])

        pip_freeze = [
            str(module).split('==')
            for module in pip_freeze.splitlines()
        ]

        repositories = [git_dir]

        try:
            submodule_file = open(os.path.join(git_dir, '.gitmodules')).read()
        except IOError:
            pass
        else:
            repositories.extend(re.findall(r'path.?=.?(.*)\n?', submodule_file))

        git_info = [get_repository_info(repo) for repo in repositories]

        # debug_info.append(repositories)
        return render(request, 'app_gitpull/gitpull.html', {
            'pip_freeze': pip_freeze,
            'git_info': git_info,
            # 'debug_info': debug_info
        })

    if request.method == 'POST':
        return do_gitpull(request)


@_auth_decorator
def view_make_system_checks(request):
    messages, critical = make_system_checks.make_system_checks()
    return render(request, 'app_gitpull/check_view.html', {'messages': messages, 'critical': critical})
