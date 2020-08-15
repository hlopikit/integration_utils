# -*- coding: UTF-8 -*-

import django

version = django.get_version().split('.')

if int(version[0]) > 0 and not (int(version[0]) == 1 and int(version[1]) < 7):
    # from .check_on_delete_protect import check_on_delete_protect
    from .check_unapplied_migrations import check_unapplied_migrations
    from .check_pyc_files import check_pyc_files
    from .check_ilogger import check_ilogger
