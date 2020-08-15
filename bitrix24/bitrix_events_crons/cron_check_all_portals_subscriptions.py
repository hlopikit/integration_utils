# coding=utf-8

from __future__ import unicode_literals

from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken
from settings import ilogger, APP_SETTINGS


def cron_check_all_portals_subscriptions():
    """
    Подписаться на события и отписаться от более не нужных

    :rtype: dict
    :returns: {
        # Результат батч-подписки
        'bind': {
            'ONCRMACTIVITYADD:online': {
                'result': True,
                'error': None,
            },
            'ONCRMACTIVITYUPDATE:offline': {...},
            ...
        },
        # Результат батч-отписки
        'unbind': {
            'ONCRMACTIVITYDELETE:offline': {
                'result': True,
                'error': None,
            },
            ...
        },
        # Уже были активными и остались такими
        'untouched': {
            'ONCRMACTIVITYADD:offline': {
                'event': 'ONCRMACTIVITYADD',
                'offline': 1,
                ...,
            },
        },
    }
    """

    # Получаем токен и активные подписки
    bx_token = BitrixUserToken.objects.get(user__email='evg@it-solution.ru')
    active_subs_result = bx_token.call_api_method_v2('event.get')['result']

    # Определяем тип подписок и собираем в множество кортежей:
    # {(событие, 'offline'/'online', 'https://...'/'offline'), ...}
    active_subs_map = {}
    already_subscribed_events = set()
    for sub in active_subs_result:
        event_type = 'offline' if sub.get('offline') else 'online'
        handler = sub.get('handler') if sub.get('handler') else 'offline'

        already_subscribed_events.add((sub['event'], event_type, handler))

        event_key = '{}:{}'.format(sub['event'], event_type)
        active_subs_map[event_key] = sub

    # События на которые мы хотим быть подписаны
    active_events = set()
    for event in APP_SETTINGS.bitrix_events_plan:
        active_events.add((event, 'offline', 'offline'))
        # active_events.add((event, 'online', self.BITRIX_ONLINE_EVENT_HANDLER))

    # Должны быть подписаны на эти события, но пока не подписались
    to_subscribe = set(active_events) - set(already_subscribed_events)
    # Левые подписки, отписываемся
    to_unsubscribe = set(already_subscribed_events) - set(active_events)

    # Уже активные нужные подписки, не отписываемся от них
    untouched = {}
    for event, event_type, handler in \
            set(already_subscribed_events) - to_unsubscribe:
        event_key = '{}:{}'.format(event, event_type)
        untouched[event_key] = active_subs_map[event_key]

    # Отписка от лишних событий
    methods = []
    for event, event_type, handler in to_unsubscribe:
        methods.append((
            '{}:{}'.format(event, event_type),
            'event.unbind',
            dict(event=event, event_type=event_type, handler=handler)
        ))
    unbind_result = bx_token.batch_api_call(methods, v=3)
    if not unbind_result.all_ok:
        ilogger.error('unbind_error', 'unbind_result: %r' % unbind_result)

    # Подписка на недостающие события
    methods = []
    for event, event_type, handler in to_subscribe:
        methods.append((
            '{}:{}'.format(event, event_type),
            'event.bind',
            dict(event=event, event_type=event_type, handler=handler)
        ))
    bind_result = bx_token.batch_api_call(methods, v=3)
    if not unbind_result.all_ok:
        ilogger.error('bind_error', 'bind_result: %r' % bind_result)

    # Информация о выполненных действиях
    return dict(
        bind=bind_result,
        unbind=unbind_result,
        untouched=untouched,
    )
