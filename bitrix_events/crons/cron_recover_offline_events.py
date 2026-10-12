from collections import Counter
from typing import Type

from django.utils.module_loading import import_string

from ..classes import BaseBitrixEventObject
from .cron_collect_offline_events import BitrixEventCollectionError, handle_offline_events, validate_event_class


def recover_offline_events(event_class: Type[BaseBitrixEventObject]) -> str:
    """
    Дополучить потерянную пачку оффлайн-событий для event_class.
    Если collect_offline_events остановится на полпути - часть событий будет потеряна.
    Такие события нельзя получить снова через event.offline.get.
    Но их можно дополучить через event.offline.list.

    ВАЖНО: Нужно ждать, пока collect закончит обработку своих событий.
    Иначе recover может подобрать события, обрабатываемые в collect, и запустить обработку по ним второй раз.
    Для этого есть константа RECOVER_AFTER_SECONDS - через сколько секунд считать событие потерянным.
    """
    validate_event_class(event_class)
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    events = token.call_list_method('event.offline.list', fields={'filter': {'ERROR': 0}})
    recovered_processes = Counter(event['PROCESS_ID'] for event in events if event['PROCESS_ID'])

    successful_total = failed_total = 0
    for process_id, remaining in recovered_processes.items():
        while remaining > 0:
            result = token.call_api_method('event.offline.get', {'clear': 0, 'process_id': process_id})['result']
            successful, failed = handle_offline_events(result, event_class, token)
            if not successful and not failed:
                break
            successful_total += successful
            failed_total += failed
            remaining -= successful + failed

    summary = f'{dict(recovered_processes)=}, {successful_total=}, {failed_total=}'
    if failed_total:
        raise BitrixEventCollectionError(summary)
    return summary


def cron_recover_offline_events(event_class_path: str) -> str:
    """
    Дополучить потерянную пачку оффлайн-событий для event_class.
    Подходит для запуска в кроне со строчным параметром пути до event_class.
    """
    event_class = import_string(event_class_path)
    return recover_offline_events(event_class)
