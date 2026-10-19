from typing import Iterable, List

from integration_utils.bitrix24.functions.batch_api_call import BatchResultDict
from settings import ilogger

__all__ = [
    "change_subscriptions",
    "bind_events",
    "unbind_events",
]


def change_subscriptions(method: str, events: Iterable[str]) -> BatchResultDict:
    """Изменить подписки на офлайн-события"""
    log_tag = 'integration_utils.bitrix_events.functions.subscriptions.change_subscriptions'

    if isinstance(events, str):
        raise TypeError('events must be an iterable of event names, not a string')

    names: List[str] = []

    for event in events:
        if not isinstance(event, str) or not event.strip():
            raise ValueError('event names must be non-empty strings')
        names.append(event.strip().upper())

    methods = []

    for event in dict.fromkeys(names):
        methods.append((event, method, {'event': event, 'event_type': 'offline'}))

    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    result = BitrixUserToken.get_admin_token().batch_api_call(methods)

    for event, error in result.iter_errors():
        ilogger.error(
            'bitrix_events_subscription_error',
            f'{method=}, {event=}, {error=}',
            tag=log_tag,
        )
    return result


def bind_events(events: Iterable[str]) -> BatchResultDict:
    """Подписать приложение на список офлайн-событий"""
    return change_subscriptions('event.bind', events)


def unbind_events(events: Iterable[str]) -> BatchResultDict:
    """Отписать приложение от списка офлайн-событий"""
    return change_subscriptions('event.unbind', events)
