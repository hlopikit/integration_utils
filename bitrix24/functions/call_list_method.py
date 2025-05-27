# -*- coding: utf-8 -*-
from __future__ import division
from collections import OrderedDict

from django.http import JsonResponse
from django.utils import timezone
import six

from integration_utils.bitrix24.functions.api_call import DEFAULT_TIMEOUT
from integration_utils.bitrix24.functions.batch_api_call import BatchResultDict
from settings import ilogger

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
    'sale.order.list': 'orders',
    'sale.propertyvalue.list': 'propertyValues',
    'sale.basketItem.list': 'basketItems',
    'crm.stagehistory.list': 'items',
    'crm.item.list': 'items',
    'crm.type.list': 'types',
    'crm.item.productrow.list': 'productRows',
    'userfieldconfig.list': 'fields',
    'catalog.catalog.list': 'catalogs',
    'catalog.product.list': 'products',
    'catalog.storeproduct.list': 'storeProducts',
    'catalog.product.offer.list': 'offers',
    'catalog.section.list': 'sections',
    'catalog.productPropertyEnum.list': 'productPropertyEnums',
    'rpa.item.list': 'items',
    'rpa.stage.listForType': 'stages',
    'socialnetwork.api.workgroup.list': 'workgroups',
    'catalog.product.sku.list': 'units',
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


WEIRD_PAGINATION_METHODS = set([
    'task.item.list',
    'task.items.getlist',
    'task.elapseditem.getlist',
])


def next_params(method, params, next_step, page_size=50):
    # type: (str, dict, int, int) -> dict
    """Конструирует параметры для следующего запроса,
    для большинства методов просто устанавливает ?start=next_step,
    для нескольких стремных методов происходит магия:

    например: https://dev.1c-bitrix.ru/rest_help/tasks/task/elapseditem/getlist.php
    """
    if method.lower() not in WEIRD_PAGINATION_METHODS:
        return dict(params, start=next_step)

    # iNumPage, 1 - первая страница (начало), 2 - вторая и т.д.
    # next_step при этом возвращается у первой страницы - 50, у второй 100 и т.д.

    # Таблица преобразования:
    # | next_step | start | iNumPage |
    # | ==== | ===== | ======== |
    # |    0 |     0 |        1 |
    # |   50 |    50 |        2 |
    # |  100 |   100 |        3 |
    # |  150 |   150 |        4 |

    i_num_page = next_step // page_size + 1
    nav_params = OrderedDict([
        ('nPageSize', page_size),
        ('iNumPage', i_num_page),
    ])

    # Убедимся, что работаем с OrderedDict
    if not isinstance(params, OrderedDict):
        params = OrderedDict(params)
    else:
        params = params.copy()

    # Удаляем пагинацию с первого шага
    params.pop('PARAMS', None)

    # Подсчет кол-ва обязательных параметров
    def _count_required_params(optional_params_n=0):
        return len(params) - optional_params_n

    if method.lower() == 'task.item.list':
        # 4 параметра: ORDER, FILTER, PARAMS, SELECT
        if _count_required_params() < 1:
            params['ORDER'] = {}
        if _count_required_params() < 2:
            params['FILTER'] = {}
        # Тут проблемка, что навигация торчит в середине
        if _count_required_params() > 3:
            raise ValueError(
                'Передано слишком много параметров, пожалуйста, ознакомьтесь '
                'с докумментацией https://dev.1c-bitrix.ru/rest_help/tasks/task/item/list.php '
                'и передавайте не более 3 параметров (PARAMS проставляется'
                'автоматически данным методом)'
            )

        # Если передан SELECT, временно его убираем
        select = None
        if _count_required_params() == 3:
            _, select = params.popitem()

        params['PARAMS'] = {'NAV_PARAMS': nav_params}
        if select is not None:  # ставим SELECT после постранички
            params['SELECT'] = select
        return params

    if method.lower() == 'task.items.getlist':
        # 4 параметра: ORDER, FILTER, TASKDATA, NAV_PARAMS
        if _count_required_params() < 1:
            params['ORDER'] = {'ID': 'asc'}
        if _count_required_params() < 2:
            params['FILTER'] = {}
        if _count_required_params() < 3:
            # Ругается на ['*'] почему-то
            params['TASKDATA'] = ['ID', 'TITLE']
        while _count_required_params() > 3:
            params.popitem()

        params['NAV_PARAMS'] = {'NAV_PARAMS': nav_params}
        return params

    assert method.lower() == 'task.elapseditem.getlist', \
        'unknown method %s' % method
    # Убервсратый метод, первый параметр опционален, пример вызова с
    # первым (опциональным) параметром - ID задачи
    # params = OrderedDict([
    #     ('TASKID', 8),
    #     ('ORDER', {'ID': 'ASC'}),
    #     ('FILTER', {}),
    #     ('SELECT', ['*']),
    #     ('PARAMS', {'NAV_PARAMS': {'iNumPage': 2}},)
    # ])
    # Пример вызова без опционального параметра
    # params = OrderedDict([
    #     ('ORDER', {'ID': 'ASC'}),
    #     ('FILTER', {}),
    #     ('SELECT', ['*']),
    #     ('PARAMS', {'NAV_PARAMS': {'iNumPage': 2}},)
    # ])

    # Если первый параметр - строка или число, видимо передан TASKID
    optional_params = 0
    if params and isinstance(next(iter(params.values())), (int, str)):
        optional_params = 1

    # пустые параметры, надо заполнить дефолтными значениями
    if _count_required_params(optional_params) < 1:
        params['ORDER'] = {'ID': 'ASC'}
    if _count_required_params(optional_params) < 2:
        params['FILTER'] = {}
    if _count_required_params(optional_params) < 3:
        params['SELECT'] = ['*']
    while _count_required_params(optional_params) > 3:
        params.popitem()

    params['PARAMS'] = {'NAV_PARAMS': nav_params}
    return params


def check_params(method, params):
    if method.lower() == 'task.ctasks.getlist':
        raise ValueError(
            'Нестандартный коробочный метод %s, не работает в облаке, '
            'не поддерживает пагинацию, пожалуйста воспользуйтесь '
            'нормальным методом, например tasks.task.list' % method)
    if isinstance(params, (list, tuple)):
        params = OrderedDict((str(i), value) for i, value in enumerate(params))
    # if (
    #     # TODO: хорошо бы проверить все методы с позиционными параметрами,
    #     # сейчас проверяются 3 особо странных
    #     method.lower() in WEIRD_PAGINATION_METHODS and
    #     params and
    #     not isinstance(params, OrderedDict)
    # ):
    #     raise ValueError(u'Надо использовать OrderedDict с %s' % method)
    return params


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
        ilogger.warning('deprecated_force_total', 'deprecated_force_total')
        limit = force_total

    if v == 0:
        ilogger.warning('call_list_method_incorrect_using', 'use BitrixUserToken.call_list_method instead')

    assert 1 <= batch_size <= 50, 'check: 1 <= batch_size <= 50'
    fields = check_params(method, fields)

    # ### TODO БЛОК УСЛОВИЯ ВЫНЕСТИ В ФУНКЦИЮ ПОСЛЕ ОТЛАДКИ
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

        batch = bx_token.batch_api_call(methods, timeout=timeout,
                                           chunk_size=batch_size,
                                           log_prefix=log_prefix, halt=1)

        result = unwrap_batch_res_method(batch,
                                         wrapper=METHOD_WRAPPERS.get(method))
        return result
    # ### TODO БЛОК УСЛОВИЯ ВЫНЕСТИ В ФУНКЦИЮ ПОСЛЕ ОТЛАДКИ

    start = timezone.now()
    time_log = ['list method %s' % method, 'function started: %s' % start]
    batch_start = None

    if method.lower() in WEIRD_PAGINATION_METHODS:
        # Есть корнер-кейс при котором надо проставить "странную пагинацию"
        # >>> tok.call_list_method_v2('task.item.List', OrderedDict([
        # ...     ('ORDER', {'ID': 'DESC'}),
        # ...     ('FILTER', {'<=ID': 10000}),
        # ...     ('SELECT', ['ID']), # <- надо зафорсить этот параметр на четвертое место
        # ... ]))
        fields = next_params(method, fields or {}, 0)

    # NB! fields.copy() защищает оригинал от изменения
    # (api_call2 добавляет туда auth)
    response = bx_token.call_api_method(
        method, params=fields and fields.copy(), timeout=timeout,
    )

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

        # fixme: с batch_api_call_v3 можно не нарезать вручную по 50 запросов
        reqs = []
        step = 50
        while next_step < total:
            # Строим список методов для batch call: {"метод": {параметры}, ...}
            new_fields = next_params(method, fields, next_step, page_size=step)
            reqs.append((method, new_fields))
            next_step += step

        batch_start = timezone.now()
        time_log.append('batch started: %s' % batch_start)

        batch_res = bx_token.batch_api_call(
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

    if batch_start and time_spent > ALLOWABLE_TIME:
        # записать время выполнения в лог, если batch_api_call был вызван и выполнялся дольше 2 секунд
        ilogger.info('call_bx_list_method_time_log', '\n'.join(time_log))

    if allowable_error is not None and not limit:
        result_length = len(result)
        length_error = abs(result_length - total_param)
        if length_error > allowable_error:
            ilogger.warning(u'%scall_bx_list_method_length_error' % log_prefix,
                            u'total: %s, result length: %s, allowable_error: %s'
                            % (total_param, result_length, allowable_error))

            raise CallListException(u'Количество элементов изменилось за время выполнения запроса на %s (допустимо %s)' % (
                length_error, allowable_error
            ))

    return result
