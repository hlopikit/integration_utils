def set_value(key, value, comment=''):

    from settings import ilogger
    from integration_utils.its_utils.app_settings.models import KeyValue

    result = KeyValue.objects.filter(key=key).update(value=value)
    if not result:
        KeyValue.objects.create(key=key, value=value, comment=comment)
    ilogger.debug('set_value', '{}->{}'.format(key, value))
    return

def get_value(key, create=False, default='', comment=''):
    from integration_utils.its_utils.app_settings.models import KeyValue

    try:
        return KeyValue.objects.get(key=key).value
    except KeyValue.DoesNotExist:
        if create:
            set_value(key=key, value=default, comment=comment)
            return default
        return None