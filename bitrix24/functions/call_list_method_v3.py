import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from integration_utils.bitrix24.constants import (
    REST_V3_DEFAULT_PAGE_SIZE,
    REST_V3_MAX_LIST_PAGES,
)
from integration_utils.bitrix24.functions.api_call import DEFAULT_TIMEOUT

if TYPE_CHECKING:
    from integration_utils.bitrix24.bitrix_token import BaseBitrixToken


class RestV3ResponseError(ValueError):
    """REST 3.0 вернул ответ с неожиданной структурой."""


class RestV3PaginationError(RestV3ResponseError):
    """REST 3.0 вернул ответ, который нельзя безопасно обработать как список."""


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RestV3PaginationError(
            '{} должен быть положительным целым числом, получено {!r}'.format(
                name,
                value,
            )
        )
    return value


def unwrap_rest_v3_result(response: Any) -> Any:
    if not isinstance(response, dict):
        raise RestV3ResponseError(
            'Ответ REST 3.0 должен быть объектом, получено {!r}'.format(
                type(response).__name__,
            )
        )
    if 'result' not in response:
        raise RestV3ResponseError('Ответ REST 3.0 не содержит result')
    return response['result']


def _result_with_items(response: Any) -> Tuple[Dict[str, Any], list]:
    result = unwrap_rest_v3_result(response)

    if not isinstance(result, dict):
        raise RestV3PaginationError(
            'Ответ списочного метода REST 3.0 не содержит объект result'
        )

    items = result.get('items')
    if not isinstance(items, list):
        raise RestV3PaginationError(
            'Ответ списочного метода REST 3.0 не содержит массив result.items'
        )

    return result, items


def _cursor(result: Dict[str, Any]) -> Tuple[bool, Any]:
    """Вернуть признак наличия курсорного поля и сам следующий курсор."""
    if 'nextCursor' in result:
        return True, result['nextCursor']
    if 'afterCursor' in result:
        return True, result['afterCursor']
    return False, None


def _cursor_key(cursor: Any) -> str:
    try:
        return json.dumps(
            cursor,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )
    except (TypeError, ValueError):
        # REST должен вернуть JSON-совместимое значение. repr оставляем
        # запасным вариантом, чтобы диагностика пагинации не упала сама.
        return repr(cursor)


def call_list_method_v3(
    bx_token: 'BaseBitrixToken',
    method: str,
    fields: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    *,
    max_pages: int = REST_V3_MAX_LIST_PAGES,
) -> Tuple[Dict[str, Any], int]:
    """
    Последовательно получить все страницы списочного метода REST 3.0.

    REST 3.0 возвращает элементы в ``result.items``, но использует разные
    способы навигации: курсор ``nextCursor``/``afterCursor`` либо
    ``pagination.limit`` + ``pagination.offset``. Курсоры имеют приоритет,
    поскольку следующая страница при таком способе зависит от предыдущей.

    Возвращает агрегированный ``result`` и количество фактически полученных
    элементов. Переданные ``params`` не изменяет.
    """
    max_pages = _positive_int(max_pages, name='max_pages')

    if fields is None:
        params = {}
    elif isinstance(fields, dict):
        params = deepcopy(fields)
    else:
        raise RestV3PaginationError(f"Параметры REST 3.0 должны быть объектом или null, получено {type(fields).__name__!r}")

    all_items = []
    aggregated_result = None
    seen_cursors = set()

    for _page_number in range(1, max_pages + 1):
        response = bx_token.call_api_method_v3(
            api_method=method,
            params=params,
            timeout=timeout,
        )
        page_result, page_items = _result_with_items(response)

        if aggregated_result is None:
            aggregated_result = deepcopy(page_result)

        all_items.extend(page_items)

        cursor_field_exists, next_cursor = _cursor(page_result)
        has_more = page_result.get('hasMore')

        if has_more is False:
            break

        if cursor_field_exists:
            if next_cursor is None:
                if has_more is True:
                    raise RestV3PaginationError(
                        'REST 3.0 сообщил hasMore=true, но не вернул курсор'
                    )
                break

            cursor_key = _cursor_key(next_cursor)
            if cursor_key in seen_cursors:
                raise RestV3PaginationError(
                    'REST 3.0 повторно вернул тот же курсор пагинации'
                )
            seen_cursors.add(cursor_key)

            pagination = params.get('pagination') or {}
            if not isinstance(pagination, dict):
                raise RestV3PaginationError(
                    'Параметр pagination должен быть объектом'
                )
            pagination = deepcopy(pagination)
            pagination.pop('page', None)
            pagination.pop('offset', None)
            pagination['afterCursor'] = deepcopy(next_cursor)
            params['pagination'] = pagination
            continue

        pagination = params.get('pagination') or {}
        if not isinstance(pagination, dict):
            raise RestV3PaginationError(
                'Параметр pagination должен быть объектом'
            )

        limit = _positive_int(
            pagination.get('limit', REST_V3_DEFAULT_PAGE_SIZE),
            name='pagination.limit',
        )
        if len(page_items) < limit:
            break

        current_offset = pagination.get('offset')
        if current_offset is None:
            page = _positive_int(
                pagination.get('page', 1),
                name='pagination.page',
            )
            current_offset = (page - 1) * limit
        elif isinstance(current_offset, str) and current_offset.isdigit():
            current_offset = int(current_offset)

        if isinstance(current_offset, bool) or not isinstance(current_offset, int) \
                or current_offset < 0:
            raise RestV3PaginationError(
                'pagination.offset должен быть неотрицательным целым числом, '
                'получено {!r}'.format(current_offset)
            )

        pagination = deepcopy(pagination)
        pagination.pop('page', None)
        pagination['offset'] = current_offset + len(page_items)
        params['pagination'] = pagination
    else:
        raise RestV3PaginationError(
            'Превышено максимальное количество страниц REST 3.0: {}'
            .format(max_pages)
        )

    # После полной выгрузки не возвращаем курсор последней обработанной
    # страницы как будто по нему еще можно продолжать обход.
    aggregated_result['items'] = all_items
    if 'hasMore' in aggregated_result:
        aggregated_result['hasMore'] = False
    if 'nextCursor' in aggregated_result:
        aggregated_result['nextCursor'] = None
    if 'afterCursor' in aggregated_result:
        aggregated_result['afterCursor'] = None

    return aggregated_result, len(all_items)
