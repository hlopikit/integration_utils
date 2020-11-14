# coding=utf8
import json
import functools
from json.decoder import JSONDecodeError

from django.http import JsonResponse


# Декоратор который помогает собрать типовые входящие параметры
# Приоритет такой GET -> POST -> request.body
# какие бонусы это дает
# Меньше кода, можно тестирвовать из гет строки в браузере
# получить параметры можно из request.its_params.get(НАЗВАНИЕПАРАМЕТРА)

def get_params_from_sources(function):
    @functools.wraps(function)
    def _f(request, *args, **kwargs):
        try:
            params = json.loads(request.body.decode('utf-8'))
        except ValueError:
            params = {}
        else:
            if params is None:
                # Обработка случая json.loads('null') is None
                params = {}
            elif not isinstance(params, dict):
                # Обработка случаев:
                # json.loads('[1, 2, 3]') == [1, 2, 3]
                # json.loads('1') == 1
                # json.loads('"foobar"') == 'foobar'
                # и пр.
                t = type(params).__name__
                return JsonResponse(dict(
                    error='bad request, expected json object got %s' % t,
                ), status=400)

        for key, value in request.POST.items():
            try:
                params[key] = json.loads(value)
            except JSONDecodeError:
                params[key] = value

        for key, value in request.GET.items():
            try:
                params[key] = json.loads(value)
            except JSONDecodeError:
                params[key] = value

        request.its_params = params
        return function(request, *args, **kwargs)

    return _f
