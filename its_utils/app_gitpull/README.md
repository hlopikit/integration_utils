###Приложения для git pull на продакшне


####Подключение 
1) в INSTALLED_APPS добавить 'its_utils.app_gitpull',
2) в urls добавить
url(r'^its/', include('its_utils.app_gitpull.urls')),
3) Можно добавить в settings настройки
дефолт можно посмотреть app_gitpull/settings.py

####Использование
1) в браузере запускаем http://domain.com/its/gitpull
