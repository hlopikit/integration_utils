from arrow import Arrow, ArrowFactory

from integration_utils.its_utils.app_datetime.calendar_work_days import WORK_AND_REST_DAYS
from settings import ilogger

# https://pypi.org/project/arrow/

def dt_its(*args, **kwargs):
    # сокращение для DtIts.get() и обрабатывает None!!!
    if args == (None,) and not kwargs:
        return None
    if args and isinstance(args[0], str) and args[0].startswith('0000-01-01'):
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
        '2025-05-01T20:27:51.614763+03:00'
        return self.isoformat()

    def replace_to_moscow(self):
        return self.replace(tzinfo='Europe/Moscow')

    def to_b24_database(self):
        """
        Задача этой функции перевести к такому виду чтобы можно было делать запросы к БД Битрикс24, там даты хранятся в МСК без часового пояса (может не у всех в МСК)
        Вариант 1: делаем например timezone.now() и это в UTC уже, тогда надо добавить 3 часа и replace_to_utc сделать...
        Вариант 2: у нас уже дата с MSK+3, ТО НАДО replace_utc сделать

        Итог вот такие конструкции вернут одинаковое
        from integration_utils.iu_datetime.dt_its import DtIts
        DtIts.now().to_b24_database()

        from django.utils import timezone
        DtIts.get(timezone.now()).to_b24_database()

        Returns:

        """
        if self.utcoffset().seconds == 0:
            # У нас в UTC, то добавляем + 3
            return self.shift(hours=3)
        elif self.utcoffset().seconds == 10800:
            # МСК время, убираем знание таймзоны
            return self.replace_to_utc()
        else:
            ilogger.error("dtits_timezene", "Добавьте поддержку других таймзон")



    def replace_to_utc(self):
        """
        Можно использовать когда хотим стукнутсья в БД Битрикс24,
        dt = DtIts.now().shift(minutes=-5) # Получили время текущее, но в БД Битрикс хранится без часового пояса
        comments = BForumMessage.objects.qs_tasks_comments().qs_not_service().filter(post_date__gte=dt.replace_to_utc().datetime).order_by('id')
        Returns:

        """
        return self.replace(tzinfo='UTC')

    @classmethod
    def get(cls, *args, **kwargs):
        """
        Собрать класс DtIts из входящих параметров
        from integration_utils.iu_datetime.dt_its import DtIts
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
        # Смещает дни учитывая рабочие и выходные.
        # Возвращает новый объект.
        # Если сегодня понедельник, то один рабочий день назад - это пятница.
        # А если сегодня суббота, то тоже - пятница.
        # Создаём новый результат, чтобы не вернуть тот же объект.
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
        # Должен вычислить количество полных рабочих суток.
        # Если dt1 > dt2, то вернет положительное число, иначе - отрицательное.
        # Если dt1 = понедельник 13-00 и dt2 = предыдущая пятница 16-00, то рабочие сутки ещё не прошли.
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
