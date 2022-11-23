from django.urls import path

from .models import ExampleRobot
from .views import install

app_name = 'bitrix_robot_example'

urlpatterns = [
    path('register/', install, name='register'),
    path('handler/', ExampleRobot.as_view(), name='handler'),
]
