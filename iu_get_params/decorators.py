# -*- coding: utf-8 -*-
import functools
import json
import math
from copy import deepcopy
from inspect import Parameter, signature
from typing import get_origin, get_type_hints

from django.http import HttpResponse
from django.http import HttpResponseBadRequest
import six
from django.http import JsonResponse

from .functions import bool_param, nullable_bool_param, json_error_response


if not six.PY2:  # typing
    from typing import Optional, Any, Callable, Union, TypeVar, Type, Tuple

    ParamType = TypeVar('ParamType')
    View = Callable[..., HttpResponse]
    ApiView = Callable[..., JsonResponse]
    CoerceFn = Union[Type[ParamType], Callable[[Any], ParamType]]
    CoercePair = Tuple[CoerceFn, str]


missing = object()


def expect_typed_params(*, from_='its_params', api=False):
    """Привести аннотированные аргументы view через cattrs.

    ``request`` и аргументы, уже переданные Django позиционно или по имени,
    не обрабатываются. Параметр без аннотации также не обрабатывается. Значение
    по умолчанию используется только при отсутствии ключа; явный null допустим
    лишь для Optional/Union с None (или Any). Ошибки возвращаются с HTTP 400;
    при ``api=True`` тело ответа имеет вид ``{"error": "..."}``.

    Декоратор ставится под ``@get_params_from_sources`` для ``its_params``::

        @get_params_from_sources
        @expect_typed_params(api=True)
        def save_items(request, items: list[dict[str, int]], page: int = 0):
            ...
    """
    # Старые декораторы должны импортироваться без необязательной зависимости cattrs.
    try:
        from cattrs import Converter, transform_error
        from cattrs.cols import list_structure_factory, mapping_structure_factory
        from cattrs.errors import BaseValidationError
    except ImportError as import_error:
        raise ImportError(
            'expect_typed_params requires cattrs>=24.1.0'
        ) from import_error

    def decorator(view):
        converter = Converter(detailed_validation=True)
        view_signature = signature(view)

        def structure_str(value, _):
            if not isinstance(value, str):
                raise TypeError('expected str')
            return value

        def structure_int(value, _):
            if type(value) is int:
                return value
            invalid_integer_format = (
                not isinstance(value, str)
                or value != value.strip()
                or '_' in value
            )
            if invalid_integer_format:
                raise TypeError('expected int')
            return int(value)

        def structure_float(value, _):
            if type(value) not in (int, float, str):
                raise TypeError('expected float')
            invalid_float_format = (
                isinstance(value, str)
                and (value != value.strip() or '_' in value)
            )
            if invalid_float_format:
                raise TypeError('expected float')
            structured_value = float(value)
            if not math.isfinite(structured_value):
                raise ValueError('expected finite float')
            return structured_value

        def structure_bool(value, _):
            if type(value) not in (bool, int, str):
                raise TypeError('expected bool')
            return bool_param(value)

        def strict_list_structure_factory(expected_type, current_converter):
            structure_list_items = list_structure_factory(
                expected_type,
                current_converter,
            )

            def structure_list_strict(value, target_type):
                if not isinstance(value, list):
                    raise TypeError('expected list')
                return structure_list_items(value, target_type)

            return structure_list_strict

        def strict_dict_structure_factory(expected_type, current_converter):
            structure_dict_items = mapping_structure_factory(
                expected_type,
                current_converter,
            )

            def structure_dict_strict(value, target_type):
                if not isinstance(value, dict):
                    raise TypeError('expected dict')
                return structure_dict_items(value, target_type)

            return structure_dict_strict

        converter.register_structure_hook(str, structure_str)
        converter.register_structure_hook(int, structure_int)
        converter.register_structure_hook(float, structure_float)
        converter.register_structure_hook(bool, structure_bool)
        converter.register_structure_hook_factory(
            lambda expected_type: get_origin(expected_type) is list,
            strict_list_structure_factory,
        )
        converter.register_structure_hook_factory(
            lambda expected_type: get_origin(expected_type) is dict,
            strict_dict_structure_factory,
        )

        typed_parameters = []
        type_hints = get_type_hints(view, include_extras=True)
        for parameter_name, parameter in view_signature.parameters.items():
            parameter_is_request = parameter_name == 'request'
            parameter_is_untyped = parameter_name not in type_hints
            parameter_is_variadic = parameter.kind in (
                Parameter.VAR_POSITIONAL,
                Parameter.VAR_KEYWORD,
            )
            if parameter_is_request or parameter_is_untyped or parameter_is_variadic:
                continue

            expected_type = type_hints[parameter_name]
            structure_value = converter.get_structure_hook(expected_type)

            if parameter.default is Parameter.empty:
                default = missing
            else:
                # Некорректный default — ошибка программиста, выявляем её при запуске.
                default = structure_value(parameter.default, expected_type)
            typed_parameters.append(
                (parameter_name, expected_type, structure_value, default)
            )

        error_response = json_error_response if api else HttpResponseBadRequest

        @functools.wraps(view)
        def decorated_view(request, *args, **kwargs):
            source_params = getattr(request, from_)
            bound_arguments = view_signature.bind_partial(
                request,
                *args,
                **kwargs,
            )
            for (
                parameter_name,
                expected_type,
                structure_value,
                default,
            ) in typed_parameters:
                if parameter_name in bound_arguments.arguments:
                    continue
                if parameter_name not in source_params:
                    if default is missing:
                        return error_response(
                            f'missing required {parameter_name} param'
                        )
                    parameter_value = deepcopy(default)
                else:
                    raw_value = source_params[parameter_name]
                    if from_ in ('GET', 'POST') and isinstance(raw_value, str):
                        try:
                            raw_value = json.loads(raw_value)
                        except json.JSONDecodeError:
                            pass
                    try:
                        parameter_value = structure_value(raw_value, expected_type)
                    except (
                        BaseValidationError,
                        TypeError,
                        ValueError,
                        OverflowError,
                    ) as structure_error:
                        error_messages = []
                        for error_message in transform_error(structure_error):
                            description, path_separator, path = (
                                error_message.rpartition(' @ $')
                            )
                            if path_separator:
                                error_messages.append(
                                    f'{parameter_name}{path}: {description}'
                                )
                            else:
                                error_messages.append(
                                    f'{parameter_name}: {error_message}'
                                )
                        return error_response('; '.join(error_messages))
                kwargs[parameter_name] = parameter_value
            return view(request, *args, **kwargs)

        return decorated_view

    return decorator


def expect_param(
        param,  # type: str
        from_='its_params',  # type: str
        coerce=None,  # type: Union[CoerceFn, CoercePair, None]
        default=missing,  # type: Optional[ParamType]
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
                if default is not missing:
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
        default=missing,  # type: Optional[ParamType]
        as_=None,  # type: Optional[str]
):  # type: (...) -> Callable[[ApiView], ApiView]
    """Аналог @expect_param, но при ошибке отдает JsonResponse вместо HttpResponse
    """
    return expect_param(param, from_=from_, coerce=coerce, default=default,
                        as_=as_, err=json_error_response)


def expect_flag(
        param,  # type: str
        from_='its_params',  # type: str
        default=missing,  # type: Optional[ParamType]
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
    return expect_param(param, coerce=coerce, from_=from_,
                        default=default, as_=as_)


def expect_flag_api(
        param,  # type: str
        from_='its_params',  # type: str
        default=missing,  # type: Optional[ParamType]
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
    return expect_param_api(param, coerce=coerce, from_=from_,
                            default=default, as_=as_)
