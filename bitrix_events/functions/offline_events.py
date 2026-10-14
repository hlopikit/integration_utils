from typing import Any, Dict, Tuple, Type

from integration_utils.bitrix24.models import BitrixUserToken
from integration_utils.bitrix_events.classes import BaseBitrixEventObject
from integration_utils.bitrix_events.models import BaseBitrixEventModel
from settings import ilogger


def receive_offline_events(
    event_class: Type[BaseBitrixEventObject],
    result: Dict[str, Any],
    token: 'BitrixUserToken',
    clear_on_get: bool = False,
    clear_error: bool = True
) -> Tuple[int, int]:
    """
    Получить оффлайн-события, собранные через event.offline.get, и при необходимости их обработать.
    :param event_class: класс события.
    :param result: результат метода event.offline.get.
    :param token: токен для обращения в Битрикс.
    :param clear_on_get: очищались ли события через event.offline.get с clear=1.
    :param clear_error: очищать событие из очереди при ошибке обработки (event.offline.error).
    """
    log_tag = 'integration_utils.bitrix_events.functions.offline_events.receive_offline_events'

    process_id = result['process_id']
    successful_message_ids = []
    failed_message_ids = []

    for result_event in result['events']:
        event_id = result_event['ID']
        event_name = result_event['EVENT_NAME']
        message_id = result_event['MESSAGE_ID']
        log_message = f"{process_id=}, {event_id=}, {event_name=}, {message_id=}"
        try:
            event = event_class.from_bitrix_data(result_event)
            if event_class.PROCESS_WHEN_RECEIVED:
                event.process()
        except Exception as e:
            failed_message_ids.append(message_id)
            ilogger.error('bitrix_event_handle_fail', f"({e}): {log_message}", tag=log_tag)
        else:
            successful_message_ids.append(message_id)
            ilogger.debug('bitrix_event_handle_success', log_message, tag=log_tag)

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
    Дособрать оффлайн-события, зарезервированные через event.offline.get, но не очищенные.
    :param event_class: класс события.
    :param token: токен для обращения в Битрикс.
    :param clear_on_get: очищать события через event.offline.get с clear=1.
    :param clear_error: очищать событие из очереди при ошибке обработки (event.offline.error).
    """
    list_result = token.call_api_method('event.offline.list', {'filter': {'ERROR': 0}})['result']
    recovered_process_ids = dict.fromkeys(
        event['PROCESS_ID']
        for event in list_result
        if event['PROCESS_ID']
    )

    successful_total = failed_total = 0
    for process_id in recovered_process_ids:
        clear = int(clear_on_get)
        result = token.call_api_method('event.offline.get', {
            'clear': clear, 'process_id': process_id
        })['result']
        successful, failed = receive_offline_events(
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
    В крон-функции вызовите collect_offline_events со своим классом события и нужными параметрами.

    Сценарии использования:

    - Запуск по умолчанию собирает и резервирует события через event.offline.get,
      успешно обработанные очищаются из очереди через event.offline.clear,
      а ошибочные помечаются в очереди через event.offline.error.
      Резервирование через clear=0 требует возможности rest_offline_extended,
      иначе Битрикс вернёт ошибку WRONG_LICENSE.
    - Используйте recover=True, чтобы перед основным сбором дополучить события,
      зарезервированные прошлым запуском, но не очищенные по какой-либо причине.
      Запуски с recover не должны пересекаться: recover может повторно получить пакет,
      который ещё обрабатывает другой запуск. При возможном пересечении используйте внешнюю блокировку.
    - Используйте clear_error=False вместе с recover=True, чтобы не помечать ошибочные
      события в очереди и дополучать их через recover в следующих запусках.
    - Используйте clear_on_get=True для очистки события из очереди через event.offline.get.
      Это позволяет не делать отдельные запросы clear и error, ускоряя выполнение функции.
      При этом возможна потеря события при ошибке и дополучить через recover их не получится.

    :param event_class: класс события.
    :param clear_on_get: очищать события через event.offline.get с clear=1.
    :param clear_error: очищать события при ошибке обработки (event.offline.error).
    :param recover: дополучать события, зарезервированные через event.offline.get, но не очищенные.
    """
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
    collected_successful, collected_failed = receive_offline_events(
        event_class=event_class,
        result=result,
        token=token,
        clear_on_get=clear_on_get,
        clear_error=clear_error,
    )
    summary = f"{collected_successful=}, {collected_failed=}{summary}"
    return summary


def process_offline_events(event_model: Type[BaseBitrixEventModel], limit: int = 50) -> str:
    """
    Обработать пачку модельных оффлайн-событий.
    Для использования в приложении создайте крон-функцию без параметров (для cron_starter).
    В крон-функции вызовите process_offline_events со своей моделью события и нужным лимитом.
    :param event_model: модель события.
    :param limit: максимальное число событий в пачке.
    """
    log_tag = 'integration_utils.bitrix_events.functions.offline_events.process_offline_events'

    events_qs = event_model.objects.filter(process_started_at__isnull=True).order_by('created_at', 'pk')[:limit]
    processed_successful = processed_failed = processed_skipped = 0

    for event in events_qs:
        pk = event.pk
        bitrix_id = event.bitrix_id
        event_name = event.event_name
        log_message = f'{pk=}, {bitrix_id=}, {event_name=}'
        try:
            event.process_with_lock()
        except Exception as e:
            processed_failed += 1
            ilogger.error('bitrix_event_process_fail', f'({e}): {log_message}', tag=log_tag)
        else:
            if event.process_started_at is None:
                processed_skipped += 1
                ilogger.warning('bitrix_event_process_skip', log_message, tag=log_tag)
                continue
            processed_successful += 1
            ilogger.debug('bitrix_event_process_success', log_message, tag=log_tag)

    return f'{processed_successful=}, {processed_failed=}, {processed_skipped=}'
