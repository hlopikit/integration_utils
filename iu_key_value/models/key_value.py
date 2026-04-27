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
        """
        1) Сохраняет значение по ключу в `json_value`, а при переданном непустом `comment` синхронно обновляет и комментарий записи.
        2) Используется cron/helper-кодом как компактный API поверх `KeyValue`, чтобы не дублировать ручной `get_or_create/update`.
        """

        from settings import ilogger
        update_fields = {"json_value": value}
        if comment:
            update_fields["comment"] = comment
        result = KeyValue.objects.filter(key=key).update(**update_fields)
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
