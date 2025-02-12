import pytz


def to_msk(date):
    TZ_NAME = 'Europe/Moscow'
    return date.astimezone(pytz.timezone(TZ_NAME))