# 2026-07-07

- `NetworkError` из `integration_utils.vendors.telegram.utils.request` теперь маскирует Telegram bot token в URL transport-ошибок urllib3 перед попаданием в app_logger и другие логи.
- Маскировка применяется для стандартного Telegram Bot API `/bot<TOKEN>/...`, file API `/file/bot<TOKEN>/...` и локального proxy `/tapi/bot<TOKEN>/...`.
- `ConnectTimeoutError`, завернутый в `MaxRetryError`, теперь классифицируется как Telegram `TimedOut`, а не как общий `NetworkError`.

# 2026-05-12

- Невалидный JSON-ответ от Telegram proxy/upstream в `integration_utils.vendors.telegram.utils.request` теперь классифицируется как `NetworkError`, а не как общий `TelegramError`.
- HTTP-ошибки с пустым или HTML body больше не приводят к ложному падению polling-кронов Telegram-ботов.
