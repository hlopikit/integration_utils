import time
import urllib
from collections import OrderedDict

import six

from settings import ilogger
from .api_call import (
    api_call,
    convert_params,
    RawStringParam,
    DEFAULT_TIMEOUT,
)
from ..exceptions import JsonDecodeBatchFailed, BatchApiCallError

# typing
if not six.PY2:
    from typing import Union, Optional, List, Sequence, Tuple, Any, Iterable, Dict
if False:
    from ..models import BitrixUserToken


if not six.PY2:
    # Параметры для метода - всегда словарь или None
    ApiParams = Optional[dict]
    # Метод с параметрами - одно из:
    #  - ('user.get', None)
    #  - ('user.get', {'FILTER': {'ACTIVE': 'Y'}})
    ApiMethodAndParams = Tuple[str, ApiParams]

    # Именованый метод с параметрами - одно из:
    #  - ('users', 'user.get', None)
    #  - ('users', 'user.get', {'FILTER': {'ACTIVE': 'Y'}})
    NamedMethodAndParams = Tuple[str, str, ApiParams]

    # Параметр methods как список:
    Methods = Sequence[Union[ApiMethodAndParams, NamedMethodAndParams]]


# лучше показать реплейсы, чем просто отбрасывать непонятные символы
DECODE_ERRORS = 'replace' if six.PY2 else 'backslashreplace'


class BatchResultDict(OrderedDict):
    @property
    def all_ok(self):  # type: () -> bool
        return not any(self.iter_errors())

    def iter_errors(self):  # type: () -> Iterable[Tuple[str, Any]]
        for name, res in self.items():
            if res['error'] is not None:
                yield name, res['error']

    @property
    def errors(self):  # type: () -> Dict[str, Any]
        return OrderedDict(self.iter_errors())

    def iter_successes(self):  # type: () -> Iterable[Tuple[str, Any]]
        for name, res in self.items():
            if res['error'] is None:
                yield name, res

    @property
    def successes(self):  # type: () -> Dict[str, Any]
        return OrderedDict(self.iter_successes())

    def __repr__(self):
        return '{}({}, all_ok={})'.format(
            type(self).__name__,
            dict.__repr__(self),
            self.all_ok,
        )


def convert_methods(methods):
    # type: (List[Tuple[str, str, ApiParams]]) -> List[Tuple[str, RawStringParam]]
    """
    Преобразовать список методов из json в строки, принимаемые методом batch в параметре cmd

    Пример:
    [
        # (название запроса, API-метод, параметры)
        (
            'request1',
            'crm.lead.list',
            {
                'filter': {
                    'ASSIGNED_BY_ID': 42,
                    'STATUS_ID': 1,
                },
            },
        ),
        (
            'request2',
            'crm.deal.list',
            {
                'filter': {
                    'ASSIGNED_BY_ID': 42,
                    'STAGE_ID': 2,
                },
            },
        ),
    ]

    станет:

    [
        ('request1', 'crm.lead.list?filter[ASSIGNED_BY_ID]=42%26filter[STATUS_ID]=1'),
        ('request2', 'crm.deal.list?filter[ASSIGNED_BY_ID]=42%26filter[STAGE_ID]=2'),
    ]

    Сохраняет порядок ключей, если передан OrderedDict
    """

    cmd = []

    for request_name, method, params in methods:
        if params is None:
            params = {}

        # RawStringParam - Параметр, к которому не нужно применять urlquote
        cmd.append((
            request_name,
            RawStringParam('{}?{}'.format(
                method,
                urllib.parse.quote(convert_params(params), safe='[]=')  # квотировать нужно только &
            )),
        ))

    return cmd


def to_chunks(lst, chunk_size=50):
    # type: (list, int) -> List[list]
    """Разрезает список на чанки

    :param lst: любой список
    :param chunk_size: максимальный размер чанка

    :returns: список чанков

    Usage:
        >>> to_chunks([1, 2,3, 4, 5], chunk_size=3)
        [[1, 2, 3], [4, 5]]
    """
    assert chunk_size > 0

    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]


def _batch_api_call(
            methods,  # type: Methods
            bitrix_user_token,  # type: BitrixUserToken
            function_calling_from_bitrix_user_token_think_before_use,
            halt=0,  # type: int
            chunk_size=50,  # type: int
            timeout=DEFAULT_TIMEOUT,  # type: int
            log_prefix='',  # type: str
        ):  # type: (...) -> BatchResultDict
    """Пакетный POST-запрос к Bitrix24 api

    Выполняет все запросы, переданные в methods,
    в несколько итераций по 50 запросов

    Для авторизации используется bitrix_user_token

    :param bitrix_user_token: токен для выполнения запроса

    :param methods: описание методов:
            [
                # Метод без параметров с автоматическим названием data_0
                ('user.get', None),
                # Именованый метод с параметрами
                ('lead', 'crm.lead.get', {'ID': 42}),
                # Метод с параметрами с автоматическим названием data_2
                ('crm.activity.get', {'ID': 42}),
                # Некорректный метод для проверки ошибок
                ('test_error', 'invalid.method', {'foo': 'bar'}),
            ]

    :param timeout: таймаут запроса в секундах
        NB! если токен протух и производится его обновление,
        фактически таймаут может быть в 3 раза больше.
    :param halt: Остановить выполнение дальнейших запросов,
        если в 1 случилась ошибка.
    :param chunk_size: размер чанка, по умолчанию 50 запросов в 1 батче,
        допустимые значения: от 1 до 50

    Есть отличие от batch_api_call, batch_api_call2 - результаты будут в словаре:
         BatchResultDict({
           # Этот метод выполнился без ошибки
           'method1': {'result': {...}, 'error': None},
           # а этот с ошибкой
           'method2': {'result': None: 'error': {...}},
         })
    Сколько бы ни было запросов: 50, 100, 999 - всегда ввернется
    один плоский словарь.

    Также словарь сохраняет последовательность запросов (подкласс OrderedDict)

    :return: объект с результатами, для примера из methods:
        BatchResultDict({
            'data_0': {
                'result': [... первые 50 пользователей ...],
                'error': None,
                'total': 435,  # У списочных методов
                'next': 50,  # У списочных, если не получены все результаты
            },
            'lead': {
                'result': {'ID': '42', ...},
                'error': None,
                'total': None,
                'next': None,
            },
            'data_2': {
                'result': {'ID': '42', ...},
                'error': None,
                'total': None,
                'next': None,
            },
            'test_error': {
                'result': None,
                'error': {'error': 'ERROR_METHOD_NOT_FOUND', ...},
                'total': None,
                'next': None,
            },
        }, all_ok=False)
    """
    if chunk_size < 1 or chunk_size > 50:
        raise ValueError('chunk_size must be within the range [1, 50]')

    webhook = False
    domain = getattr(bitrix_user_token, 'domain', None)
    if not domain:
        domain = bitrix_user_token.user.portal.domain

    if bitrix_user_token.web_hook_auth:
        auth_token = bitrix_user_token.web_hook_auth
        webhook = True

    else:
        app = getattr(bitrix_user_token, 'application', None)
        if app and getattr(app, 'is_webhook', False):
            auth_token = '{}/{}'.format(bitrix_user_token.user.bitrix_id, bitrix_user_token.auth_token)
            webhook = True

        else:
            auth_token = bitrix_user_token.auth_token

    if not methods:
        return BatchResultDict()

    # Добавление автоматических название методов,
    # проверка уникальности названий запросов
    normalized_methods = []
    seen_keys = set()
    i = 0
    for maybe_named_method in methods:
        if len(maybe_named_method) > 2:
            name, method, params = maybe_named_method
        else:
            method, params = maybe_named_method
            name = 'data_%d' % i
        i += 1
        if name in seen_keys:
            raise ValueError('duplicate key: {}'.format(name))
        else:
            seen_keys.add(name)
        normalized_methods.append((name, method, params))
    methods = normalized_methods

    # urlencode всех параметров методов
    converted_requests = convert_methods(methods)
    # Получаем список срезов, по 50 штук
    parts_methods = to_chunks(converted_requests, chunk_size=chunk_size)

    responses = BatchResultDict()  # Список ответов и данных

    def add_response(part_request_names, part_resp):  # type: (List[str], dict) -> None
        # Добавляем запросы в словарь ответов
        res = part_resp['result']
        # Известный косяк php-сериалайсера json:
        # Array(0 => 'foo') становится ['foo']
        # Array() становится []
        # даже если должно быть {"0": "foo"} и {}
        for key in ('result', 'result_error', 'result_time',
                    'result_total', 'result_next'):
            if key not in res:
                # Добавляем отсутствующие ключи
                res[key] = {}
            elif isinstance(res[key], list):
                # Заменяем списки словарями, т.к. это очень неприятный момент
                res[key] = {str(i): v for i, v in enumerate(res[key])}

        for req_name in part_request_names:
            responses[req_name] = dict(
                result=res['result'].get(req_name),
                error=res['result_error'].get(req_name),
                time=res['result_time'].get(req_name),
                total=res['result_total'].get(req_name),
                next=res['result_total'].get(req_name),
            )

    # Берем по chunk_size методов и отправляем запросы
    for part in parts_methods:
        response = api_call(
            domain=domain,
            api_method='batch',
            auth_token=auth_token,
            params={
                'cmd': OrderedDict(part), 'halt': halt
            },
            webhook=webhook,
            timeout=timeout,
        )

        try:
            data = response.json()

            try:
                operating = max([v['operating'] for k,v in data['result']['result_time'].items()])
                operating = max(operating, data['time']['operating'])
                if operating > 300:
                    log_method = ilogger.info if operating < 400 else ilogger.warning
                    log_method('method_operating', '{}, batch({}): {}'.format(
                        domain, ', '.join({m for _, m, _ in normalized_methods}), operating,
                    ))
                    time.sleep(operating-300)
            except:
                pass

        except ValueError:  # response - не json
            # Если апи вернуло ошибку, не связанную с токеном, логируем
            try:
                response_text = response.text
            except UnicodeError:
                response_text = response.content \
                    .decode(response.apparent_encoding, errors=DECODE_ERRORS)
            ilogger.warning(u'%sbitrix_api_error' % log_prefix, response_text)

            # Нет смысла возвращать None, т.к.:
            # - либо вызов проигнорируют и будет оошибка в бизнес-логике
            # - либо будут ожидать словарь и будет TypeError
            raise JsonDecodeBatchFailed(reason=response)

        else:
            error = data.get('error')
            if error == 'expired_token' and bitrix_user_token and \
                    bitrix_user_token.refresh(timeout=timeout):
                # Если обновление токена прошло успешно, повторить запрос
                return _batch_api_call(methods, bitrix_user_token,
                                        function_calling_from_bitrix_user_token_think_before_use=True,
                                        halt=halt,
                                        chunk_size=chunk_size,
                                        timeout=timeout)
            elif error:
                raise BatchApiCallError(reason=response)

            add_response(part_request_names=[name for name, _ in part],
                         part_resp=data)

    return responses
