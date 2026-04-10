from datetime import date

from django.utils import timezone

from integration_utils.iu_datetime.calendar_work_days import WORK_AND_REST_DAYS


def is_workday(check_date: date) -> bool:
    day_tuple = check_date.timetuple()[:3]  # (year, month, day)
    return WORK_AND_REST_DAYS.get(day_tuple, check_date.weekday() < 5)

def is_today_workday() -> bool:
    return is_workday(timezone.localdate())
