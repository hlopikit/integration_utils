from django.db import models


class KeyValue(models.Model):
    """Хранит служебные JSON-значения и дает единый API для cron и helper-кода."""
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
        Сохраняет значение по ключу в `json_value`, а при переданном непустом `comment` синхронно обновляет комментарий записи.

        Используется cron/helper-кодом вместо ручных `objects.get_or_create()`, `create()` и `save()`, чтобы правила хранения и логирование
        оставались в одном месте.
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
        """
        Возвращает JSON-значение по ключу и при первом чтении переносит legacy-значение из `app_settings.KeyValue`.

        Используется cron/helper-кодом для чтения настроек без прямого запроса к ORM. При `create=True` создает отсутствующий ключ через
        `set_value()` со значением `default`.
        """
        try:
            return KeyValue.objects.get(key=key).json_value
        except KeyValue.DoesNotExist:
            try:
                # Переезд выполняется лениво, чтобы первый вызов нового API не терял уже сохраненный служебный курсор.
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
