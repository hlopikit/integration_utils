from traceback import format_exc
from typing import TYPE_CHECKING, Any, Dict, Tuple, Type

from django.utils.module_loading import import_string
from settings import ilogger

from ..classes import BaseBitrixEventObject
from ..models import BaseBitrixEventModel

if TYPE_CHECKING:
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken


LOG_TAG = 'integration_utils.bitrix_events'


class BitrixEventCollectionError(RuntimeError):
    """Часть событий в пачке не удалось сохранить или обработать"""


def validate_event_class(event_class: Type[BaseBitrixEventObject]):
    if not issubclass(event_class, BaseBitrixEventObject):
        raise TypeError('event_class must inherit BaseBitrixEventObject')


def process_offline_events(result: Dict[str, Any], event_class: Type[BaseBitrixEventObject],
                           token: 'BitrixUserToken') -> Tuple[int, int]:
    """Обработать и подтвердить полученные события"""
    process_id = result['process_id']
    processed_message_ids = []
    failed_message_ids = []
    for data in result['events']:
        message_id = data['MESSAGE_ID']
        try:
            event = event_class.from_bitrix_data(data)
            if not isinstance(event, BaseBitrixEventModel):
                event.process()
                ilogger.info('bitrix_event_processed_without_saving',
                             f'process_id={process_id}, event_id={data["ID"]}, event_name={data["EVENT_NAME"]}', tag=LOG_TAG)
        except Exception:
            failed_message_ids.append(message_id)
            ilogger.error('bitrix_event_processing_failed',
                          f'process_id={process_id}, event_id={data.get("ID")}, message_id={message_id}\n{format_exc()}',
                          tag=LOG_TAG)
        else:
            processed_message_ids.append(message_id)

    if processed_message_ids:
        token.call_api_method('event.offline.clear', {'process_id': process_id, 'message_id': processed_message_ids})
    if failed_message_ids:
        token.call_api_method('event.offline.error', {'process_id': process_id, 'message_id': failed_message_ids})
    return len(processed_message_ids), len(failed_message_ids)


def collect_bitrix_events(event_class: Type[BaseBitrixEventObject]) -> str:
    """Получить и обработать новую пачку событий"""
    validate_event_class(event_class)
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    result = token.call_api_method('event.offline.get', {'clear': 0})['result']
    processed, failed = process_offline_events(result, event_class, token)
    summary = f'collected {processed}, errors {failed}'
    if failed:
        raise BitrixEventCollectionError(summary)
    return summary


def cron_collect_bitrix_events(class_path: str) -> str:
    """Собрать события для класса по строковому пути"""
    return collect_bitrix_events(import_string(class_path))
