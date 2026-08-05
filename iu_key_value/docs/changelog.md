# Changelog

## 2026-08-05

- Документирован публичный API `KeyValue.get_value()` и `KeyValue.set_value()` как обязательный способ работы с JSON-значениями в новом cron/helper-коде.
- Добавлен шаблон безопасного cursor для cron-сценариев с ленивым переносом значения из legacy `app_settings.KeyValue`.
