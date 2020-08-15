# -*- coding: UTF-8 -*-

import os
import re

from django.conf import settings
from django.core.checks import Critical, register

pychache_dir = '__pycache__'
pyc_extension = '.pyc'
cpython_36_infix_re = '\.cpython-\d+'

exclude_dirs = list()
exclude_dirs.extend(settings.STATICFILES_DIRS)
exclude_dirs.append(settings.MEDIA_ROOT)
exclude_dirs.append(os.path.join(settings.BASE_DIR, '.git'))


@register()
def check_pyc_files(app_configs, **kwargs):
    errors = []

    in_root_dirs = []
    in_root_files = []

    for dir_ in os.listdir(settings.BASE_DIR):
        path = os.path.join(settings.BASE_DIR, dir_)
        if os.path.isdir(path):
            in_root_dirs.append(path)
        else:
            in_root_files.append(os.path.split(path)[1])

    dirs_files = {settings.BASE_DIR: in_root_files}
    for dir_in_root in in_root_dirs:
        # обходим директории, пропуская static и media, чтобы не закопаться там надолго
        if dir_in_root not in exclude_dirs:
            for path, dirs, files in os.walk(dir_in_root, topdown=True):
                # собираем в словарь файлы текущей директории
                dirs_files[path] = files

                for file_ in files:
                    if file_.endswith(pyc_extension):
                        if path.endswith(pychache_dir):
                            py_dir, _ = os.path.split(path)  # убираем /__pycache__

                        else:
                            py_dir = path

                        # убираем последний символ 'c' и .cpython-36 из имени .pyc
                        py_file = re.sub(cpython_36_infix_re, u'', file_[:-1])

                        # проверяем наличие файла в директории
                        # т.к. обходим сверху вниз, файлы верхней директории уже добавлены в словарь dirs_files
                        if py_file not in dirs_files[py_dir]:
                            # Если .py файл не найден, удаляем .pyc
                            pyc_path = os.path.join(path, file_)
                            os.remove(pyc_path)
                            errors.append(Critical(
                                u'.pyc file has no matching .py file DELETED: {}'.format(pyc_path),
                                hint=None,
                                obj='Critical',
                                id='%s.W001' % 'check_pyc_files'
                            ))

    return errors
