from collections import Counter
from typing import Type, Dict, Any, Tuple

from integration_utils.bitrix24.models import BitrixUserToken
from integration_utils.bitrix_events.classes import BaseBitrixEventObject
from integration_utils.bitrix_events.crons.cron_collect_offline_events import validate_event_class
from settings import ilogger


def handle_offline_events(
    event_class: Type[BaseBitrixEventObject],
    result: Dict[str, Any],
    token: 'BitrixUserToken',
    clear_on_get: bool = False,
    clear_error: bool = True
) -> Tuple[int, int]:
    """
    Обработать оффлайн-события, полученные из event.offline.get.
    :param event_class: класс события.
    :param result: результат метода event.offline.get.
    :param token: токен для обращения в Битрикс.
    :param clear_on_get: очищались ли события через event.offline.get с clear=1.
    :param clear_error: очищать событие из очереди при ошибке обработки (event.offline.error).
    """
    log_tag = 'integration_utils.bitrix_events.crons.cron_collect_offline_events.handle_offline_events'

    process_id = result['process_id']
    successful_message_ids = []
    failed_message_ids = []

    for event in result['events']:
        event_id = event['ID']
        event_name = event['EVENT_NAME']
        message_id = event['MESSAGE_ID']
        log_message = f"{process_id=}, {event_id=}, {event_name=}, {message_id=}"
        try:
            event = event_class.from_bitrix_data(event)
            if event_class.PROCESS_ON_COLLECT:
                event.process()
        except Exception as e:
            failed_message_ids.append(message_id)
            ilogger.error('bitrix_event_process_fail', f"({e}): {log_message}", tag=log_tag)
        else:
            successful_message_ids.append(message_id)
            ilogger.debug('bitrix_event_process_success', log_message, tag=log_tag)

    if clear_on_get:
        return len(successful_message_ids), len(failed_message_ids)

    if successful_message_ids:
        token.call_api_method('event.offline.clear', {'process_id': process_id, 'message_id': successful_message_ids})
    if failed_message_ids and clear_error:
        token.call_api_method('event.offline.error', {'process_id': process_id, 'message_id': failed_message_ids})

    return len(successful_message_ids), len(failed_message_ids)


def recover_offline_events(
    event_class: Type[BaseBitrixEventObject],
    token: 'BitrixUserToken',
    clear_on_get: bool = False,
    clear_error: bool = True,
) -> Tuple[int, int]:
    """
    Дополучить оффлайн-события, зарезервированные через event.offline.get, но не очищенные.
    :param event_class: класс события.
    :param token: токен для обращения в Битрикс.
    :param clear_on_get: очищать события через event.offline.get с clear=1.
    :param clear_error: очищать событие из очереди при ошибке обработки (event.offline.error).
    """
    list_result = token.call_api_method('event.offline.list', {'filter': {'ERROR': 0}})['result']
    recovered_processes = Counter(event['PROCESS_ID'] for event in list_result if event['PROCESS_ID'])

    successful_total = failed_total = 0
    for process_id, _ in recovered_processes.items():
        clear = int(clear_on_get)
        result = token.call_api_method('event.offline.get', {
            'clear': clear, 'process_id': process_id
        })['result']
        successful, failed = handle_offline_events(
            event_class=event_class,
            result=result,
            token=token,
            clear_on_get=clear_on_get,
            clear_error=clear_error,
        )
        successful_total += successful
        failed_total += failed

    return successful_total, failed_total


def collect_offline_events(
    event_class: Type[BaseBitrixEventObject],
    clear_on_get: bool = False,
    clear_error: bool = True,
    recover: bool = False,
) -> str:
    """
    Собрать оффлайн-события.
    Для использования в приложении создайте крон-функцию без параметров (для cron_starter).
    В созданной функции вызовите эту функцию со своим классом события и нужными параметрами.
    :param event_class: класс события.
    :param clear_on_get: очищать события через event.offline.get с clear=1.
    :param clear_error: очищать события при ошибке обработки (event.offline.error).
    :param recover: дополучать события, зарезервированные через event.offline.get, но не очищенные.
    """
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    summary = ""

    if recover:
        recovered_successful, recovered_failed = recover_offline_events(
            event_class=event_class,
            token=token,
            clear_on_get=clear_on_get,
            clear_error=clear_error,
        )
        summary = f"{summary}, {recovered_successful=}, {recovered_failed=}"

    clear = int(clear_on_get)
    result = token.call_api_method('event.offline.get', {'clear': clear})['result']
    collected_successful, collected_failed = handle_offline_events(
        event_class=event_class,
        result=result,
        token=token,
        clear_on_get=clear_on_get,
        clear_error=clear_error,
    )
    summary = f"{collected_successful=}, {collected_failed=}{summary}"
    return summary
