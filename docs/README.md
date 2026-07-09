# Integration Utils

## Назначение

`integration_utils` хранит общие интеграционные helpers и vendored-клиенты, которые используются несколькими приложениями проекта.

## Telegram retry

`integration_utils/itsolution/decorators/telegram_retry_decorator.py` содержит `telegram_retry_decorator` для повторных попыток Telegram-методов.

Поведение на 2026-07-09:

- `RetryAfter` повторяется после `exc.retry_after`;
- `TimedOut` повторяется после `timeout_delay`;
- сетевой `NetworkError` повторяется после `timeout_delay`;
- логические наследники `NetworkError`, например `BadRequest`, не повторяются.

Это важно для отправки сообщений через `tgpr1.it-solution.ru`: кратковременные `Bad Gateway` и connect timeout должны получить повторную попытку, а ошибки некорректного запроса должны сразу возвращаться вызывающему коду.
