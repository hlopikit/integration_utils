# Авторизация Bitrix24

Приложение `integration_utils.bitrix24` содержит общий OAuth-транспорт и декораторы авторизации iframe-приложений Bitrix24.

`main_auth(on_start=True)` вызывает `authenticate_on_start_application()`. Если Bitrix24 передал `invalid_token`, декоратор возвращает контролируемую страницу с HTTP 401 вместо необработанного HTTP 500. Пользователю нужно повторно открыть приложение; это не меняет сохраненные токены и данные портала.

## Возврат после авторизации по cookie

Статус исправления: локальные изменения по задаче #328153, 2026-10-28; запуск в живом портале не проверен.

- `bitrix_user_auth/main_auth.py`: при отсутствии или повреждении cookie на GET/HEAD декоратор `main_auth(on_cookies=True)` открывает `https://<portal_domain>/marketplace/app/<BITRIX_MARKETPLACE_AUTH_APP_ID>/?return_to=...`. В `return_to` передаётся исходный относительный путь вместе с query-строкой. Без корректного ID приложения и для небезопасных методов сохраняется HTTP 401.
- `views/start.py`: iframe-view `start` авторизует OAuth через `main_auth(on_start=True, set_cookie=True)`. Битрикс24 передаёт параметры Marketplace-ссылки в POST-поле `PLACEMENT_OPTIONS` как JSON-объект; наличие GET-параметра `return_to` у iframe не требуется.
- `_get_index_path` сначала проверяет непустой GET `return_to`, затем значение из разобранного `PLACEMENT_OPTIONS`. Если поле отсутствует, JSON повреждён или содержит не объект, сохраняется резервное чтение параметров из query-строки `HTTP_REFERER`. Корректный пустой объект не заменяется Referer-параметрами.
- Адрес возврата должен быть строкой с начальным `/` и пройти `url_has_allowed_host_and_scheme`. Внешние URL, адреса вида `//example.com/` и нестроковые значения заменяются `APP_SETTINGS.application_index_path`.
- Управляющий `return_to` удаляется из пересылаемых GET- и `bx_referer_params`. Остальные placement-параметры передаются в JSON-параметре `bx_referer_params`, остальные GET-параметры — напрямую. Существующие query-параметры, повторяющиеся значения и fragment адреса сохраняются.
- Шаблон `templates/start.html` экранирует адрес через `escapejs` и выполняет `location.href`: переход происходит внутри iframe. Установка и отправка cookie зависят от настроек браузера; тесты подтверждают заголовок cookie, но не поведение браузера на живом портале.

В проекте `integration_server` GET-запуск без OAuth обрабатывает `start/templates/start/marketplace_bootstrap.html`: после `BX24.init()` форма передаёт OAuth и `BX24.placement.info()` в тот же POST-контракт. Это проектная обёртка, а не часть общего приложения.

Проверки находятся в `integration_utils/bitrix24/tests.py`: полный путь без cookie, GET-приоритет, placement/Referer, небезопасные адреса, query и fragment, установка cookie и JavaScript-экранирование. При изменении авторизации нужно также проверять фактический запуск Marketplace и ограничения iframe-cookie в целевом браузере.
