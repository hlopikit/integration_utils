from typing import Type, Union

from dateutil.parser import isoparse
from django.utils import timezone
from django.utils.module_loading import import_string

from ..bitrix_event import BitrixEvent
from ..models import AbstractBitrixEvent

from settings import ilogger


def cron_collect_bitrix_events(event_class: Union[Type[BitrixEvent], str]) -> str:
    """Собирает одну страницу офлайн-событий.

    event_class: наследник BitrixEvent или конкретная модель на основе AbstractBitrixEvent; можно передать класс или его модульный путь
    Обычные события обрабатываются через process(), события модели сохраняются в БД
    Успешно собранные события удаляются из очереди Bitrix24
    """
    from ...models.bitrix_user_token import BitrixUserToken

    event_cls = import_string(event_class) if isinstance(event_class, str) else event_class
    if not issubclass(event_cls, BitrixEvent):
        raise TypeError('event_class must inherit BitrixEvent')
    token = BitrixUserToken.get_admin_token()
    result = token.call_api_method('event.offline.list')
    processed_ids = []
    try:
        for data in result['result']:
            try:
                event_dt = isoparse(data['TIMESTAMP_X'])
            except (KeyError, ValueError):
                ilogger.error('event_no_or_bad_timestamp', repr(data))
                event_dt = timezone.now()
            event = event_cls(event_name=data['EVENT_NAME'], data=data, datetime=event_dt)
            if isinstance(event, AbstractBitrixEvent):
                event.save()
            else:
                event.process()
            processed_ids.append(data['ID'])
    finally:
        # При ошибке подтверждаем только уже обработанные или сохраненные события.
        if processed_ids:
            token.call_api_method('event.offline.clear', {
                'process_id': '', 'id': processed_ids,
            })
    return f'collected {len(processed_ids)}, total {result["total"]}'
