import pytz


def to_msk(date):
    return date.astimezone(pytz.timezone('Europe/Moscow'))
