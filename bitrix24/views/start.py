from django.shortcuts import render
from django.conf import settings

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth

from django.http import QueryDict
from six.moves import urllib_parse
import json
from urllib.parse import urlencode

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

    index_path = settings.APP_SETTINGS.application_index_path

    params_string = ''
    if bx_referer_params and len(bx_referer_params):
        params_string = '?' + urlencode({'bx_referer_params': json.dumps(bx_referer_params)})
    get_params_string = urlencode(request.GET)
    if len(get_params_string):
        if params_string:
            params_string += '&'
        else:
            params_string += '?'
        params_string += get_params_string

    index_path += params_string

    return render(request, 'start.html', locals())

