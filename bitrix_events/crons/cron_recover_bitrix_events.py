from collections import Counter
from typing import Type

from django.utils.module_loading import import_string

from ..classes import BaseBitrixEventObject
from .cron_collect_bitrix_events import BitrixEventCollectionError, process_offline_events, validate_event_class


def recover_bitrix_events(event_class: Type[BaseBitrixEventObject]) -> str:
    """Найти зарезервированные пачки и обработать их

    Запускать после остановки обычного сборщика: PROCESS_ID может принадлежать
    ещё работающему процессу
    """
    validate_event_class(event_class)
    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    token = BitrixUserToken.get_admin_token()
    events = token.call_list_method('event.offline.list', fields={'filter': {'ERROR': 0}})
    pending = Counter(event['PROCESS_ID'] for event in events if event['PROCESS_ID'])

    processed_total = failed_total = 0
    for process_id, remaining in pending.items():
        while remaining > 0:
            result = token.call_api_method('event.offline.get', {'clear': 0, 'process_id': process_id})['result']
            processed, failed = process_offline_events(result, event_class, token)
            if not processed and not failed:
                break
            processed_total += processed
            failed_total += failed
            remaining -= processed + failed

    summary = f'recovered processes {len(pending)}, collected {processed_total}, errors {failed_total}'
    if failed_total:
        raise BitrixEventCollectionError(summary)
    return summary


def cron_recover_bitrix_events(class_path: str) -> str:
    """Добрать зарезервированные пачки для класса по строковому пути"""
    return recover_bitrix_events(import_string(class_path))
