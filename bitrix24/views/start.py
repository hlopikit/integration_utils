from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

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

    if bx_referer_params and len(bx_referer_params):
        index_path += '?' + urlencode(bx_referer_params)

    return render(request, 'start.html', locals())

