# Changelog

## 2026-09-13

- `main_auth(on_start=True)` возвращает контролируемый HTTP 401 при ответе Bitrix24 `invalid_token`, а не необработанный HTTP 500.
