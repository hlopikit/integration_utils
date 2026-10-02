# -*- coding: utf-8 -*-
from __future__ import annotations, division

from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Literal, TYPE_CHECKING, TypeAlias, overload

from django.http import JsonResponse
from django.utils import timezone

from integration_utils.bitrix24.functions.api_call import DEFAULT_TIMEOUT
from integration_utils.bitrix24.functions.batch_api_call import BatchResultDict
from settings import ilogger

if TYPE_CHECKING:
    from ..models import BitrixUserToken
    from integration_utils.retry_utils import RetryDecorator


ALLOWABLE_TIME = 2000
MICROSECONDS_TO_MILLISECONDS = 1000
WEIRD_PAGINATION_METHODS = {
    'task.item.list',
    'task.items.getlist',
    'task.elapseditem.getlist',
}
ALLOWED_PARAMS_FOR_OPTIMIZATION_BY_ID = ('filter', 'select')
FILTER_ID_KEYS = ('id', '@id')

CallListFields: TypeAlias = dict[str, Any] | list[Any] | tuple[Any, ...] | None
CallListResult: TypeAlias = list[Any] | dict[str, Any]
CallListResultWithTotal: TypeAlias = tuple[CallListResult, dict[str, int]]
CallListTimeout: TypeAlias = int | None

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
    def __init__(self, *args: Any) -> None:
        super(CallListException, self).__init__(*args)
        self.error = args[0] if args else None

    def dict(self) -> dict[str, Any]:
        if isinstance(self.error, dict):
            return self.error
        return dict(error=self.error)

    def json_response(self, status: int = 500) -> JsonResponse:
        json_error_response = JsonResponse(self.dict(), status=status)
        if status >= 500:
            # skip django reports for 5xx responses
            json_error_response._has_been_logged = True
        return json_error_response


def unwrap_batch_res(
        batch_res: BatchResultDict,
        result: CallListResult | None = None,
        wrapper: str | None = None,
) -> CallListResult:
    """
    Собрать результаты batch_api_call в один список.
    Может использоваться ка самостоятельный метод.

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


def _check_filter_by_id_only(params: Any) -> tuple[str | None, str | None, list[Any] | None]:
    """
    Проверяет, можно ли разбить переданный список ID на batch-команды.

    Для ключа, который заканчивается на ID и не начинается с !,
    пустой Iterable возвращается как пустой список, чтобы не выполнять API-запрос.
    """
    if not isinstance(params, dict):
        return None, None, None

    filter_key = next((key for key in params if key.lower() == 'filter'), None)
    # Если filter_key нет, проверяем методы с ID на верхнем уровне параметров, например department.get: {'ID': [...]}
    filter_params = params[filter_key] if filter_key else params

    if not isinstance(filter_params, dict):
        return filter_key, None, None

    allowed_params = ALLOWED_PARAMS_FOR_OPTIMIZATION_BY_ID if filter_key else FILTER_ID_KEYS + ('select',)
    allowed_filter_fields = FILTER_ID_KEYS if filter_key else allowed_params
    can_optimize_by_id = all(key.lower() in allowed_params for key in params)
    filter_id_key = None
    filter_ids = None
    excluded_iterable_types = (str, bytes, bytearray, Mapping)

    for filter_field, filter_value in filter_params.items():
        filter_field_lower = filter_field.lower()
        can_optimize_by_id = can_optimize_by_id and filter_field_lower in allowed_filter_fields

        if not filter_field_lower.endswith('id'):
            continue

        if not (isinstance(filter_value, Iterable)
                and not isinstance(filter_value, excluded_iterable_types)):
            continue

        # Преобразуем Iterable в список, чтобы не передать в API уже пройденный генератор
        filter_value = filter_value if isinstance(filter_value, list) else list(filter_value)
        filter_params[filter_field] = filter_value

        if filter_field_lower.endswith('id') and not filter_field_lower.startswith('!') and not filter_value:
            return filter_key, filter_field, []

        if filter_field_lower in FILTER_ID_KEYS:
            filter_id_key = filter_field
            filter_ids = filter_value

    if filter_ids and not can_optimize_by_id:
        filter_ids = None

    return filter_key, filter_id_key, filter_ids


def _generate_filter_id_methods_for_batch(
        method: str,
        fields: dict[str, Any],
        filter_key: str | None,
        filter_id_key: str,
        filter_ids: list[Any],
        batch_size: int,
) -> list[tuple[str, dict[str, Any]]]:
    methods = []
    # Через OrderedDict делаем дедупликацию для сохранения порядка
    unique_filter_ids = list(OrderedDict.fromkeys(filter_ids))

    for start in range(0, len(unique_filter_ids), batch_size):
        filter_id_chunk = unique_filter_ids[start:start + batch_size]
        params = fields.copy()

        if filter_key:
            # Для стандартного формата меняем только список ID внутри filter, остальные разрешенные параметры, например select, сохраняем
            filter_params = params[filter_key].copy()
            filter_params[filter_id_key] = filter_id_chunk
            params[filter_key] = filter_params
        else:
            # Для методов с ID на верхнем уровне чанкуем само поле ID/id/@ID.
            params[filter_id_key] = filter_id_chunk

        # При запросе по списку ID total не нужен, поэтому отключаем его подсчёт через start=-1
        params['start'] = -1
        methods.append((method, params))

    return methods


def next_params(
        method: str,
        params: dict[str, Any],
        next_step: int,
        page_size: int = 50,
) -> dict[str, Any]:
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
    def _count_required_params(optional_params_n: int = 0) -> int:
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
                'с документацией https://dev.1c-bitrix.ru/rest_help/tasks/task/item/list.php '
                'и передавайте не более 3 параметров (PARAMS проставляется'
                'автоматически данным методом)'
            )

        # Если передан SELECT, временно его убираем
        select = None
        if _count_required_params() == 3:
            _, select = params.popitem()

        params['PARAMS'] = {'NAV_PARAMS': nav_params}
        if select is not None:  # ставим SELECT после NAV_PARAMS
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


def check_params(method: str, params: CallListFields) -> CallListFields:
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


@overload
def call_list_method(
        bx_token: BitrixUserToken,
        method: str,
        fields: CallListFields = None,
        limit: int | None = None,
        return_total: Literal[False] = False,
        allowable_error: int | None = None,
        unwrap_batch_res_method: Callable[..., CallListResult] = unwrap_batch_res,
        timeout: CallListTimeout = DEFAULT_TIMEOUT,
        force_total: int | None = None,
        log_prefix: str = '',
        batch_size: int = 50,
        retry_settings: RetryDecorator | None = None,
        v: int = 0,
) -> CallListResult:
    ...


@overload
def call_list_method(
        bx_token: BitrixUserToken,
        method: str,
        fields: CallListFields = None,
        limit: int | None = None,
        return_total: Literal[True] = True,
        allowable_error: int | None = None,
        unwrap_batch_res_method: Callable[..., CallListResult] = unwrap_batch_res,
        timeout: CallListTimeout = DEFAULT_TIMEOUT,
        force_total: int | None = None,
        log_prefix: str = '',
        batch_size: int = 50,
        retry_settings: RetryDecorator | None = None,
        v: int = 0,
) -> CallListResultWithTotal:
    ...


@overload
def call_list_method(
        bx_token: BitrixUserToken,
        method: str,
        fields: CallListFields = None,
        limit: int | None = None,
        return_total: bool = False,
        allowable_error: int | None = None,
        unwrap_batch_res_method: Callable[..., CallListResult] = unwrap_batch_res,
        timeout: CallListTimeout = DEFAULT_TIMEOUT,
        force_total: int | None = None,
        log_prefix: str = '',
        batch_size: int = 50,
        retry_settings: RetryDecorator | None = None,
        v: int = 0,
) -> CallListResult | CallListResultWithTotal:
    ...


def call_list_method(
        bx_token: BitrixUserToken,
        method: str,
        fields: CallListFields = None,
        limit: int | None = None,
        return_total: bool = False,
        allowable_error: int | None = None,
        unwrap_batch_res_method: Callable[..., CallListResult] = unwrap_batch_res,
        timeout: CallListTimeout = DEFAULT_TIMEOUT,
        force_total: int | None = None,
        log_prefix: str = '',
        batch_size: int = 50,
        retry_settings: RetryDecorator | None = None,
        v: int = 0,
) -> CallListResult | CallListResultWithTotal:
    """
    Выполнить списочный метод битрикс 24

    :param bx_token: объект BitrixUserToken
    :param method: метод
    :param fields: параметры

    :param limit: максимальное количество объектов, которые нужно получить.
                  Если None, получить все. Должно быть кратно 50

    :param return_total: если True, дополнительно возвращает словарь с `total` по полной выборке Bitrix24,
                         даже если результат был ограничен параметром `limit`

    :param DEPRECATED force_total: максимальное количество объектов, которые нужно получить.
                                   Если None, получить все. Должно быть кратно 50

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

    :param retry_settings: настройки повторных попыток для REST-запросов

    :param v:

    :return: старый результат либо кортеж `(результат, {"total": <полное количество>})`, если `return_total=True`
    """

    if force_total:
        ilogger.warning('deprecated_force_total', 'deprecated_force_total')
        limit = force_total

    if v == 0:
        ilogger.warning('call_list_method_incorrect_using', 'use BitrixUserToken.call_list_method instead')

    assert 1 <= batch_size <= 50, 'check: 1 <= batch_size <= 50'
    fields = check_params(method, fields)

    # Копируем params, так как проверка ID преобразует Iterable в список
    if isinstance(fields, dict):
        fields = fields.copy()
        filter_key = next((key for key in fields if key.lower() == 'filter'), None)
        if filter_key and isinstance(fields[filter_key], dict):
            fields[filter_key] = fields[filter_key].copy()

    filter_key, filter_id_key, filter_ids = _check_filter_by_id_only(fields)

    if filter_ids is not None:
        if not filter_ids:
            result = {METHOD_WRAPPERS[method]: []} if method in METHOD_WRAPPERS else []
            if return_total:
                return result, {"total": 0}
            return result

        assert isinstance(fields, dict)
        assert filter_id_key is not None
        methods = _generate_filter_id_methods_for_batch(
            method=method,
            fields=fields,
            filter_key=filter_key,
            filter_id_key=filter_id_key,
            filter_ids=filter_ids,
            batch_size=batch_size,
        )

        batch = bx_token.batch_api_call(methods, timeout=timeout, chunk_size=batch_size,
                                        log_prefix=log_prefix, halt=1,
                                        retry_settings=retry_settings)

        wrapper = METHOD_WRAPPERS.get(method)
        result = unwrap_batch_res_method(batch, wrapper=wrapper)
        result_items = result[wrapper] if wrapper else result
        total = len(result_items)

        if limit is not None:
            del result_items[limit:]

        if return_total:
            return result, {"total": total}

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
        api_method=method,
        params=fields and fields.copy(),
        timeout=timeout,
        retry_settings=retry_settings,
    )

    result = unwrap_batch_res_method(BatchResultDict(), response.get('result'), wrapper=METHOD_WRAPPERS.get(method))

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
            methods=reqs,
            timeout=timeout,
            log_prefix=log_prefix,
            chunk_size=batch_size,
            halt=1,  # останавливается на первой ошибке
            retry_settings=retry_settings,
        )

        # Записать результаты batch_api_call в result
        result = unwrap_batch_res_method(batch_res, result, wrapper=METHOD_WRAPPERS.get(method))

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

    if return_total:
        return result, {"total": total_param or len(result)}

    return result
