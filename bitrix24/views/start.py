from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth


@main_auth(on_start=True, set_cookie=True)
def start(request):
    index_path = settings.APP_SETTINGS.application_index_path
    return render(request, 'start.html', locals())

