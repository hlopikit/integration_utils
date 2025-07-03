# -*- coding: utf-8 -*-
import datetime
from decimal import Decimal, InvalidOperation

import six
import sys

from django.http import JsonResponse


TRUE_VALUES = (1, True, '1', 'true')
FALSE_VALUES = (0, False, '0', 'false')
NULL_VALUES = (None, '', 'null')


# @expect_param_api('foo_id', coerce=int_param)


def _nullable_param(coerce_fn):
    return lambda v: None if v in NULL_VALUES else coerce_fn(v)


def decimal_param(value):
    try:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal(0)
        return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('{!r} cannot be interpreted as decimal'.format(value))


def bool_param(value):
    if value in TRUE_VALUES:
        return True
    elif value in FALSE_VALUES:
        return False
    raise ValueError('{!r} cannot be interpreted as bool'.format(value))


nullable_bool_param = _nullable_param(bool_param)


def int_param(value):
    try:
        return int(value)
    except (TypeError, OverflowError, ValueError):
        raise ValueError('{!r} cannot be interpreted as int'.format(value))


nullable_int_param = _nullable_param(int_param)


def int_or(default, silent=False):
    def coerce(value):
        if isinstance(value, six.integer_types):
            return value
        if value in NULL_VALUES:
            return default
        try:
            return int_param(value)
        except ValueError:
            if not silent:
                raise
            return default
    return coerce


def int_list(sep=','):
    def to_int_list(value):
        if not value:
            return []
        if isinstance(value, str):
            value = value.split(sep)
        try:
            return [int_param(s) for s in value]
        except TypeError:
            raise TypeError('expected list of integers or {sep!r}-separated '
                            'string with integers, got {value!r} instead'
                            .format(**locals()))
    return to_int_list


def one_of(choice=()):
    """
    >>> one_of(['lead', 'deal'])('lead')
    'lead'
    >>> one_of(['lead', 'deal'])('company')
    Traceback (most recent call last):
      ...
    ValueError: 'company' not in ['lead', 'deal']
    >>> one_of(['lead', 'deal'])(1)
    Traceback (most recent call last):
      ...
    TypeError: expected str, got int
    >>> one_of([2.0, 42])('tweeëntwintig')
    Traceback (most recent call last):
      ...
    TypeError: expected float or int, got str
    """
    choices_display = '[%s]' % ', '.join(map(repr, choice))
    allowed_types = list(sorted({type(c) for c in choice},
                                key=lambda t: t.__name__))
    types_display = ' or '.join(t.__name__ for t in allowed_types)

    def coerce(value):
        if type(value) not in allowed_types:
            raise TypeError('expected {}, got {}'
                            .format(types_display, type(value).__name__))
        if value in choice:
            return value
        raise ValueError('{!r} not in {}'.format(value, choices_display))
    return coerce


if sys.version_info >= (3, 7):
    _date_fromisoformat = datetime.date.fromisoformat
else:
    def _date_fromisoformat(value):
        return datetime.datetime.strptime(value, '%Y-%m-%d').date()


def isodate_param(value):
    try:
        return _date_fromisoformat(value)
    except TypeError:
        raise ValueError('expected isoformatted date string, e.g.: "2019-12-31"')


def time_param(value):
    if isinstance(value, datetime.time):
        return value
    try:
        time_args = [int(bit.strip()) for bit in value.split(':')]
        return datetime.time(*time_args)
    except (TypeError, AttributeError, ValueError, OverflowError):
        raise ValueError(
            'expected time string "hour:minute[:second][:microsecond]", '
            'e.g.: "12:31" or "12:31:15" or "12:31:15:666"'
        )


# json responses
def json_error_response(error, status=400, **kwargs):
    return JsonResponse(dict(error=error, **kwargs), status=status)


def json_not_found(error=u'Not Found', **kwargs):
    return json_error_response(error, status=404, **kwargs)


def json_forbidden(error=u'Forbidden', **kwargs):
    return json_error_response(error, status=403, **kwargs)


def json_402(error=u'Premium required', **kwargs):
    return json_error_response(error, status=402, **kwargs)


def json_unauthorized(error=u'Unauthorized', **kwargs):
    return json_error_response(error, status=401, **kwargs)
