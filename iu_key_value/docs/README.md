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

Подробный пример cursor для cron: `integration_utils/iu_key_value/kdbdocs/README.md`.

## Проверки при изменениях

- применены ли миграции `iu_key_value`;
- не потеряется ли значение ключа из legacy `app_settings.KeyValue` при первом чтении;
- сохраняется ли курсор только после успешной обработки соответствующей записи.
