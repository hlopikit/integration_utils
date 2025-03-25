# Добавить в settings.py
# from integration_utils.its_utils.mute_logger import MuteLogger
# ilogger = MuteLogger()
from django.conf import settings


class MuteLogger:
    # Немой логгер
    # можно использовать при передаче логгера в Битрикс токен вызовы
    # пример в def call_api_method(

    def do_nothing(self, log_type, message=None, app=None, exc_info=False, params=None, **kwargs):
        if settings.DEBUG:
            print("INFO: {} => {}".format(log_type, message))
        return None

    debug = info = warning = warn = error = exception = critical = do_nothing
