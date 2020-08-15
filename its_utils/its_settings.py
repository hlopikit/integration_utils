#coding: utf-8
import os
from django.conf import settings


# Директория в которой лежит этот файлик
ITS_UTILS_PATH = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')

# Директория проекта к которому подключены разные app из its_utils
PROJECT_PATH = getattr(settings, 'PROJECT_PATH',
                       os.path.abspath(os.path.dirname(ITS_UTILS_PATH)))


#тест
