# -*- coding: utf-8 -*-
import functools

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
        # вернется HttpResponseBadRequest с описанием ошибки

    :param param: str - параметр
    :param from_: str - откуда брать: 'its_params', 'GET', 'POST'
    :param coerce: coerce_fn or (coerce_fn, str) - Приведение к нужному типу,
        пример начений:
        - app_get_params.functions.int_param
        - str
        - (MyClass, MyClass.__name__)
        При ValueError/TypeError возвращается HttpResponseBadRequest
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
    """Аналог @expect_param но отдает JsonResponse вместо HttpResponse
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
