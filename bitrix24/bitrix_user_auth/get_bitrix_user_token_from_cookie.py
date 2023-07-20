import django
from django.conf import settings
from six.moves.http_cookies import CookieError

from integration_utils.bitrix24.models import BitrixUserToken


class EmptyCookie(Exception):
    pass


def get_bitrix_user_token_from_cookie(request):

    auth_cookie = 'b24app_auth_{}'.format(settings.APP_SETTINGS.app_name)


    bitrix_user_token_signed_pk = request.COOKIES.get(auth_cookie)

    if bitrix_user_token_signed_pk:
        request.bitrix_user_token = BitrixUserToken.get_by_signed_pk(bitrix_user_token_signed_pk)
        request.bitrix_user = request.bitrix_user_token.user
        request.bitrix_user_is_new = False
        return request.bitrix_user_token
    else:
        raise EmptyCookie()
