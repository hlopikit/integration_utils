import logging
from typing import Callable, Type

from ..classes import BitrixEvent
from ..models import AbstractBitrixEvent


logger = logging.getLogger(__name__)


def get_cron_collect_bitrix_events(event_class: Type[BitrixEvent]) -> Callable[[], str]:
    """Возвращает крон сбора офлайн-событий для переданного класса события."""
    if not issubclass(event_class, BitrixEvent):
        raise TypeError('event_class must inherit BitrixEvent')

    def cron_collect_bitrix_events() -> str:
        from ...models.bitrix_user_token import BitrixUserToken

        token = BitrixUserToken.get_admin_token()
        result = token.call_api_method('event.offline.get', {'clear': 0})['result']
        process_id = result['process_id']
        processed_message_ids = []
        failed_message_ids = []

        for data in result['events']:
            try:
                event = event_class.from_bitrix_data(data)
                if not isinstance(event, AbstractBitrixEvent):
                    event.process()
            except Exception:
                failed_message_ids.append(data['MESSAGE_ID'])
                logger.exception('Offline event processing failed: event_id=%s', data['ID'])
            else:
                processed_message_ids.append(data['MESSAGE_ID'])

        if processed_message_ids:
            token.call_api_method('event.offline.clear', {
                'process_id': process_id,
                'message_id': processed_message_ids,
            })
        if failed_message_ids:
            token.call_api_method('event.offline.error', {
                'process_id': process_id,
                'message_id': failed_message_ids,
            })

        return 'collected {}, errors {}'.format(len(processed_message_ids), len(failed_message_ids))

    return cron_collect_bitrix_events
