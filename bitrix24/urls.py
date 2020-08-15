from django.urls import path

from integration_utils.bitrix24.views.start import start

urlpatterns = [
    path('', start),
]
