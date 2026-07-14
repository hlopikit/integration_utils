###Приложения для git pull на продакшне

В `settings.ITS_UTILS_GITPULL` можно указать `GIT_HTTP_PROXY` в формате `http://domain:port`.
Этот proxy будет использоваться для HTTP/HTTPS remote в git-командах, которые ходят в remote: `git pull`, `git submodule update` и аналогичные вызовы через `app_gitpull`.

Для SSH remote нужно отдельно указать `GIT_SSH_COMMAND`. Пример:

```python
ITS_UTILS_GITPULL = {
    'GIT_HTTP_PROXY': 'http://proxy.example.com:3128',
    'GIT_SSH_COMMAND': "ssh -o ProxyCommand='corkscrew proxy.example.com 3128 %h %p'",
}
```

`GIT_SSH_COMMAND` передаётся в окружение git как есть, без авто-генерации и без привязки к конкретной утилите.


####Подключение 
1) в INSTALLED_APPS добавить 'its_utils.app_gitpull',
2) в urls добавить
url(r'^its/', include('its_utils.app_gitpull.urls')),
3) Можно добавить в settings настройки
дефолт можно посмотреть app_gitpull/settings.py

####Использование
1) в браузере запускаем http://domain.com/its/gitpull
2) на странице есть кнопка "Дерево коммитов", которая открывает `/its/git/commit_tree/` для просмотра истории текущего репозитория.
