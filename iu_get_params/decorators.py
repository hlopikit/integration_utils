# -*- coding: utf-8 -*-
import functools
import json
import math
import re
import types
from collections.abc import Mapping, Sequence
from copy import deepcopy
from inspect import Parameter, signature
from typing import Any, Callable, Literal, Optional, Type, TypeVar, Tuple, Union, cast, get_args, get_origin, get_type_hints, overload

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseBadRequest

from .functions import bool_param, nullable_bool_param, json_error_response


__all__ = [
    "expect_flag",
    "expect_flag_api",
    "expect_param",
    "expect_param_api",
    "expect_typed_params",
]


ParamType = TypeVar('ParamType')
View = Callable[..., HttpResponse]
ApiView = Callable[..., JsonResponse]
CoerceFn = Union[Type[ParamType], Callable[[Any], ParamType]]
CoercePair = Tuple[CoerceFn, str]
StructureHook = Callable[[Any, Any], Any]


class _MissingType:
    """Sentinel type for values that are intentionally not provided."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _MissingType()

@overload
def expect_typed_params(*, source: str = 'its_params', api: Literal[False] = False) -> Callable[[View], View]: ...

@overload
def expect_typed_params(*, source: str = 'its_params', api: Literal[True]) -> Callable[[ApiView], ApiView]: ...

def expect_typed_params(*, source: str = 'its_params', api: bool = False) -> Callable[[...], Union[ApiView, View]]:
    """Привести аннотированные аргументы view через cattrs.

    Аргументы, переданные Django позиционно или по имени, тоже преобразуются.
    ``request`` и параметры без аннотации не обрабатываются.
    Аннотированные positional-only параметры не поддерживаются. Значение по
    умолчанию используется только при отсутствии ключа; явный null допустим
    лишь для Optional/Union с None (или Any). Ошибки возвращаются с HTTP 400;
    при ``api=True`` тело ответа имеет вид ``{"error": "..."}``.

    Декоратор ставится под ``@get_params_from_sources`` для ``its_params``::

        @get_params_from_sources
        @expect_typed_params(api=True)
        def save_items(request, items: list[dict[str, int]], page: int = 0):
            ...
    """
    try:
        # Импортируем cattrs внутри декоратора, чтобы не сломались старые декораторы при отсутствии cattrs.
        from cattrs import Converter, transform_error
        from cattrs.cols import list_structure_factory, mapping_structure_factory
        from cattrs.errors import BaseValidationError
    except ImportError as import_error:
        raise ImportError(
            'expect_typed_params requires cattrs>=24.1.0'
        ) from import_error

    def decorator(view: View) -> View:
        converter = Converter()
        view_signature = signature(view)

        def structure_str(value: Any, _: Type[str]) -> str:
            if type(value) not in (str, int, float):
                raise TypeError('expected str or number')
            return str(value)

        def structure_int(value: Any, _: Type[int]) -> int:
            if type(value) is int:
                return value

            if type(value) is float and value.is_integer():
                return int(value)

            if isinstance(value, str) and re.fullmatch(r'[+-]?[0-9]+(?:\.0+)?', value):
                return int(value.partition('.')[0])

            raise ValueError('expected int without a fractional part')

        def structure_float(value: Any, _: Type[float]) -> float:
            if type(value) not in (int, float, str):
                raise TypeError('expected float')

            invalid_float_format = isinstance(value, str) and (value != value.strip() or '_' in value)

            if invalid_float_format:
                raise TypeError('expected float')

            structured_value = float(value)

            if not math.isfinite(structured_value):
                raise ValueError('expected finite float')

            return structured_value

        def structure_bool(value: Any, _: Type[bool]) -> bool:
            if type(value) not in (bool, int, float, str):
                raise TypeError('expected bool')
            return bool_param(value)

        def structure_none(value: Any, _: Type[None]) -> None:
            if value is not None:
                raise TypeError('expected null')
            return None

        def literal_structure_factory(literal_type: Any) -> StructureHook:
            literal_values = get_args(literal_type)

            def structure_literal(value: Any, _: Any) -> Any:
                value_matches_literal = any(
                    type(value) is type(literal_value) and value == literal_value
                    for literal_value in literal_values
                )

                if not value_matches_literal:
                    raise ValueError(f'{value!r} is not a valid {literal_type}')

                return value

            return structure_literal

        def strict_list_structure_factory(list_type: Any, current_converter: Converter) -> StructureHook:
            structure_list_items = list_structure_factory(list_type, current_converter)

            def structure_list_strict(value: Any, target_type: Any) -> list[Any]:
                value_is_list_like = isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview))

                if not value_is_list_like:
                    raise TypeError('expected a list-like sequence')

                return structure_list_items(value, target_type)

            return structure_list_strict

        def strict_dict_structure_factory(dict_type: Any, current_converter: Converter) -> StructureHook:
            structure_dict_items = mapping_structure_factory(dict_type, current_converter)

            def structure_dict_strict(value: Any, target_type: Any) -> dict[Any, Any]:
                if not isinstance(value, Mapping):
                    raise TypeError('expected mapping')

                return structure_dict_items(value, target_type)

            return structure_dict_strict

        def is_literal_type(candidate_type: Any) -> bool:
            candidate_origin =  get_origin(candidate_type)
            return candidate_origin is Literal

        def is_list_type(candidate_type: Any) -> bool:
            candidate_origin =  get_origin(candidate_type)
            return candidate_origin is list

        def is_dict_type(candidate_type: Any) -> bool:
            candidate_origin =  get_origin(candidate_type)
            return candidate_origin is dict

        # Вычисляем один раз, чтобы не вычислять при каждом использовании is_union_type
        native_union_type = getattr(types, 'UnionType', None)

        def is_union_type(candidate_type: Any) -> bool:
            candidate_origin = get_origin(candidate_type)
            return candidate_origin is Union or (
                native_union_type is not None
                and candidate_origin is native_union_type
            )

        def union_member_match_priority(value: Any, member_type: Any) -> int:
            """
            Вычисляем приоритет типа, входящего в Union.
            От этого зависит, в какой тип будем структурировать value.
            0 - тип value не соответствует member_type.
            1 - тип value является экземпляром member_type или его наследника.
            2 - тип value равен member_type.
            """
            if member_type is Any:
                return 0

            member_origin = get_origin(member_type)

            # Для Literal должны одновременно совпасть значение и его тип: True не равен Literal[1].
            if member_origin is Literal:
                value_matches_literal = any(
                    type(value) is type(literal_value) and value == literal_value
                    for literal_value in get_args(member_type)
                )
                return 2 if value_matches_literal else 0

            runtime_type = member_origin or member_type

            try:
                if type(value) is runtime_type:
                    return 2
                if isinstance(value, runtime_type):
                    return 1
            except TypeError:
                # Не у каждой typing-аннотации есть runtime-тип для проверки через isinstance.
                pass

            return 0

        def union_structure_factory(union_type: Any, current_converter: Converter) -> StructureHook:
            # Получаем member_hooks один раз при создании декоратора, а не на каждом запросе.
            # В данном случае под member имеются в виду типы внутри Union[].
            member_hooks = [
                (member_type, current_converter.get_structure_hook(member_type))
                for member_type in get_args(union_type)
            ]

            def structure_union(value: Any, _: Any) -> Any:
                # Сортируем member_hooks по их приоритету (близости value к member_type).
                prioritized_member_hooks = sorted(
                    (
                        (
                            union_member_match_priority(value, member_type),
                            member_type,
                            member_structure_hook,
                        )
                        for member_type, member_structure_hook in member_hooks
                    ),
                    key=lambda member_hook: member_hook[0],
                    reverse=True,
                )

                matching_structure_error = None

                # Пытаемся структурировать value через member_hooks в порядке их приоритета.
                for match_priority, member_type, member_structure_hook in prioritized_member_hooks:
                    try:
                        return member_structure_hook(value, member_type)
                    except (BaseValidationError, TypeError, ValueError, OverflowError) as structure_error:
                        if match_priority > 0 and matching_structure_error is None:
                            # Сохраняем ошибку приоритетного member_hook.
                            matching_structure_error = structure_error

                if matching_structure_error is not None:
                    raise matching_structure_error

                # Ни один member_type не совпал с value (приоритет у всех был 0).
                raise ValueError(f'{value!r} does not match any type in {union_type}')

            return structure_union

        converter.register_structure_hook(str, structure_str)
        converter.register_structure_hook(int, structure_int)
        converter.register_structure_hook(float, structure_float)
        converter.register_structure_hook(bool, structure_bool)
        converter.register_structure_hook(type(None), structure_none)
        converter.register_structure_hook_factory(is_literal_type, literal_structure_factory)
        converter.register_structure_hook_factory(is_list_type, strict_list_structure_factory)
        converter.register_structure_hook_factory(is_dict_type, strict_dict_structure_factory)
        converter.register_structure_hook_factory(is_union_type, union_structure_factory)

        typed_params = []
        type_hints = get_type_hints(view, include_extras=True)

        # Берём типизированные параметры из сигнатуры view
        for signature_param_name, signature_param in view_signature.parameters.items():
            param_is_request = signature_param_name == 'request'
            param_is_untyped = signature_param_name not in type_hints

            if param_is_request or param_is_untyped:
                continue

            if signature_param.kind is Parameter.POSITIONAL_ONLY:
                raise TypeError(
                    'expect_typed_params does not support positional-only '
                    f'parameter {signature_param_name!r}'
                )

            param_is_variadic = signature_param.kind in (
                Parameter.VAR_POSITIONAL,
                Parameter.VAR_KEYWORD,
            )

            if param_is_variadic:
                continue

            signature_param_type = type_hints[signature_param_name]
            signature_param_structure_hook = converter.get_structure_hook(signature_param_type)

            if signature_param.default is Parameter.empty:
                # Не указан default в параметрах view.
                signature_param_default = MISSING
            else:
                # Указан default в параметрах view.
                # Проверяем через structure_hook, что default подходит под type.
                signature_param_default = signature_param_structure_hook(signature_param.default, signature_param_type)

            typed_params.append((
                signature_param_name,
                signature_param_type,
                signature_param_structure_hook,
                signature_param_default,
            ))

        error_response = json_error_response if api else HttpResponseBadRequest

        @functools.wraps(view)
        def decorated_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            source_params = getattr(request, source)
            bound_arguments = view_signature.bind_partial(request, *args, **kwargs)

            for param_name, param_type, param_structure_hook, param_default in typed_params:
                if param_name in bound_arguments.arguments:
                    raw_value = bound_arguments.arguments[param_name]
                elif param_name not in source_params:
                    if param_default is MISSING:
                        return error_response(f'missing required {param_name} param')
                    bound_arguments.arguments[param_name] = deepcopy(param_default)
                    continue
                else:
                    raw_value = source_params[param_name]
                    if source in ('GET', 'POST') and isinstance(raw_value, str):
                        try:
                            # Проверяем raw_value на наличие JSON-строки
                            raw_value = json.loads(raw_value)
                        except json.JSONDecodeError:
                            pass
                try:
                    # Преобразуем и входные параметры, и аргументы самого вызова view
                    param_value = param_structure_hook(raw_value, param_type)
                except (BaseValidationError, TypeError, ValueError, OverflowError) as structure_error:
                    error_messages = []

                    for error_message in transform_error(structure_error):
                        description, path_separator, path = error_message.rpartition(' @ $')

                        if path_separator:
                            error_messages.append(f'{param_name}{path}: {description}')
                        else:
                            error_messages.append(f'{param_name}: {error_message}')

                    return error_response('; '.join(error_messages))

                bound_arguments.arguments[param_name] = param_value

            return view(*bound_arguments.args, **bound_arguments.kwargs)

        return decorated_view

    return decorator


def expect_param(
        param,  # type: str
        from_='its_params',  # type: str
        coerce=None,  # type: Union[CoerceFn, CoercePair, None]
        default=MISSING,  # type: Optional[ParamType]
        as_=None,  # type: Optional[str]
        err=HttpResponseBadRequest,  # type: Callable[[str], HttpResponse]
):  # type: (...) -> Callable[[View], View]
    """Декоратор для быстрого описания входных параметров

    Принцип тот же, что и в click https://click.palletsprojects.com/
    один входящий параметр - 1 декоратор.

    Usage:
        # Пример вьюхи создания статьи.
        # По умолчанию параметры берутся из request.its_params,
        # так что первым идет декоратор get_params_from_sources
        @get_params_from_sources
        # Обязательный заголовок
        @expect_param('title', coerce=str)
        # Необязательное тело статьи
        @expect_param('body', coerce=str, default='')
        # Обязательный тип статьи
        @expect_param('type_id', coerce=int_param)
        # Необязательный id раздела
        @expect_param('directory_id', coerce=int_or(None), default=None)
        # Необязательный флаг
        @expect_flag_api('important', default=False)
        # Все параметры попадают в **kwargs view-функции
        def create_article(request, *, **kwargs):
            article = Article(**kwargs)
            article.save()
            return redirect('view_article', kwargs=dict(id=article.id))
        # Зачастую лучше записать аргументы явно через запятую
        def create_article(request, *, title, body, author_id,
                           directory_id, important):
            article = Article(title=title, body=body, ...)
            article.save()
            return redirect('view_article', kwargs=dict(id=article.id))

        # В случае если любой из обязательных параметров отсутствует
        # или при ошибках приведения типа (допустим ?directory_id=not-an-int)
        # вернется err (по умолчанию HttpResponseBadRequest) с описанием ошибки

    :param param: str - параметр
    :param from_: str - откуда брать: 'its_params', 'GET', 'POST'
    :param coerce: coerce_fn or (coerce_fn, str) - Приведение к нужному типу,
        пример значений:
        - app_get_params.functions.int_param
        - str
        - (MyClass, MyClass.__name__)
        При ValueError/TypeError возвращается err
        При передаче кортежа/списка значение str - это название нужного типа для текста ошибки
    :param default: значение по умолчанию, используется только если
        параметр при запросе вообще не передан.
    :param as_: str - параметр, который будет передан в view,
        по умолчанию совпадает с `param`.
    :param err: функция или конструктор, принимающая 1 параметр (текст ошибки)
        и возвращающая HttpResponse
    :return: decorated function
    """
    def decorator(view):
        @functools.wraps(view)
        def decorated_view(request, *args, **kwargs):
            data = getattr(request, from_)
            if param not in data:
                if default is not MISSING:
                    value = default
                else:
                    msg = 'missing required {} param'.format(param)
                    return err(msg)
            else:
                value = data[param]
                if coerce is not None:
                    if isinstance(coerce, (list, tuple)):
                        coerce_fn, expected_type = coerce
                    else:
                        coerce_fn, expected_type = coerce, param
                    try:
                        value = coerce_fn(value)
                    except (ValueError, TypeError) as error:
                        return err(
                            u'{value!r} is not a valid {expected_type}: '
                            u'{error!s}'.format(**locals()))
            kwargs[as_ or param] = value
            return view(request, *args, **kwargs)
        return decorated_view
    return decorator


def expect_param_api(
        param,  # type: str
        from_=u'its_params',  # type: str
        coerce=None,  # type: Union[CoerceFn, CoercePair, None]
        default=MISSING,  # type: Optional[ParamType]
        as_=None,  # type: Optional[str]
):  # type: (...) -> Callable[[ApiView], ApiView]
    """Аналог @expect_param, но при ошибке отдает JsonResponse вместо HttpResponse"""
    return cast(
        Any,
        expect_param(
            param,
            from_=from_,
            coerce=coerce,
            default=default,
            as_=as_,
            err=json_error_response,
        ),
    )


def expect_flag(
        param,  # type: str
        from_='its_params',  # type: str
        default=MISSING,  # type: Optional[ParamType]
        null=False,  # type: bool
        as_=None,  # type: Optional[str]
):  # type: (...) -> Callable[[View], View]
    """shortcut для:
        @expect_param('my_flag', coerce=bool_param)
        -> @expect_flag('my_flag')
        @expect_param('my_flag', coerce=nullable_bool_param, default=None)
        -> @expect_flag('my_flag', null=True, default=None)
    """
    coerce = nullable_bool_param if null else bool_param
    return expect_param(param, coerce=coerce, from_=from_, default=default, as_=as_)


def expect_flag_api(
        param,  # type: str
        from_='its_params',  # type: str
        default=MISSING,  # type: Optional[ParamType]
        null=False,  # type: bool
        as_=None,  # type: Optional[str]
):  # type: (...) -> Callable[[ApiView], ApiView]
    """shortcut для:
        @expect_param_api('my_flag', coerce=bool_param)
        -> @expect_flag_api('my_flag')
        @expect_param_api('my_flag', coerce=nullable_bool_param, default=None)
        -> @expect_flag_api('my_flag', null=True, default=None)
    """
    coerce = nullable_bool_param if null else bool_param
    return expect_param_api(param, coerce=coerce, from_=from_, default=default, as_=as_)
