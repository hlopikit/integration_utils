from arrow import Arrow, ArrowFactory
from arrow import api

from its_utils.app_datetime.calendar_work_days import WORK_AND_REST_DAYS


# https://pypi.org/project/arrow/

def dt_its(*args, **kwargs):
    # сокращение для DtIts.get() и обрабатывает None!!!
    if args == (None, ) and not kwargs:
        return None
    return DtIts.get(*args, **kwargs)

class DtIts(Arrow):
    # !!! ЧИТАТЬ РИДМИ
    # чтобы работало как arrow.get
    # DtIts.get('2013-05-11T21:23:58.970460+07:00')
    # <DtIts [2013-05-11T21:23:58.970460+07:00]>
    #
    # now = DtIts.now()
    # after_one_hour = now.shift(hours=1)

    def bitrix_format(self):
        return self.to('Europe/Moscow').isoformat()

    def bitrix_format(self):
        return self.isoformat()

    @classmethod
    def get(cls, *args, **kwargs):
        """
        Собрать класс DtIts из входящих параметров
        from its_utils.app_datetime.dt_its import DtIts
        from django.utils import timezone
        DtIts.get(timezone.now())
        """
        ar = ArrowFactory(type=cls).get(*args, **kwargs)
        return ar

    def start_of_day(self):
        return self.replace(hour=0, minute=0, second=0, microsecond=0)

    def end_of_day(self):
        return self.replace(hour=23, minute=59, second=59, microsecond=999999)


    def shift_workdays(self, days):
        # Смещает дни учитывая рабочие и выходные
        # Возварщает новый объект
        # Есди сегодня понедельник, то один рабочий день назад это пятница
        # А если сегодня суббота????? то скорее тоже пятница
        # создаем новый результат, чтобы не вернуть тот же объект
        result = DtIts.get(self)
        while days:
            if days > 0:
                result = result.shift(days=1)
            else:
                result = result.shift(days=-1)
            if result.is_workday():
                if days > 0:
                    days -= 1
                else:
                    days += 1

        return result.shift()

    def is_workday(self):
        day_type = WORK_AND_REST_DAYS.get((self.year, self.month, self.day), None)
        if day_type is not None:
            return day_type

        if self.weekday() in [5, 6]:
            return False
        else:
            return True

    @staticmethod
    def workdays_diff(dt1: 'DtIts', dt2: 'DtIts') -> int:
        # Должен вычислить количество полных рабочих суток
        # если dt1 > dt2, то вернет положительное число, иначе отрицательное
        # Если dt1 = пондельник 13-00 и dt2 = предыдущая пятница 16-00, то рабочие сутки еще не прошли
        days = 0
        if dt1 == dt2:
            return 0
        if dt1 > dt2:
            dt_min = dt2
            dt_max = dt1
            direction = 1
        else:
            dt_max = dt2
            dt_min = dt1
            direction = -1
        while True:
            dt_min = dt_min.shift_workdays(days=1)
            if dt_max >= dt_min:
                days += 1
            else:
                break

        return days * direction
