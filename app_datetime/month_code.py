

def month_code(date):
    """
    Важно! переведите в timezone нужную
    например to_msk(date)


    Args:
        date:

    Returns:
        # Переводит дату к коду месяца
        # 202312 - декабрь 2023 года

    Examples:
        from django.utils import timezone
        from its_utils.app_datetime.month_code import month_code
        month_code(timezone.now() - timezone.timedelta(days=100))


    """



    return int(date.strftime('%Y%m'))