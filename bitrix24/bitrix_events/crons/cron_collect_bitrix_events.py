from typing import Callable, Type

from ..bitrix_event import BitrixEvent
from ..models import AbstractBitrixEvent


def get_cron_collect_bitrix_events(event_class: Type[BitrixEvent]) -> Callable[[], str]:
    """Возвращает крон сбора офлайн-событий для переданного класса события."""
    if not issubclass(event_class, BitrixEvent):
        raise TypeError('event_class must inherit BitrixEvent')

    def cron_collect_bitrix_events() -> str:
        from ...models.bitrix_user_token import BitrixUserToken

        token = BitrixUserToken.get_admin_token()
        result = token.call_api_method('event.offline.list')
        processed_ids = []
        try:
            for data in result['result']:
                event = event_class.from_bitrix_data(data)
                if not isinstance(event, AbstractBitrixEvent):
                    event.process()
                processed_ids.append(data['ID'])
        finally:
            if processed_ids:
                token.call_api_method('event.offline.clear', {
                    'process_id': '', 'id': processed_ids,
                })
        return f'collected {len(processed_ids)}, total {result["total"]}'

    return cron_collect_bitrix_events
