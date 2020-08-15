import django
from django.conf import settings
from six.moves.http_cookies import CookieError

from integration_utils.bitrix24.models import BitrixUserToken

class InvalidHeader(Exception):
    pass

def get_bitrix_user_token_from_header(request):

    bitrix_user_token_signed_pk = request.headers.get('X-Bitrix-Signed-Token')

    if bitrix_user_token_signed_pk:
        request.bitrix_user_token = BitrixUserToken.get_by_signed_pk(bitrix_user_token_signed_pk)
    else:
        raise InvalidHeader()
