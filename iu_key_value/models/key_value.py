from django.db import models


class KeyValue(models.Model):
    key = models.SlugField(u'ключ', primary_key=True)

    json_value = models.JSONField(u'json значение', null=True, blank=True)
    comment = models.TextField(u'комментарий', blank=True)

    class Meta:
        app_label = 'iu_key_value'

    def __unicode__(self):
        return self.key

    @staticmethod
    def set_value(key, value, comment=''):

        from settings import ilogger
        result = KeyValue.objects.filter(key=key).update(json_value=value)
        if not result:
            KeyValue.objects.create(key=key, json_value=value, comment=comment)
        ilogger.debug('set_value', '{}->{}'.format(key, value))
        return

    @staticmethod
    def get_value(key, create=False, default='', comment=''):
        try:
            return KeyValue.objects.get(key=key).json_value
        except KeyValue.DoesNotExist:
            try:
                # Кусок для переезда со старой функции
                from integration_utils.its_utils.app_settings.models import KeyValue as KeyValueOld
                kv = KeyValueOld.objects.get(key=key)
                KeyValue.objects.create(key=key, json_value=kv.value, comment=kv.comment)
                # Вызовем рекурсивно еще раз
                return KeyValue.get_value(key, create=create, default=default, comment=comment)
            except Exception:
                # На любую ошибку забиваем, т.к это только попытка взять из старого для переезда
                pass

            if create:
                KeyValue.set_value(key=key, value=default, comment=comment)
                return default
            return None