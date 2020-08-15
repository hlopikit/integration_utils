import requests
import time

from django.conf import settings
from django.utils.http import urlquote
from django.utils.encoding import force_text


# Таймаут запроса по-умолчанию:
# 1 минута, потому что наш nginx все равно отрубает обработчики после 1 минуты,
# если все-таки нужно выполнить ожидаемо очень долгий запрос,
# например в кроне, можно явно передать большее значение или даже None.
from integration_utils.bitrix24.exceptions import ConnectionToBitrixError, BitrixTimeout, BitrixApiError

DEFAULT_TIMEOUT = 60

class RawStringParam:
    # Параметр, к которому не нужно применять urlquote

    def __init__(self, value):
        self.value = value

    __unicode__ = __str__ = lambda self: self.value
    __repr__ = lambda self: '<RawStringParam %r>' % self.value


def call_with_retries(url, converted_params, retries_on_503=20, sleep_on_503_time=0.5, timeout=DEFAULT_TIMEOUT, files=None):

    response = None

    try:
        response = requests.post(
            url,
            converted_params,
            auth=getattr(settings, 'B24_HTTP_BASIC_AUTH', None),
            timeout=timeout,
            files=files,
        )
    except requests.exceptions.SSLError as e:
        raise ConnectionToBitrixError()
    except requests.Timeout as e:
        raise BitrixTimeout(requests_timeout=e, timeout=timeout)
    except requests.ConnectionError as e:
        raise ConnectionToBitrixError()
    else:
        if response.status_code == 503:
            if retries_on_503 > 0:
                if sleep_on_503_time:
                    time.sleep(sleep_on_503_time)
                return call_with_retries(
                    url=url,
                    converted_params=converted_params,
                    retries_on_503=retries_on_503 - 1,
                    sleep_on_503_time=sleep_on_503_time,
                )
            else:
                raise BitrixApiError(401, 'превышено количество попыток')

    return response

def convert_params(form_data):
    """
    Рекурсивно, с помощью функции recursive_traverse проходит словарь/кортеж/список,
    превращая его в параметры, понятные битриксу.

    Обычный вызов
    >>> convert_params({'field': {'hello': 'world'}})
    'field[hello]=world'

    Вызов со списком
    >>> convert_params([{'field': 'hello'}, {'field': 'world'}])
    '0[field]=hello&1[field]=world'

    Обычный вызов
    >>> convert_params({'auth': 123, 'field': {'hello': 'world'}})
    'auth=123&field[hello]=world'

    Экранирование ключей
    >>> convert_params({'FILTER': {'>=PRICE': 15}})
    'FILTER[%3E%3DPRICE]=15'

    Экранирование значений
    >>> convert_params({'FIELDS': {'POST_TITLE': "[1] + 1 == 11 // true"}})
    'FIELDS[POST_TITLE]=%5B1%5D%20%2B%201%20%3D%3D%2011%20//%20true'

    и т.д.
    """

    def recursive_traverse(values, key=None):

        """
        При первом вызове key ничему не равен, затем к нему будут добавляться новые ключи.
        '' => 'field' => 'field[hello]' => 'field[hello][there]' => ...

        Если values - строка, то возвращается строка вида 'key=values', иначе в список собираются такие же ключи и
        собираются в строку вида 'key=value&key=value' и т.д.
        """

        collection_t = dict, list, tuple,
        list_like_t = list, tuple,

        params = []

        if not isinstance(values, collection_t):
            # Скалярное значение
            values = '' if values is None else values

            if not isinstance(values, RawStringParam):
                # convert int, float, lazy_str to str
                values = urlquote(force_text(values))
            else:
                values = str(values)

            return u'%s=%s' % (key, values)

        if key is not None and isinstance(values, collection_t) and not values:
            # Для некоторых методов обязательно указывать пустые параметры,
            # например https://dev.1c-bitrix.ru/rest_help/tasks/task/item/list.php
            # Из доков:
            #     Однако, если какие-то параметры нужно пропустить,
            #     то их все равно нужно передать, но в виде пустых массивов:
            #     ORDER[]=&FILTER[]=&PARAMS[]=&SELECT[]=
            return u'%s[]=' % key

        # Создание итератора ключей и значений словаря/списка/кортежа
        # (для списка и кортежа ключами становятся индексы)
        if isinstance(values, list_like_t):
            iterable = enumerate(values)
        elif isinstance(values, dict):
            iterable = values.items()
        else:
            raise TypeError(values)

        # Тут проиходит добавление вложенности ключам и рекурсивный вызов
        for inner_key, v in iterable:

            # Кодируется только вложенная часть ключа,
            # т.к. внешняя бывает только при рекурсивном вызове и уже
            # может содержать квадратные скобки, которые мы хотим сохранить
            inner_key = urlquote(force_text(inner_key))

            if key is not None:
                inner_key = u'%s[%s]' % (key, inner_key)

            result = recursive_traverse(v, inner_key)
            if isinstance(result, list):
                params.append(u'&'.join(result))
            else:
                params.append(result)

        return params

    return u'&'.join(recursive_traverse(form_data))


def api_call(api_method, auth_token, params=None, webhook=False, timeout=DEFAULT_TIMEOUT):
    """POST-запрос к Bitrix24 api

    :param api_method: Имя метода (task.item.add)
    :param auth_token: Токен пользователя
    :param params: Словарь параметров. Может содержать просто ключ-значение,
        либо списки, кортежи или опять словари.
        Все это может быть перемешано.
    :param webhook: Метода вызывается через webhook, auth_token в этом случае:
        "{bitrix_id пользователя}/{ключ webhook'а}"
    :param timeout: По умолчанию 60 секунд, если нужно убрать таймаут,
        можно передать None, хотя возможно лучше передать просто большое
        значение, например 30 * 60 (полчаса)

    :rtype: requests.Response
    :returns: Объект ответа библиотеки requests
    """

    if not params:
        params = {}

    hook_key = ''
    if webhook:
        hook_key = '{}/'.format(auth_token)

    else:
        params['auth'] = auth_token

    converted_params = convert_params(params).encode('utf-8')
    url = 'https://{domain}/rest/{hook_key}{api_method}.json'.format(
        domain=settings.APP_SETTINGS.portal_domain, hook_key=hook_key, api_method=api_method
    )

    response = call_with_retries(url, converted_params, timeout=timeout)

    t = time.time()

    return response
