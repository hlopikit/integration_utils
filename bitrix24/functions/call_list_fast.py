from __future__ import annotations

from collections.abc import Callable, Iterator
from operator import itemgetter
from typing import Any, TYPE_CHECKING, TypeAlias

from django.conf import settings

from integration_utils.bitrix24.functions.api_call import DEFAULT_TIMEOUT
from integration_utils.bitrix24.exceptions import BatchApiCallError
from .call_list_method import _check_filter_by_id_only, _generate_filter_id_methods_for_batch

if TYPE_CHECKING:
    from integration_utils.bitrix24.functions.batch_api_call import BatchResultDict
    from integration_utils.retry_utils import RetryDecorator
    from ..models import BitrixUserToken


ApiParams: TypeAlias = dict[str, Any]
ApiEntity: TypeAlias = dict[str, Any]
OrderFunction: TypeAlias = Callable[[bool], ApiParams]
FilterFunction: TypeAlias = Callable[[int, int | None, str | None, bool], ApiParams]
EntityIdGetter: TypeAlias = Callable[[ApiEntity], int | str]
CallListFastTimeout: TypeAlias = int | None


def _deep_merge(*dicts: ApiParams) -> ApiParams:
    """Слияние словарей слева на право:
    >>> d1 = {'foo': None, 'bar': {'answer': 42}}
    >>> d2 = {'foo': {'hello': 'world'}, 'bar': {'number': 666}}
    >>> _deep_merge(d1, d2)
    {'foo': {'hello': 'world'}, 'bar': {'answer': 42, 'number': 666}}
    """
    res: ApiParams = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, dict):
                if k in res and not isinstance(res[k], (dict, type(None))):
                    raise ValueError('cannot merge {!r} into {!r}'
                                     .format(v, res[k]))
                res[k] = _deep_merge(res.get(k) or {}, v)
                continue
            res[k] = v
    return res


def simple_order(descending: bool = False) -> ApiParams:
    return {'order': {'ID': 'DESC' if descending else 'ASC'}}


def simple_order_lower(descending: bool = False) -> ApiParams:
    return {'order': {'id': 'DESC' if descending else 'ASC'}}


def voximplant_statistic_order(descending: bool = False) -> ApiParams:
    return {'order': 'DESC' if descending else 'ASC', 'sort': 'ID'}


# Как выглядят параметры сортировки, у большинства: {'order': {'ID': 'DESC'}}
METHOD_TO_ORDER: dict[str, OrderFunction] = {
    'tasks.task.list': simple_order,

    'crm.deal.list': simple_order,
    'crm.lead.list': simple_order,
    'crm.contact.list': simple_order,
    'crm.company.list': simple_order,

    'crm.product.list': simple_order,
    'crm.productrow.list': simple_order,
    'crm.activity.list': simple_order,

    'crm.requisite.list': simple_order,

    'voximplant.statistic.get': voximplant_statistic_order,

    'crm.quote.list': simple_order,

    'crm.item.list': simple_order,
    'lists.element.get': simple_order,
    'crm.invoice.list': simple_order,
    'crm.stagehistory.list': simple_order,

    'user.get': simple_order,

    'catalog.product.list': simple_order,
    'catalog.product.offer.list': simple_order,

    'rpa.item.list': simple_order_lower,

    'lists.section.get': simple_order,

    # TODO:  в этот и прочие словари надо добавлять описания прочих методов,
    #   скорее всего достаточно будет скопировать то что сейчас описано
    #   для crm.deal.list. НО не надо добавлять сюда методы, которые 100%
    #   не работают, например не умеют фильтрацию >ID или <ID
}


def filter_id_upper(
    index: int,
    last_id: int | None = None,
    wrapper: str | None = None,
    descending: bool = False,
) -> ApiParams:
    cmp = '<' if descending else '>'
    prop = cmp + 'ID'
    if index == 0:
        if last_id is not None:
            return {'filter': {prop: last_id}}
        return {}
    path = '$result[req_%d]' % (index - 1)
    if wrapper:
        path += '[%s]' % wrapper
    return {'filter': {prop: '%s[49][ID]' % path}}


def filter_id_lower(
    index: int,
    last_id: int | None = None,
    wrapper: str | None = None,
    descending: bool = False,
) -> ApiParams:
    cmp = '<' if descending else '>'
    prop = cmp + 'id'
    if index == 0:
        if last_id is not None:
            return {'filter': {prop: last_id}}
        return {}
    path = '$result[req_%d]' % (index - 1)
    if wrapper:
        path += '[%s]' % wrapper
    return {'filter': {prop: '%s[49][id]' % path}}


def filter_id_mixed(
    index: int,
    last_id: int | None = None,
    wrapper: str | None = None,
    descending: bool = False,
) -> ApiParams:  # У задач в результате `id`, а в запросе `ID`
    cmp = '<' if descending else '>'
    prop = cmp + 'ID'
    if index == 0:
        if last_id is not None:
            return {'filter': {prop: last_id}}
        return {}
    path = '$result[req_%d]' % (index - 1)
    if wrapper:
        path += '[%s]' % wrapper
    return {'filter': {prop: '%s[49][id]' % path}}


# Как выглядят параметры фильтра, у большинства: {'filter': {'>ID': ...}}
METHOD_TO_FILTER: dict[str, FilterFunction] = {
    'tasks.task.list': filter_id_mixed,

    'crm.deal.list': filter_id_upper,
    'crm.lead.list': filter_id_upper,
    'crm.contact.list': filter_id_upper,
    'crm.company.list': filter_id_upper,

    'crm.product.list': filter_id_upper,
    'crm.productrow.list': filter_id_upper,
    'crm.activity.list': filter_id_upper,

    'crm.requisite.list': filter_id_upper,

    'voximplant.statistic.get': filter_id_upper,

    'crm.quote.list': filter_id_upper,
    'lists.element.get': filter_id_upper,

    'crm.item.list': filter_id_lower,
    'crm.invoice.list': filter_id_upper,
    'crm.stagehistory.list': filter_id_upper,

    'user.get': filter_id_upper,

    'catalog.product.list': filter_id_lower,
    'catalog.product.offer.list': filter_id_lower,

    'rpa.item.list': filter_id_lower,

    'lists.section.get': filter_id_upper,
}


# Получить ID из сущности, у большинства `entity['ID']` или `entity['id']`
METHOD_TO_ID: dict[str, EntityIdGetter] = {
    'tasks.task.list': itemgetter('id'),

    'crm.deal.list': itemgetter('ID'),
    'crm.lead.list': itemgetter('ID'),
    'crm.contact.list': itemgetter('ID'),
    'crm.company.list': itemgetter('ID'),

    'crm.product.list': itemgetter('ID'),
    'crm.productrow.list': itemgetter('ID'),
    'crm.activity.list': itemgetter('ID'),

    'crm.requisite.list': itemgetter('ID'),

    'voximplant.statistic.get': itemgetter('ID'),

    'crm.quote.list': itemgetter('ID'),
    'lists.element.get': itemgetter('ID'),

    'crm.item.list': itemgetter('id'),
    'crm.invoice.list': itemgetter('ID'),
    'crm.stagehistory.list': itemgetter('ID'),

    'user.get': itemgetter('ID'),

    'catalog.product.list': itemgetter('id'),
    'catalog.product.offer.list': itemgetter('id'),

    'rpa.item.list': itemgetter('id'),

    'lists.section.get': itemgetter('ID'),
}


# Большинство методов возвращают просто список, но некоторые
# (в основном у задач) имеют доп. обертку (например resp['result']['tasks'])
METHOD_TO_WRAPPER: dict[str, str] = {
    'tasks.task.list': 'tasks',
    'crm.item.list': 'items',
    'crm.stagehistory.list': 'items',
    'catalog.product.list': 'products',
    'catalog.product.offer.list': 'offers',
    'rpa.item.list': 'items',
}


def is_sql_query_error(batch: BatchResultDict) -> bool:
    return 'sql query error' in list(batch.errors.values())[0]['error_description'].lower()


def is_invalid_filter_error(method: str, batch: BatchResultDict) -> bool:
    return (
            method == 'crm.item.list' and
            'invalid filter' in list(batch.errors.values())[0]['error_description'].lower()
    )


def iter_result_by_filter_ids(
        tok: BitrixUserToken,
        method: str,
        params: ApiParams,
        filter_key: str | None,
        filter_id_key: str,
        filter_ids: list[Any],
        order_by: ApiParams,
        id_fn: EntityIdGetter,
        descending: bool = False,
        wrapper: str | None = None,
        timeout: CallListFastTimeout = DEFAULT_TIMEOUT,
        limit: int | None = None,
        batch_size: int = 50,
        log_prefix: str = '',
        retry_settings: RetryDecorator | None = None,
) -> Iterator[ApiEntity]:
    # Сортируем ID до разбиения на чанки, чтобы сохранить общий порядок результата
    filter_ids = sorted(filter_ids, key=int, reverse=descending)
    fields = _deep_merge(params, order_by)
    methods = _generate_filter_id_methods_for_batch(
        method=method,
        fields=fields,
        filter_key=filter_key,
        filter_id_key=filter_id_key,
        filter_ids=filter_ids,
        batch_size=batch_size,
    )

    batch = tok.batch_api_call(
        methods=methods,
        timeout=timeout,
        chunk_size=batch_size,
        halt=1,
        log_prefix=log_prefix,
        retry_settings=retry_settings,
    )

    if not batch.all_ok:
        raise BatchApiCallError(batch)

    seen_ids: set[int] = set()

    for _, response in batch.iter_successes():
        result = response['result']
        if wrapper is not None:
            result = result[wrapper]

        for entity in result:
            entity_id = int(id_fn(entity))
            if entity_id in seen_ids:
                continue

            seen_ids.add(entity_id)
            yield entity

            if limit is not None and len(seen_ids) >= limit:
                return


def call_list_fast(
    tok: BitrixUserToken,
    method: str,
    params: ApiParams | None = None,
    descending: bool = False,
    log_prefix: str = '',
    timeout: CallListFastTimeout = DEFAULT_TIMEOUT,
    limit: int | None = None,
    batch_size: int = 50,
    retry_settings: RetryDecorator | None = None,
) -> Iterator[ApiEntity]:
    """Быстрое получение списочных записей
    с помощью batch method?start=-1
    https://dev.1c-bitrix.ru/rest_help/rest_sum/start.php

    Производительность на 10к записях контактов CRM ~25 секунд против
    ~60 обычным списочным методом.

    Если записей мало (менее 2500) может оказаться медленнее.

    (Проверено) Работает с методами crm, пока не работает с `tasks.task.*`,
    другие методы не проверял. `tasks.task.list` просто игнорирует start=-1,
    результат возвращется корректный, но ускорения никакого.
    `user.get` игнорирует фильтр >ID и возвращает записи без фильтрации.

    Некоторые методы игнорируют фильтрацию вида `{'>ID': ...}`,
    например `user.get`, так что им этод метод не подойдет.

    TODO: заполнить справочники METHOD_TO_* при использовании прочих методов

    Usage:
        >>> but = BitrixUserToken.objects.filter(is_active=True).first()
        >>> for contact in but.call_list_fast('crm.contact.list'):
        >>>     print(contact['ID'], contact['NAME'], contact['LAST_NAME'])

    Возвращаемое значение (генератор) можно проитерировать (только 1 раз),
    альтернативно можно собрать в список:
        >>> deals = list(but.call_list_fast('crm.deal.list'))
    """
    order_fn = METHOD_TO_ORDER[method]
    filter_fn = METHOD_TO_FILTER[method]
    id_fn = METHOD_TO_ID[method]
    wrapper = METHOD_TO_WRAPPER.get(method)
    assert 1 <= batch_size <= 50
    assert limit is None or limit >= 0

    last_entity_id: int | None = None
    seen_entity_ids: set[int] = set()

    order_by = order_fn(descending)
    if params and any(key in order_by for key in params):
        raise ValueError("Method doesn't support sort/order")

    # Копируем params, так как проверка ID преобразует Iterable в список
    if params is not None:
        params = _deep_merge(params)

    # Фильтр только по ID разбиваем на batch-команды
    filter_key, filter_id_key, filter_ids = _check_filter_by_id_only(params)

    if filter_ids is not None:
        if not filter_ids:
            return

        assert filter_id_key is not None
        yield from iter_result_by_filter_ids(
            tok=tok,
            method=method,
            params={} if params is None else params,
            filter_key=filter_key,
            filter_id_key=filter_id_key,
            filter_ids=filter_ids,
            order_by=order_by,
            id_fn=id_fn,
            descending=descending,
            wrapper=wrapper,
            timeout=timeout,
            limit=limit,
            batch_size=batch_size,
            log_prefix=log_prefix,
            retry_settings=retry_settings,
        )
        return

    while True:
        batch_params = []
        for i in range(batch_size):
            # Необходимые методу параметры: фильтрация, сортировка, ?start=-1
            call_fast_params = _deep_merge(
                order_by,
                filter_fn(i, last_entity_id, wrapper, descending),
                dict(start=-1),
            )

            # Проверка нет ли параметров в разном регистре,
            # например filter и FILTER, из-за них бывают глюки
            check_lower_keys = set(key.lower() for key in call_fast_params)
            if params is not None and any(
                    (key not in call_fast_params and
                     key.lower() in check_lower_keys)
                    for key in params
            ):
                raise ValueError(
                    'Переданные параметры {params!r} могут конфликтовать '
                    'c параметрами метода {call_fast_params!r}. Проверьте, '
                    'чтобы регистр совпадал, например разный регистр filter и '
                    'FILTER вызвал баг на одном из порталов.'.format(**locals())
                )
            batch_params.append((
                'req_%d' % i,
                method,
                _deep_merge({} if params is None else params, call_fast_params),
            ))

        batch = tok.batch_api_call_v3(
            methods=batch_params,
            timeout=timeout,
            log_prefix=log_prefix,
            retry_settings=retry_settings,
        )

        duplicate_count = 0
        max_duplicate_count = getattr(settings, 'CALL_LIST_FAST_MAX_DUPLICATE_COUNT', 10)

        for _, response in batch.iter_successes():
            result = response['result']
            if wrapper is not None:
                result = result[wrapper]
            if not result:
                return

            for entity in result:
                entity_id = int(id_fn(entity))
                if entity_id in seen_entity_ids:
                    if duplicate_count < max_duplicate_count:
                        # https://b24.it-solution.ru/workgroups/group/347/tasks/task/view/50889/
                        # crm.deal.list может вернуть одну сделку дважды. пропускаем первый дублированный элемент
                        duplicate_count += 1
                        continue

                    return  # Если дублей несколько - завершаем выполнение

                if last_entity_id:
                    if (descending and last_entity_id < entity_id) or (not descending and last_entity_id > entity_id):
                        # https://b24.it-solution.ru/workgroups/group/421/tasks/task/view/79144/
                        # фикс на случае, когда в запросе есть фильтр по id
                        return

                yield entity
                seen_entity_ids.add(entity_id)
                last_entity_id = entity_id
                if limit is not None and len(seen_entity_ids) >= limit:
                    return  # Достигли запрошенного лимита
        if not batch.all_ok:
            if is_sql_query_error(batch) or is_invalid_filter_error(method, batch):
                # fixme: количество методов в батче берётся с запасом. voximplant.statistic.get с сортировкой по
                #        убыванию при выходе batch за границы начинает отдавать 'SQL query error'. здесь мы уже
                #        получили все элементы, поэтому можем игнорировать ошибку
                return
            raise BatchApiCallError(batch)
        if not all(
                chunk['result'] and len(
                    chunk['result'][wrapper]
                    if wrapper
                    else chunk['result']
                ) == 50
                for chunk in batch.values()
        ):
            # Вернулся пустой список или менее 50 записей на один из запросов
            return
