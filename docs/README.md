# Integration Utils

## Назначение

`integration_utils` хранит общие интеграционные helpers и vendored-клиенты, которые используются несколькими приложениями проекта.

## OPERATING в Bitrix24

Правило разбора медленных REST-вызовов Bitrix24 и критерии оптимизации описаны в [будущей статье БЗ](../kdbdocs/operating_bitrix24_optimization.md). Сигнал `method_operating` не следует скрывать или компенсировать только увеличением таймаута: необходимо изучить вызывающий сценарий и сократить нагрузку на API.

## Telegram retry

`integration_utils/itsolution/decorators/telegram_retry_decorator.py` содержит `telegram_retry_decorator` для повторных попыток Telegram-методов.

Поведение на 2026-07-09:

- `RetryAfter` повторяется после `exc.retry_after`;
- `TimedOut` повторяется после `timeout_delay`;
- сетевой `NetworkError` повторяется после `timeout_delay`;
- логические наследники `NetworkError`, например `BadRequest`, не повторяются.

Это важно для отправки сообщений через `tgpr1.it-solution.ru`: кратковременные `Bad Gateway` и connect timeout должны получить повторную попытку, а ошибки некорректного запроса должны сразу возвращаться вызывающему коду.

## Browser-вход через Bitrix24

`integration_utils/bitrix24/views/start.py` — общий iframe-start endpoint приложения Marketplace. Он выполняет `main_auth(on_start=True, set_cookie=True)` и создаёт на `itsis.it-solution.ru` cookie, которую затем могут читать защищённые страницы.

При `main_auth(on_cookies=True)` отсутствие либо повреждение cookie на GET/HEAD автоматически открывает Marketplace-приложение из настройки проекта `BITRIX_MARKETPLACE_AUTH_APP_ID` и передаёт текущий относительный путь в `return_to`. После успешного iframe-входа endpoint возвращает пользователя на него. Внешние URL игнорируются, поэтому параметр не является открытым redirect. Если настройка отсутствует или некорректна, остаётся прежний 401. Для POST/PUT/PATCH/DELETE также остаётся 401: перенаправление не должно менять метод или терять тело операции. Каждый экран по-прежнему сам проверяет свои права; например, календарь `/hr/absense` требует существующего активного Django-superuser.

## Общий декоратор повторных попыток

`integration_utils/retry_utils/retry_decorator.py` содержит независимый от конкретной интеграции `RetryDecorator`. Он используется Bitrix24-клиентом через параметр `retry_settings` и позволяет ограничить число повторных вызовов, задержку и набор retryable-исключений.

Контракт, порядок проверок и ограничения использования описаны в [исходнике будущей статьи БЗ](../retry_utils/kdbdocs/retry_decorator.md). Применять повторные попытки следует только к подтверждённо временным сбоям и безопасным для повторного выполнения операциям.
