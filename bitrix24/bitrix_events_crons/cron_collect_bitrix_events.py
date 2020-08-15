# coding=utf-8
from __future__ import unicode_literals

import dateutil.parser
from django.utils import timezone

from integration_utils.bitrix24.models.bitrix_event import BitrixEvent
from integration_utils.bitrix24.models.bitrix_user_token import BitrixUserToken
from settings import ilogger


def cron_collect_bitrix_events(class_path=None):
    """
    Получить новые события на порталах и сохранить их в модель BitrixEvent
    """

    try:
        bx_token = BitrixUserToken.objects.get(user__email='evg@it-solution.ru')
        ilogger.debug('collect_bitrix_events', 'start')

        result = bx_token.call_api_method_v2('event.offline.list')
        events = result['result']

        ilogger.debug('collect_bitrix_events', 'got {} events; total events in queue: {}'.format(
            len(events), result.get('total', 0)
        ))

        message_ids = []
        for event in events:
            ilogger.debug('collect_bitrix_events', '{} got events'.format(event['EVENT_NAME']))

            # Записать событие в бд
            try:
                # Предпочтительно знать время совершения события на портале,
                # а не появления его в нашей базе
                event_dt = dateutil.parser.isoparse(event['TIMESTAMP_X'])
            except (KeyError, ValueError):
                ilogger.error('event_no_or_bad_timestamp', repr(event))
                event_dt = timezone.now()
            BitrixEvent.objects.create(
                event_name=event['EVENT_NAME'],
                data=event, datetime=event_dt
            )

            message_ids.append(event['ID'])

        if message_ids:
            # вычищаем очередь от обработанных событий
            bx_token.call_api_method_v2('event.offline.clear', {'process_id': '', 'id': message_ids})

        ilogger.debug('collect_bitrix_events', 'finished')

        force_collect_events = result.get('total', 0) > 50

        result = 'collected {}, total {}'.format(len(events), result.get('total', "unknown"))

    # except BitrixTimeout as e:
    #     ilogger.warning(
    #         'collect_bitrix_events_timeout',
    #         'TIMEOUT portal: {portal}, timeout: {err!r}\n{link}'
    #         .format(portal=self.portal, err=e,
    #                 link=get_admin_a_tag(self, self.portal)),
    #         exc_info=True,
    #     )
    #     result = 'timeout'
    # except BitrixUserTokenDoesNotExist:
    #     # Закомментировал, т.к в бпстартере порталы деактивировались, но потом им нечем обратно активироваться
    #     # cls.objects.filter(pk=self.pk).update(is_active=False)
    #     # ilogger.warning('portal_settings_deactivated', '{}'.format(get_admin_url(self)))
    #     result = 'no token'
    #
    # except BitrixApiError as e:
    #     if e.is_internal_server_error:
    #         result = 'connection error'
    #     elif e.is_error_connecting_to_authorization_server:
    #         result = 'error_connecting_to_authorization_server'
    #     elif e.is_error_connecting_to_authorization_server:
    #         result = 'error_connecting_to_authorization_server'
    #     elif e.is_connection_to_bitrix_error:
    #         result = 'connection_to_bitrix_error'
    #     elif e.is_no_auth_found:
    #         result = 'no auth found'
    #     else:
    #         ilogger.error(
    #             'collect_bitrix_events',
    #             '{} bitrix api error'
    #             .format(get_admin_a_tag(self, self.portal))
    #         )
    #         result = 'bitrix api error'

    except Exception:
        ilogger.error(
            'collect_bitrix_events',
            'failed to collect events objects on portal'
        )
        result = 'unknown error'

    return result