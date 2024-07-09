from operator import itemgetter

import six
from django.conf import settings

from settings import ilogger
from integration_utils.bitrix24.functions.api_call import DEFAULT_TIMEOUT
from integration_utils.bitrix24.exceptions import BatchApiCallError

if not six.PY2:
    from typing import Optional, Iterable, Any, Hashable, Dict, Callable, TYPE_CHECKING
    if TYPE_CHECKING:
        from ..models import BitrixUserToken


def _deep_merge(*dicts):  # type: (*dict) -> dict
    """Слияние словарей слева на право:
    >>> d1 = {'foo': None, 'bar': {'baz': 42}}
    >>> d2 = {'foo': {'hello': 'world'}, 'bar': {'quux': 666}}
    >>> _deep_merge(d1, d2)
    {'foo': {'hello': 'world'}, 'bar': {'baz': 42, 'quux': 666}}
    """
    res = {}
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


def simple_order(descending=False):
    return {'order': {'ID': 'DESC' if descending else 'ASC'}}


def simple_order_lower(descending=False):
    return {'order': {'id': 'DESC' if descending else 'ASC'}}


def voximplant_statistic_order(descending=False):
    return {'order': 'DESC' if descending else 'ASC', 'sort': 'ID'}


# Как выглядят параметры сортировки, у большинства: {'order': {'ID': 'DESC'}}
METHOD_TO_ORDER = {
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

    # TODO:  в этот и прочие словари надо добавлять описания прочих методов,
    #   скорее всего достаточно будет скопировать то что сейчас описано
    #   для crm.deal.list. НО не надо добавлять сюда методы, которые 100%
    #   не работают, например не умеют фильтрацию >ID или <ID
}


def filter_id_upper(
    index,  # type: int
    last_id=None,  # type: Optional[int]
    wrapper=None,  # type: Optional[str]
    descending=False,
):
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
    index,  # type: int
    last_id=None,  # type: Optional[int]
    wrapper=None,  # type: Optional[str]
    descending=False,
):
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
    index,  # type: int
    last_id=None,  # type: Optional[int]
    wrapper=None,  # type: Optional[str]
    descending=False,
):  # У задач в результате `id`, а в запросе `ID`
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
METHOD_TO_FILTER = {
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
}


# Получить ID из сущности, у большинства `entity['ID']` или `entity['id']`
METHOD_TO_ID = {
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
}


# Большинство методов возвращают просто список, но некоторые
# (в основном у задач) имеют доп. обертку (например resp['result']['tasks'])
METHOD_TO_WRAPPER = {
    'tasks.task.list': 'tasks',
    'crm.item.list': 'items',
    'crm.stagehistory.list': 'items',
    'catalog.product.list': 'products',
    'catalog.product.offer.list': 'offers',
    'rpa.item.list': 'items',
}


def is_sql_query_error(batch):
    return 'sql query error' in list(batch.errors.values())[0]['error_description'].lower()


def is_invalid_filter_error(method, batch):
    return (
            method == 'crm.item.list' and
            'invalid filter' in list(batch.errors.values())[0]['error_description'].lower()
    )


def call_list_fast(
    tok,  # type: BitrixUserToken
    method,  # type: str
    params=None,  # type: Dict[str, Any]
    descending=False,  # type: bool
    log_prefix='',  # type: str
    timeout=DEFAULT_TIMEOUT,  # type: Optional[int]
    limit=None,  # type: Optional[int]
    batch_size=50,  # type: int
):  # type: (...) -> Iterable[Any]
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
    order_fn = METHOD_TO_ORDER[method]  # type: Callable[[bool], Dict[str, Any]]
    filter_fn = METHOD_TO_FILTER[method]  # type: Callable[[int, Optional[int], Optional[str], bool], Dict[str, Any]]
    id_fn = METHOD_TO_ID[method]  # type: Callable[[Any], Hashable]
    wrapper = METHOD_TO_WRAPPER.get(method)  # type: Optional[str]
    assert 1 <= batch_size <= 50
    assert limit is None or limit >= 0

    last_entity_id = None
    seen_ids = set()

    order_by = order_fn(descending)
    if params and any(key in order_by for key in params):
        raise ValueError("Method doesn't support sort/order")

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
        batch = tok.batch_api_call_v3(batch_params,
                                      timeout=timeout, log_prefix=log_prefix)

        duplicate_count = 0
        max_duplicate_count = getattr(settings, 'CALL_LIST_FAST_MAX_DUPLICATE_COUNT', 10)
        for _, response in batch.iter_successes():
            result = response['result']
            if wrapper is not None:
                result = result[wrapper]
            # ilogger.debug('fast_batch_debug', "результат ".format(', '.join(id_fn(x) for x in result)))

            if not result:
                return

            for entity in result:
                id = int(id_fn(entity))
                if id in seen_ids:
                    if duplicate_count < max_duplicate_count:
                        # https://b24.it-solution.ru/workgroups/group/347/tasks/task/view/50889/
                        # crm.deal.list может вернуть одну сделку дважды. пропускаем первый дублированный элемент
                        duplicate_count += 1
                        continue

                    return  # Если дублей несколько - завершаем выполнение

                if last_entity_id:
                    if (descending and last_entity_id < id) or (not descending and last_entity_id > id):
                        # https://b24.it-solution.ru/workgroups/group/421/tasks/task/view/79144/
                        # фикс на случае, когда в запросе есть фильтр по id
                        return

                yield entity
                seen_ids.add(id)
                last_entity_id = id
                if limit is not None and len(seen_ids) >= limit:
                    return  # Достигли запрошенного лимита
        if not batch.all_ok:
            if is_sql_query_error(batch) or is_invalid_filter_error(method, batch):
                # fixme: количество методов в батче берётся с запасом. voximplant.statistic.get с сортировкой по
                #        убыванию при выходе батча за границы начинает отдавать 'SQL query error'. здесь мы уже
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
