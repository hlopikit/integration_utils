# -*- coding: UTF-8 -*-
from django.core.checks import register, Critical
import settings


@register()
def check_ilogger(app_configs, **kwargs):
    """
    Проверка наличия ilogger в settings
    """

    errors = []

    ilogger = getattr(settings, 'ilogger', None)

    if ilogger is None:
        errors.append(
            Critical(
                'ilogger not found in settings',
                hint=None,
                obj='Critical',
                id='%s.W001' % 'check_ilogger',
            )
        )

    return errors
