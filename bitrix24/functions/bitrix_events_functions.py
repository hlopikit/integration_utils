# coding=utf-8

from __future__ import unicode_literals

import pytz

UNDEFINED = 'undefined'


def date_to_bitrix_format(dt):
    # Переводит в
    # '2023-11-18T13:52:57'
    return dt.astimezone(pytz.timezone('Europe/Moscow')).isoformat()[:19]


def get_bitrix_id_from_event(event):
    event_data = event['EVENT_DATA']

    if event_data.get('id'):
        # Сработало с ONCALENDARENTRYDELETE
        return event_data.get('id')

    for prop in ['FIELDS', 'FIELDS_AFTER', 'FIELDS_BEFORE']:
        fields = event_data.get(prop)
        if fields and fields != UNDEFINED and 'ID' in fields and fields['ID'] and fields['ID'] != UNDEFINED:
            return fields['ID']

    raise ValueError('No bitrix id {}'.format(event))
