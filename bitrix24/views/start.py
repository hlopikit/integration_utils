import json
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import QueryDict
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth


def _get_index_path(request, bx_referer_params=None):
    """
    Возвращает безопасный адрес для iframe-view `start` после входа в Bitrix24.

    По умолчанию сохраняет `APP_SETTINGS.application_index_path`. Параметр
    `return_to` нужен внешним read-only экранам itsis: сначала Marketplace
    запускает приложение и создаёт cookie, затем пользователь возвращается на
    исходный относительный адрес. Внешние адреса не принимаются, чтобы запуск
    приложения не стал открытым redirect.

    :param request: GET-параметр `return_to` имеет приоритет над параметрами запуска.
    :param bx_referer_params: параметры из `PLACEMENT_OPTIONS` или резервного HTTP Referer;
        используются, если в GET нет непустого `return_to`.
    """
    return_to = request.GET.get('return_to', '')
    if not return_to and bx_referer_params:
        return_to = bx_referer_params.get('return_to', '')
    if isinstance(return_to, str) and return_to.startswith('/') and url_has_allowed_host_and_scheme(
        return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return return_to
    return settings.APP_SETTINGS.application_index_path


@main_auth(on_start=True, set_cookie=True)
def start(request):
    """При iframe-запуске Marketplace создаёт auth-cookie и возвращает на запрошенную страницу."""
    http_referer = request.META.get('HTTP_REFERER')
    bx_referer_params = None
    if 'PLACEMENT_OPTIONS' in request.POST:
        try:
            placement_options = json.loads(request.POST['PLACEMENT_OPTIONS'])
        except json.JSONDecodeError:
            placement_options = None
        if isinstance(placement_options, dict):
            bx_referer_params = QueryDict('', mutable=True)
            bx_referer_params.update(placement_options)
    if bx_referer_params is None and http_referer:
        bx_referer_params = QueryDict(urlsplit(http_referer).query)

    index_path = _get_index_path(request, bx_referer_params)

    forwarded_params = request.GET.copy()
    forwarded_params.pop('return_to', None)
    if bx_referer_params:
        bx_referer_params = bx_referer_params.copy()
        bx_referer_params.pop('return_to', None)
        if bx_referer_params:
            forwarded_params['bx_referer_params'] = json.dumps(bx_referer_params)

    if forwarded_params:
        index_url = urlsplit(index_path)
        index_query = forwarded_params.urlencode()
        if index_url.query:
            index_query = f'{index_url.query}&{index_query}'
        index_path = urlunsplit(index_url._replace(query=index_query))

    return render(request, 'start.html', locals())

