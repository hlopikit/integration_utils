#!/usr/bin/env python
# coding=utf-8
"""Пример того как должен выглядеть кронфайл"""
import sys
import os
import django
import importlib

FILE_PATH = os.path.abspath(os.path.dirname(__file__))
# sys.path.append(os.path.join(FILE_PATH, '../../'))
sys.path.insert(0, os.path.join(FILE_PATH, '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# django.setup() требуется только для версий django >=1.7
try:
    django.setup()
except AttributeError:
    pass

if __name__ == '__main__':
    # Пробуем импортировать settings
    from django.conf import settings

    print('settings imported successful')
    # Пробуем импортировать urls
    import urls

    print('urls imported successful')

    # Пробуем импортировать все модели
    for app in settings.INSTALLED_APPS:
        print(app)
        models_path = "{}.models".format(app)
        try:
            importlib.import_module(models_path)
        except ImportError as e:
            if e.args[0] == 'No module named models':
                # python 2
                continue
            elif e.args[0] == "No module named '{}'".format(models_path):
                # python 3
                continue
            else:
                raise

    print('Test successful')
