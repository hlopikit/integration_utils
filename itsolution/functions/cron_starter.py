import os, sys

from django.utils.module_loading import import_string

FILE_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(FILE_PATH, '../../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# редактируем cron
# sh crontab -e
# Раз в минуту будет запускать функцияю test_print
# * * * * *       /home/app/env_app/bin/python /home/app/app/its_utils/app_cron/cron.py integration_utils.itsolution.functions.cron_starter.test_print

import django
django.setup()

def test_print():
    print('Запущено выполнение')

def main():
    
    path = sys.argv[1]

    fun = import_string(path)

    return fun()


if __name__ == '__main__':
    main()
