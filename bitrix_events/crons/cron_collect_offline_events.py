from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, Tuple, Type

from django.utils.module_loading import import_string

from settings import ilogger
from ..classes import BaseBitrixEventObject

if TYPE_CHECKING:
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken


class BitrixEventCollectionError(RuntimeError):
    """Часть событий в пачке не удалось сохранить или обработать"""


def validate_event_class(event_class: Type[BaseBitrixEventObject]):
    if not issubclass(event_class, BaseBitrixEventObject):
        raise TypeError('event_class must inherit BaseBitrixEventObject')


def handle_offline_events(offline_result: Dict[str, Any], event_class: Type[BaseBitrixEventObject], token: 'BitrixUserToken', clear_on_get: bool = False, clear_with_error: bool = True) -> Tuple[int, int]:
    """Обработать оффлайн-события, полученные из event.offline.get."""
    log_tag = 'integration_utils.bitrix_events.crons.cron_collect_offline_events.handle_offline_events'

    process_id = offline_result['process_id']
    successful_message_ids = []
    failed_message_ids = []

    for offline_event_data in offline_result['events']:
        message_id = offline_event_data['MESSAGE_ID']
        event_id = offline_event_data['ID']
        event_name = offline_event_data['EVENT_NAME']
        try:
            event = event_class.from_bitrix_data(offline_event_data)
            if event_class.PROCESS_ON_COLLECT:
                event.process()
        except Exception as exc:
            failed_message_ids.append(message_id)
            ilogger.error(
                'bitrix_event_processing_failed',
                f'{exc=}, {process_id=}, {event_id=}, {event_name=}, {message_id=}',
                tag=log_tag,
            )
        else:
            successful_message_ids.append(message_id)
            ilogger.debug(
                'bitrix_event_processed',
                f'{process_id=}, {event_id=}, {event_name=}, {message_id=}',
                tag=log_tag,
            )

    if clear_on_get:
        return len(successful_message_ids), len(failed_message_ids)

    if successful_message_ids:
        token.call_api_method('event.offline.clear', {'process_id': process_id, 'message_id': successful_message_ids})
    if clear_with_error and failed_message_ids:
        token.call_api_method('event.offline.error', {'process_id': process_id, 'message_id': failed_message_ids})

    return len(successful_message_ids), len(failed_message_ids)


def recover_offline_events(
    event_class: Type[BaseBitrixEventObject],
    token: 'BitrixUserToken',
    clear_on_get: bool,
    clear_with_error: bool,
) -> Tuple[Dict[str, int], int, int]:
    """Обработать оставшиеся зарезервированными пачки оффлайн-событий."""
    offline_events = token.call_list_method('event.offline.list', fields={'filter': {'ERROR': 0}})
    recovered_processes = Counter(event['PROCESS_ID'] for event in offline_events if event['PROCESS_ID'])

    successful_total = failed_total = 0
    for process_id, remaining in recovered_processes.items():
        while remaining > 0:
            offline_result = token.call_api_method(
                'event.offline.get',
                {'clear': int(clear_on_get), 'process_id': process_id},
            )['result']
            successful, failed = handle_offline_events(
                offline_result,
                event_class,
                token,
                clear_on_get=clear_on_get,
                clear_with_error=clear_with_error,
            )
            if not successful and not failed:
                break
            successful_total += successful
            failed_total += failed
            remaining -= successful + failed
            has_unacknowledged_failures = failed > 0 and not clear_with_error
            if clear_on_get or has_unacknowledged_failures:
                break

    return dict(recovered_processes), successful_total, failed_total


def collect_offline_events(
    event_class: Type[BaseBitrixEventObject],
    clear_on_get: bool = False,
    clear_with_error: bool = True,
    recover: bool = False,
) -> str:
    """
    Собрать оффлайн-события для event_class.
    :raise BitrixEventCollectionError:
    """
    validate_event_class(event_class)
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    recovered_processes = {}
    successful = failed = 0
    if recover:
        recovered_processes, successful, failed = recover_offline_events(
            event_class,
            token,
            clear_on_get=clear_on_get,
            clear_with_error=clear_with_error,
        )

    offline_result = token.call_api_method('event.offline.get', {'clear': int(clear_on_get)})['result']
    collected_successful, collected_failed = handle_offline_events(
        offline_result,
        event_class,
        token,
        clear_on_get=clear_on_get,
        clear_with_error=clear_with_error,
    )
    successful += collected_successful
    failed += collected_failed

    summary = f'{successful=}, {failed=}'
    if recover:
        summary = f'{recovered_processes=}, {summary}'
    if failed:
        raise BitrixEventCollectionError(summary)
    return summary


def cron_collect_offline_events(
    event_class_path: str,
    clear_on_get: bool = False,
    clear_with_error: bool = True,
    recover: bool = False,
) -> str:
    """
    Собрать оффлайн-события для event_class.
    clear_on_get удаляет события при получении без отдельного подтверждения, допуская их потерю при ошибке.
    clear_with_error при clear_on_get=False помечает события с ошибкой обработки через event.offline.error.
    recover сначала обрабатывает оставшиеся зарезервированными пачки через event.offline.list.
    Подходит для запуска в кроне со строчным параметром пути до event_class.
    """
    event_class = import_string(event_class_path)
    return collect_offline_events(
        event_class,
        clear_on_get=clear_on_get,
        clear_with_error=clear_with_error,
        recover=recover,
    )
