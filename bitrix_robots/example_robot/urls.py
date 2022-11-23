from django.urls import path

from .models import ExampleRobot
from .views import install, uninstall

app_name = 'bitrix_robot_example'

urlpatterns = [
    path('install/', install, name='install'),
    path('uninstall/', uninstall, name='uninstall'),
    path('handler/', ExampleRobot.as_view(), name='handler'),
]
