from .abstract_key_value import AbstractKeyValue


class KeyValue(AbstractKeyValue):
    """Совместимая общая таблица служебных JSON-значений.

    Используется существующим кодом. Новые приложения могут наследоваться от
    ``AbstractKeyValue`` и получать отдельную таблицу и права доступа.
    """

    migrate_legacy_values = True

    class Meta:
        app_label = 'iu_key_value'

    def __unicode__(self):
        return self.key
