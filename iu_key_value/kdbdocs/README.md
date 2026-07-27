Статус: готово к синхронизации

# iu_key_value

`integration_utils.iu_key_value` - маленькое Django-приложение для хранения проектных ключей и JSON-значений в базе данных.

Основная модель:

- `integration_utils/iu_key_value/models/key_value.py` - `KeyValue`;
- поле `key` - строковый первичный ключ;
- поле `json_value` - JSON-значение;
- поле `comment` - пояснение для администратора и будущего обслуживания.

## Подключение через check_settings

`iu_key_value` относится к инфраструктурным приложениям, поэтому его не нужно добавлять вручную в `INSTALLED_APPS` каждого проекта.

Правильный способ подключения - через общий `check_settings(locals())` из `its_utils/base_django_settings.py`.

В конце проектного `settings.py` должно быть:

```python
from its_utils.base_django_settings import check_settings

check_settings(locals())
```

`check_settings()` добавляет `integration_utils.iu_key_value` в общий список обязательных приложений `REQUIRED_INSTALLED_APPS`.

Такой подход важен, потому что `KeyValue` используется cron/helper-кодом как общий инфраструктурный механизм. Если добавлять приложение вручную в отдельных проектах, легко получить разные схемы подключения и забытые миграции.

## Миграции

После подключения через `check_settings()` нужно применить миграции:

```bash
python manage.py migrate iu_key_value
```

Если таблицы нет, обращения к `KeyValue.get_value()` или `KeyValue.set_value()` завершатся ошибкой уровня базы данных, например отсутствием таблицы `iu_key_value_keyvalue`.

## Использование

Для новых мест используйте методы модели:

```python
from integration_utils.iu_key_value.models import KeyValue

KeyValue.set_value(
    key="example-key",
    value={"last_success_dt": "2026-07-23T10:00:00+00:00"},
    comment="Пример хранения служебной даты.",
)

value = KeyValue.get_value("example-key")
```

Функции из `integration_utils/iu_key_value/functions.py` считаются устаревшими совместимыми обертками. В новом коде их лучше не использовать.

## Пример: watermark cron-загрузки

Для cron-задач удобно сохранять дату последнего успешного запуска или загрузки:

```python
KeyValue.set_value(
    "telethon-msg-last-dt-s1",
    {"date_to": date_to.isoformat()},
    comment="Последняя успешная загрузка сообщений telethon_connector.",
)
```

Следующий запуск может прочитать это значение и взять данные с небольшим overlap, например от `date_to - 1 час`, чтобы не потерять записи на границе запусков.
