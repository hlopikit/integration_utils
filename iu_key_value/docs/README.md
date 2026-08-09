# iu_key_value

## Назначение

`integration_utils.iu_key_value` хранит служебные JSON-значения по строковому ключу. Приложение предназначено для cron-сценариев и helper-кода,
которым нужен небольшой общий persistent state: курсор синхронизации, дата последней успешной обработки или технический флаг.

## Публичный API

Модель `integration_utils/iu_key_value/models/key_value.py`, класс `KeyValue`:

- `KeyValue.get_value(key, create=False, default='', comment='')` читает JSON-значение; при первом чтении может перенести старое значение из
  `integration_utils.its_utils.app_settings.models.KeyValue`;
- `KeyValue.set_value(key, value, comment='')` создает или обновляет JSON-значение.

В новом прикладном коде нужно использовать именно эти методы, а не прямые вызовы ORM к `KeyValue.objects` или `save()`. Это сохраняет единый
контракт хранения, логирование и совместимый перенос со старого хранилища.

## Изолированное хранилище приложения

`AbstractKeyValue` в `integration_utils/iu_key_value/models/abstract_key_value.py` — абстрактная база для нового приложения. Concrete-наследник
получает собственную таблицу, отдельную модель в админке и стандартные Django-права `view`, `add`, `change`, `delete` именно этой модели.

```python
from integration_utils.iu_key_value.models import AbstractKeyValue


class ExampleAppKeyValue(AbstractKeyValue):
    log_value = False  # Если JSON содержит секреты.

    class Meta:
        verbose_name = "Настройка Example App"
        verbose_name_plural = "Настройки Example App"
```

После добавления такого наследника нужна отдельная вручную подготовленная миграция приложения. В коде наследника используйте
`ExampleAppKeyValue.get_value()` и `ExampleAppKeyValue.set_value()`, а не его ORM напрямую. Старый `KeyValue` остаётся concrete-моделью общей
инфраструктурной таблицы и сохраняет ленивый перенос значений из `app_settings.KeyValue`.

Подробный пример cursor для cron: `integration_utils/iu_key_value/kdbdocs/README.md`.

## Проверки при изменениях

- применены ли миграции `iu_key_value`;
- не потеряется ли значение ключа из legacy `app_settings.KeyValue` при первом чтении;
- сохраняется ли курсор только после успешной обработки соответствующей записи.
