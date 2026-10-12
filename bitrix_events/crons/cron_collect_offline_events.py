from typing import TYPE_CHECKING, Any, Dict, Tuple, Type

from django.utils.module_loading import import_string

from settings import ilogger
from ..classes import BaseBitrixEventObject
from ..models import BaseBitrixEventModel

if TYPE_CHECKING:
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken


class BitrixEventCollectionError(RuntimeError):
    """Часть событий в пачке не удалось сохранить или обработать"""


def validate_event_class(event_class: Type[BaseBitrixEventObject]):
    if not issubclass(event_class, BaseBitrixEventObject):
        raise TypeError('event_class must inherit BaseBitrixEventObject')


def handle_offline_events(result: Dict[str, Any], event_class: Type[BaseBitrixEventObject], token: 'BitrixUserToken') -> Tuple[int, int]:
    """
    Обработать оффлайн-события, полученные из event.offline.get.
    """
    log_tag = 'integration_utils.bitrix_events.crons.cron_collect_bitrix_events.process_offline_events'

    process_id = result['process_id']
    successful_message_ids = []
    failed_message_ids = []

    for data in result['events']:
        message_id = data['MESSAGE_ID']
        event_id = data['ID']
        event_name = data['EVENT_NAME']
        try:
            event = event_class.from_bitrix_data(data)
            if event_class.PROCESS_ON_COLLECT:
                event.process()
        except Exception as e:
            failed_message_ids.append(message_id)
            ilogger.error(
                'bitrix_event_process_fail',
                f"({e}): {process_id=}, {event_id=}, {event_name=}, {message_id=}",
                tag=log_tag,
            )
        else:
            successful_message_ids.append(message_id)
            ilogger.debug(
                'bitrix_event_process_success',
                f'{process_id=}, {event_id=}, {event_name=}, {message_id=}',
                tag=log_tag,
            )

    if successful_message_ids:
        token.call_api_method('event.offline.clear', {'process_id': process_id, 'message_id': successful_message_ids})
    if failed_message_ids:
        token.call_api_method('event.offline.error', {'process_id': process_id, 'message_id': failed_message_ids})

    return len(successful_message_ids), len(failed_message_ids)


def collect_offline_events(event_class: Type[BaseBitrixEventObject]) -> str:
    """
    Получить новую пачку оффлайн-событий для event_class.
    :raise BitrixEventCollectionError:
    """
    validate_event_class(event_class)
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    result = token.call_api_method('event.offline.get', {'clear': 0})['result']
    successful, failed = handle_offline_events(result, event_class, token)
    summary = f'{successful=}, {failed=}'
    if failed:
        raise BitrixEventCollectionError(summary)
    return summary


def cron_collect_offline_events(event_class_path: str) -> str:
    """
    Получить новую пачку оффлайн-событий для event_class.
    Подходит для запуска в кроне со строчным параметром пути до event_class.
    """
    event_class = import_string(event_class_path)
    return collect_offline_events(event_class)
