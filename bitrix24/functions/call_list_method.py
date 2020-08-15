# -*- coding: utf-8 -*-
from django.http import JsonResponse
from django.http import JsonResponse
from django.utils import timezone
import six

from ..functions.api_call import DEFAULT_TIMEOUT
from ..functions.batch_api_call3 import BatchResultDict

if not six.PY2:  # type hints
    from typing import Optional, Union, Any, Tuple

if False:  # type hints
    from ..models import BitrixUserToken

ALLOWABLE_TIME = 2000
MICROSECONDS_TO_MILLISECONDS = 1000
# Подавляющее большинство списочных методов возвращает просто список,
# но некоторые оборачивают результат, здесь перечислены такие случаи
METHOD_WRAPPERS = {
    'tasks.task.list': 'tasks',
    'tasks.task.history.list': 'list',
    'tasks.task.getFields': 'fields',
    'tasks.task.getaccess': 'allowedActions',
}

class CallListException(Exception):
    def __init__(self, *args):
        super(CallListException, self).__init__(*args)
        self.error = args[0] if args else None

    def dict(self):
        if isinstance(self.error, dict):
            return self.error
        return dict(error=self.error)

    def json_response(self, status=500):
        json_error_response = JsonResponse(self.dict(), status=status)
        if status >= 500:
            # skip django reports for 5xx responses
            json_error_response._has_been_logged = True
        return json_error_response

def unwrap_batch_res(batch_res, result=None, wrapper=None):
    # type: (BatchResultDict, Union[list, dict], Optional[str]) -> Union[list, dict]
    """
    Собрать результаты batch_api_call в один список
    Может использоваться ка самостоятельный метод

    :param batch_res: результаты batch_api_call
    :param result: список, в который будем добавлять результаты
    :param wrapper: если результат обернут в параметр,
        например 'tasks' у 'tasks.task.list'
    """
    if not batch_res.all_ok:
        # Если встречаем ошибку, возвращаем её
        raise CallListException(batch_res.errors)

    if result is None:
        result = {wrapper: []} if wrapper else []

    # Если не находим ошибку, добавляем результаты вызовов к общему результату
    for part in batch_res.values():  # Проходим по массиву результатов

        # Если тут происходит ошибка, следует обновить METHOD_WRAPPERS
        chunk = part['result'][wrapper] if wrapper else part['result']
        (result[wrapper] if wrapper else result).extend(chunk)

    return result

def call_list_method(
        bx_token,  # type: BitrixUserToken
        method,  # type: str
        fields=None,  # type: Union[dict, list, None]
        limit=None,  # type: Optional[int]
        allowable_error=None,  # type: Optional[int]
        unwrap_batch_res_method=unwrap_batch_res,
        timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
        force_total=None,  # type: Optional[int]
        log_prefix='',
        batch_size=50,  # type: int
        v=0,
):  # type: (...) -> Tuple[Union[list, dict], Optional[str]]
    """
    Выполнить списочный метод битрикс 24

    :param bx_token: объект BitrixUserToken
    :param method: метод
    :param fields: параметры

    :param force_total: максимальное количество объектов, которые нужно получить. Если None, получить все. Должно
                        быть кратно 50

    :param DEPRECATED force_total: максимальное количество объектов, которые нужно получить. Если None, получить все. Должно
                        быть кратно 50

    :param allowable_error: максимальное число, на которое может отличаться длина итогового массива от количества
                            элементов в битриксе на момент начала выполнения запроса

    :param unwrap_batch_res_method: функция для сбора результатов batch_api_call в один список. В большинстве случаев
                                    такие результаты являются словарями вида {"result": [<список объектов>]}, но есть
                                    исключения. Например, метод tasks.task.list

    :param timeout: таймаут запроса NB! таймаут применяется
        к каждому запросу к битриксу, то есть для каждого батч-кусочка
        применяется данный таймаут и общий таймаут может быть кратно больше.

    :param log_prefix: для логера

    :param batch_size: сколько запросов упаковывается в батч (от 1 до 50)

    :param v:

    :return: кортеж (результат или None, ошибка или None)
    """

    if force_total:
        limit = force_total

    assert 1 <= batch_size <= 50, 'check: 1 <= batch_size <= 50'

    # ЕСЛИ ПЕРЕДАНЫ ТОЛКО СПИСОК ID, то тормозит если их мног,
    # в каждый батч метод суем огромынй список, например 5000 айдишников
    # Альтернативное исполнение для таких ситуаций
    if (
        isinstance(fields, dict) and
        isinstance(fields.get('filter'), dict) and
        isinstance(fields['filter'].get('ID'), list) and
        len(fields['filter']) == 1 and
        len(fields) == 1
    ):
        # https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        methods = []
        for x in chunks(fields['filter']['ID'], batch_size):
            params = {'filter': {'ID': x}}
            if fields.get('select'):
                params['select'] = fields.get('select')
            methods.append((method, params))

        batch = bx_token.batch_api_call_v3(methods, timeout=timeout,
                                           chunk_size=batch_size,
                                           log_prefix=log_prefix, halt=1)

        result = unwrap_batch_res_method(batch,
                                         wrapper=METHOD_WRAPPERS.get(method))
        return result, None

    start = timezone.now()
    time_log = ['list method %s' % method, 'function started: %s' % start]
    batch_start = None

    response = bx_token.call_api_method(method, params=fields, timeout=timeout)

    result = unwrap_batch_res_method(BatchResultDict(), response.get('result'),
                                     wrapper=METHOD_WRAPPERS.get(method))
    next_step = response.get('next')
    total = total_param = response.get('total') or 0

    if limit:
        # Если задан параметр limit, получаем наименьшее из двух количество объектов
        total = min(limit, total)

    # Если в запросе получили не весь список, строим batch_call, чтобы получить остальные
    if next_step and total and next_step < total:
        if fields is None:
            fields = {}

        reqs = []
        step = 50
        while next_step < total:
            # Строим список методов для batch call: {"метод": {параметры}, ...}
            new_fields = fields.copy()
            new_fields['start'] = next_step
            reqs.append((method, new_fields))
            next_step += step

        batch_start = timezone.now()
        time_log.append('batch started: %s' % batch_start)

        batch_res = bx_token.batch_api_call_v3(
            methods=reqs, timeout=timeout, log_prefix=log_prefix,
            chunk_size=batch_size, halt=1,  # останавливается на первой ошибке
        )

        # Записать результаты batch_api_call в result
        result = unwrap_batch_res_method(batch_res, result,
                                         wrapper=METHOD_WRAPPERS.get(method))

        batch_finished = timezone.now()
        time_log.append('batch started: %s' % batch_finished)
        time_log.append('time spent for batch: %s seconds' % (batch_finished - batch_start).seconds)

    end = timezone.now()
    time_spent = (end - start).microseconds / MICROSECONDS_TO_MILLISECONDS
    time_log.append('function finished: %s' % end)
    time_log.append('time spent: %s milliseconds' % time_spent)

    if allowable_error is not None and not limit:
        result_length = len(result)
        length_error = abs(result_length - total_param)
        if length_error > allowable_error:

            return None, u'Количество элементов изменилось за время выполнения запроса на %s (допустимо %s)' % (
                length_error, allowable_error
            )

    return result, None