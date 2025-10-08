# -*- coding: utf-8 -*-

from django.db import models


class KeyValue(models.Model):
    key = models.SlugField(u'ключ', primary_key=True)
    value = models.TextField(u'значение')
    comment = models.TextField(u'комментарий', blank=True)

    class Meta:
        app_label = 'app_settings'

    def __unicode__(self):
        return self.key

    @staticmethod
    def set_value(key, value, comment=''):

        from settings import ilogger
        from integration_utils.its_utils.app_settings.models import KeyValue

        result = KeyValue.objects.filter(key=key).update(value=value)
        if not result:
            KeyValue.objects.create(key=key, value=value, comment=comment)
        ilogger.debug('set_value', '{}->{}'.format(key, value))
        return

    @staticmethod
    def get_value(key, create=False, default='', comment=''):
        try:
            return KeyValue.objects.get(key=key).value
        except KeyValue.DoesNotExist:
            if create:
                KeyValue.set_value(key=key, value=default, comment=comment)
                return default
            return None