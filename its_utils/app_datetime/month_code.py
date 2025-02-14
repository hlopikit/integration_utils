

def month_code(date):
    """
    Важно! Переведите в нужную timezone. Например, to_msk(date).

    Пример::

        from django.utils import timezone
        from its_utils.app_datetime.month_code import month_code
        month_code(timezone.now() - timezone.timedelta(days=100))

    Args:
        date:
    Returns:
        01.12.2023 -> 202312
    """
    return int(date.strftime('%Y%m'))
