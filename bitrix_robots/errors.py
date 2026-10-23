from django.http import HttpResponse


class RobotException(Exception):
    def __init__(self, message=None, http_status=400):
        self.message = type(self).__name__ if message is None else message
        self.http_status = http_status

    def __str__(self):
        return self.message

    def http_response(self):
        return HttpResponse(self.message, status=self.http_status)


class VerificationError(RobotException):
    def __init__(self, message='Verification failed', is_not_logic_error=False):
        """Ошибка проверки запроса робота.

        :param message: Текст ошибки.
        :param is_not_logic_error: Считать причину внешней и логировать её как warning.
        """
        super().__init__(message, 401)
        self._is_not_logic_error = is_not_logic_error

    @property
    def is_not_logic_error(self):
        return self._is_not_logic_error


class DelayProcess(RobotException):
    pass
