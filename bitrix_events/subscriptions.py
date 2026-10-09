from typing import Iterable

from settings import ilogger

from integration_utils.bitrix24.functions.batch_api_call import BatchResultDict
from .crons.cron_collect_bitrix_events import LOG_TAG


def _change_subscriptions(method: str, events: Iterable[str]) -> BatchResultDict:
    if isinstance(events, str):
        raise TypeError('events must be an iterable of event names, not a string')
    names = []
    for event in events:
        if not isinstance(event, str) or not event.strip():
            raise ValueError('event names must be non-empty strings')
        names.append(event.strip().upper())
    methods = []
    for event in dict.fromkeys(names):
        methods.append((event, method, {'event': event, 'event_type': 'offline'}))
    if not methods:
        return BatchResultDict()

    from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken

    result = BitrixUserToken.get_admin_token().batch_api_call(methods)
    for event, error in result.iter_errors():
        ilogger.error('bitrix_events_subscription_error',
                      f'method={method}, event={event}, error={error}', tag=LOG_TAG)
    return result


def bind_events(events: Iterable[str]) -> BatchResultDict:
    """Подписать приложение на список офлайн-событий"""
    return _change_subscriptions('event.bind', events)


def unbind_events(events: Iterable[str]) -> BatchResultDict:
    """Отписать приложение от списка офлайн-событий"""
    return _change_subscriptions('event.unbind', events)
