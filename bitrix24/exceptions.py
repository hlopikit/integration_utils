from django.conf import settings


class BitrixApiException(Exception):
    """
    Ошибки от АПИ
    """
    pass


class BitrixApiError(BitrixApiException):

    TOKEN_DEACTIVATED = 'token_deactivated'

    def __init__(self, status_code, response):
        self.status_code = status_code
        self.response = response
        if settings.DEBUG:
            print(response.text)

    def __str__(self):
        return "{} {}".format(self.status_code, self.response.text)


class ConnectionToBitrixError(Exception):
    pass


# class BitrixTimeout(Exception):
#     def __init__(self, requests_timeout, timeout):
#         self.request_timeout = requests_timeout
#         self.timeout = timeout
#
#     def __str__(self):
#         return '[{self.timeout} sec.] ' \
#                'requests_timeout={self.request_timeout!r} ' \
#                'request={self.request_timeout.request!r}'.format(self=self)
#
#     def __repr__(self):
#         rv = '<BitrixTimeout {!s}>'.format(self)
#         return rv