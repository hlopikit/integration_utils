
class MuteLogger:
    # Немой логгер
    # можно использовать при передаче логгера в Битрикс токен вызовы
    # пример в def call_api_method(

    def do_nothing(self, log_type, message=None, app=None, exc_info=False, params=None):
        return None

    debug = info = warning = warn = error = exception = critical = do_nothing
