# 2026-05-12

- Невалидный JSON-ответ от Telegram proxy/upstream в `integration_utils.vendors.telegram.utils.request` теперь классифицируется как `NetworkError`, а не как общий `TelegramError`.
- HTTP-ошибки с пустым или HTML body больше не приводят к ложному падению polling-кронов Telegram-ботов.
