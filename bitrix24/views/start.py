from django.shortcuts import render
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth

from django.http import QueryDict
from six.moves import urllib_parse
import json
from urllib.parse import urlencode


def _get_index_path(request):
    """Возвращает безопасный адрес после iframe-входа в приложение Bitrix24.

    По умолчанию сохраняет `APP_SETTINGS.application_index_path`. Параметр
    `return_to` нужен внешним read-only экранам itsis: сначала Marketplace
    запускает приложение и создаёт cookie, затем пользователь возвращается на
    исходный относительный адрес. Внешние адреса не принимаются, чтобы запуск
    приложения не стал открытым redirect.
    """
    return_to = request.GET.get('return_to', '')
    if return_to.startswith('/') and url_has_allowed_host_and_scheme(
        return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return return_to
    return settings.APP_SETTINGS.application_index_path


@main_auth(on_start=True, set_cookie=True)
def start(request):
    http_referer = request.META.get('HTTP_REFERER')
    try:
        if hasattr(request, 'POST') and 'PLACEMENT_OPTIONS' in request.POST:
            bx_referer_params = QueryDict('', mutable=True)
            bx_referer_params.update(json.loads(request.POST['PLACEMENT_OPTIONS']))
        else:
            bx_referer_params = None
    except Exception as e:
        bx_referer_params = None
    if bx_referer_params is None and http_referer:
        bx_referer_params = QueryDict(urllib_parse.urlparse(http_referer).query)

    index_path = _get_index_path(request)

    params_string = ''
    if bx_referer_params and len(bx_referer_params):
        params_string = '?' + urlencode({'bx_referer_params': json.dumps(bx_referer_params)})
    get_params = request.GET.copy()
    get_params.pop('return_to', None)
    get_params_string = urlencode(get_params, doseq=True)
    if len(get_params_string):
        if params_string:
            params_string += '&'
        else:
            params_string += '&' if '?' in index_path else '?'
        params_string += get_params_string

    index_path += params_string

    return render(request, 'start.html', locals())

