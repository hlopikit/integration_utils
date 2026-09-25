# RetryDecorator: управляемые повторные попытки вызова

Статья в БЗ: https://it-solution.kdb24.ru/new/article/534717/

Статус: готово к синхронизации

## Назначение

`RetryDecorator` — общий декоратор для ограниченного повторного запуска синхронной функции после ожидаемых исключений. Он расположен в `integration_utils/retry_utils/retry_decorator.py` и экспортируется из `integration_utils/retry_utils/__init__.py`.

Декоратор не привязан к HTTP, Bitrix24 или Django: вызывающий код сам определяет допустимое число попыток, типы исключений и дополнительное условие повтора. В проекте он используется как настройка `retry_settings` для REST-вызовов Bitrix24.

## Публичный API

```python
from integration_utils.retry_utils import RetryDecorator

retry = RetryDecorator(
    attempts=3,
    delay=1.0,
    exceptions=(ConnectionError, TimeoutError),
    exclude_exceptions=(),
    should_retry=None,
)

@retry
def load_data():
    ...
```

Параметры `RetryDecorator.__init__()`:

| Параметр | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `attempts` | `1` | Общее число вызовов функции, включая первый. Значение меньше `1` вызывает `ValueError`. |
| `delay` | `0` | Пауза в секундах перед следующей попыткой. Отрицательное значение вызывает `ValueError`. |
| `exceptions` | `(Exception,)` | Исключение или итерируемый набор исключений, при которых возможна повторная попытка. |
| `exclude_exceptions` | `()` | Исключение или набор исключений, которые не следует повторять даже при совпадении с `exceptions`. |
| `should_retry` | `None` | Необязательная функция `Callable[[Exception], bool]`. При результате `False` исходное исключение сразу передаётся вызывающему коду. |

`exceptions` и `exclude_exceptions` могут передаваться как один класс исключения или как итерируемая последовательность классов. Исключения, не соответствующие `exceptions`, декоратор не перехватывает.

## Порядок работы

1. Декоратор запускает исходную функцию.
2. При исключении из `exceptions` сначала проверяет `exclude_exceptions`, затем `should_retry`.
3. Если исключение исключено или predicate вернул `False`, исходное исключение немедленно пробрасывается.
4. Перед следующей попыткой выполняется `time.sleep(delay)`, только если `delay` не равен нулю.
5. Последняя из `attempts` попыток выполняется без перехвата этим декоратором: её результат возвращается либо её исключение передаётся вызывающему коду.

Следовательно, при `attempts=3` максимум два неуспешных вызова могут быть обработаны как повторяемые, а третий вызов является финальным. При `attempts=1` функция вызывается один раз без внутреннего `try/except`.

Декоратор использует `functools.wraps`, поэтому сохраняет имя, docstring и другие метаданные декорируемой функции.

## Применение в Bitrix24-клиенте

`integration_utils/bitrix24/bitrix_token.py` импортирует класс и публикует его также как `BaseBitrixToken.RetrySettings`. Экземпляр передаётся аргументом `retry_settings` в методы:

- `BaseBitrixToken.call_api_method()` и `call_api_method_v3()`;
- `BaseBitrixToken.batch_api_call()`;
- `BaseBitrixToken.call_list_method()` и `call_list_fast()`;
- соответствующие методы `BitrixUserToken` в `integration_utils/bitrix24/models/bitrix_user_token.py`.

Если `retry_settings` задан, Bitrix24-клиент оборачивает им внутренний REST-вызов. Повторяется весь вызов API или пакетный вызов, а не отдельный элемент уже сформированного результата. Для списочных методов настройка передаётся далее в вызовы `call_api_method`, `batch_api_call` или `batch_api_call_v3`.

Пример для Bitrix24-клиента:

```python
from integration_utils.bitrix24.exceptions import BitrixApiServerError

retry_settings = RetryDecorator(
    attempts=3,
    delay=1,
    exceptions=BitrixApiServerError,
)
response = token.call_api_method(
    api_method="user.get",
    retry_settings=retry_settings,
)
```

Набор `exceptions` следует выбирать по подтверждённому transient-сценарию. Не стоит повторять вызов с ошибкой в параметрах, правах, бизнес-правиле или неидемпотентным побочным действием, если повтор может создать дубли.

## Ограничения и проверка при изменениях

- Декоратор синхронный и блокирует текущий поток на время `delay`.
- Он не ведёт лог повторов и не реализует экспоненциальную задержку, jitter, лимит общего времени или отмену.
- Код не проверяет, что элементы `exceptions` и `exclude_exceptions` являются классами исключений; передавать следует корректные типы для `except` и `isinstance`.
- Повтор допустим только для операции, которая идемпотентна либо имеет предусмотренную защиту от повторного выполнения.

При изменении декоратора нужно отдельно проверить: число фактических вызовов, отсутствие повтора для `exclude_exceptions`, остановку по `should_retry=False`, паузу между промежуточными попытками и сохранение исходного исключения на последней попытке.

## Источники

- `integration_utils/retry_utils/retry_decorator.py`, класс `RetryDecorator`.
- `integration_utils/retry_utils/__init__.py`, экспорт `RetryDecorator`.
- `integration_utils/bitrix24/bitrix_token.py`, класс `BaseBitrixToken`.
- `integration_utils/bitrix24/models/bitrix_user_token.py`, класс `BitrixUserToken`.
- `integration_utils/bitrix24/functions/call_list_method.py`, функция `call_list_method()`.
- `integration_utils/bitrix24/functions/call_list_fast.py`, функция `call_list_fast()`.
