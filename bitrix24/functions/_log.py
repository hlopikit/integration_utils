import datetime
import logging
from pprint import pformat as pprint_pformat

from django.conf import settings
from django.utils.encoding import force_text
from django.utils import timezone
import six

from settings import ilogger

DEFAULT_REQUEST_TEMPLATE = u'''[{time}] {http_method} {method}
caller: {caller}
request params: {pretty_params}
portal domain: {portal_domain!r}
auth token: {auth_token!r}
BitrixUser: {bx_user!r}
BitrixUserToken: {bx_user_token!r}
full URL: {url}
'''
DEFAULT_RESPONSE_TEMPLATE = u'''[REQUEST]
[{time}] {http_method} {method}
caller: {caller}
request params: {pretty_params}
portal domain: {portal_domain!r}
auth token: {auth_token!r}
BitrixUser: {bx_user!r}
BitrixUserToken: {bx_user_token!r}
full URL: {url}

[RESPONSE]
status: {response_status}
headers: {response_headers}
redirects: {response_redirect_history}

[RESPONSE DATA]
{maybe_decoded_data}
'''
DEFAULT_LOG_DT_FORMAT = '%Y/%m/%d %H:%M:%S.%f'


REQUEST_TEMPLATE = getattr(
    settings,
    'BITRIX_REQUEST_LOG_TEMPLATE',
    DEFAULT_REQUEST_TEMPLATE,
)
RESPONSE_TEMPLATE = getattr(
    settings,
    'BITRIX_RESPONSE_LOG_TEMPLATE',
    DEFAULT_RESPONSE_TEMPLATE,
)
LOG_DT_FORMAT = getattr(settings, 'LOG_DT_FORMAT', DEFAULT_LOG_DT_FORMAT)


def pformat(value, indent=2, width=120, depth=4, compact=True):
    return pprint_pformat(value, indent=indent, width=width,
                          depth=depth, compact=compact)


def unicode(s, encoding='utf8', strings_only=False,
            errors='replace' if six.PY2 else 'backslashreplace'):
    return force_text(s, encoding=encoding, strings_only=strings_only,
                      errors=errors)


def timestamp_to_dt(timestamp, to_local_time=True):
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    utc_dt = timezone.make_aware(dt, timezone=timezone.utc)
    if not to_local_time:
        return utc_dt
    return timezone.localtime(utc_dt)


def fmt_dt(dt):
    return dt.strftime(LOG_DT_FORMAT)


def fmt_timestamp(timestamp, to_local_time=True):
    return fmt_dt(timestamp_to_dt(timestamp, to_local_time=to_local_time))


def fmt_dt_like(value, to_local_time=True):
    if isinstance(value, (int, float)):
        return fmt_timestamp(value, to_local_time=to_local_time)
    if isinstance(value, datetime.datetime):
        return fmt_dt(value)
    raise TypeError('%s is not a datetime-like object' % value)


def log_bitrix_request(
    caller,  # 'batch_api_call' or 'api_call_2'
    http_method,  # e.g. 'POST'
    method,  # e.g. 'user.get'
    params,  # e.g. {'id': 42}
    portal_domain,  # e.g. 'b24.it-solution.ru'
    auth_token,  # e.g. 'bi12who2ff3dfzge' or '42/zbtarwgz9wfrbriz'
    url,  # e.g. 'https://b24.it-solution.ru/rest/user.get.json?auth=...'
    time=None,  # e.g. time.time() or timezone.now()
    bx_user=None,  # BitrixUser instance
    bx_user_token=None,  # BitrixUserToken instance
    loglvl=logging.INFO,  # logging.{LVL}
):
    """Логирует данные запроса перед запросом к ресту Б24.
    """
    if time is None:
        time = timezone.now()
    return ilogger.log(loglvl, 'bitrix_request', REQUEST_TEMPLATE.format(
        caller=caller,
        time=fmt_dt_like(time),
        http_method=http_method,
        method=method,
        pretty_params=pformat(params),
        portal_domain=portal_domain,
        auth_token=auth_token,
        url=unicode(url),
        bx_user=bx_user,
        bx_user_token=bx_user_token,
    ))


def log_bitrix_response(
    caller,
    http_method,
    method,
    params,
    portal_domain,
    auth_token,
    url,
    requests_response,  # requests.Response instance
    time=None,
    bx_user=None,
    bx_user_token=None,
    loglvl=logging.INFO,
):
    """Логирует ответ от реста Б24 + данные запроса.
    """
    def fmt_response(response, pretty=True):
        data = None
        if response.status_code:
            try:
                json = response.json()
            except ValueError:
                data = unicode(response.text)
            else:
                data = pformat(json)
        ctx = dict(
            response_status=response.status_code,
            response_headers=dict(response.headers),
            response_redirect_history=[
                fmt_response(resp, False) for resp in response.history
            ] if response.status_code else None,
            maybe_decoded_data=data,
        )
        if not pretty:
            return ctx
        ctx.update(
            response_redirect_history=pformat(ctx['response_redirect_history']),
            response_headers=pformat(ctx['response_headers'])
        )
        return ctx
    if time is None:
        time = timezone.now()
    return ilogger.log(loglvl, 'bitrix_response', RESPONSE_TEMPLATE.format(
        caller=caller,
        time=fmt_dt_like(time),
        http_method=http_method,
        method=method,
        pretty_params=pformat(params),
        portal_domain=portal_domain,
        auth_token=auth_token,
        url=unicode(url),
        bx_user=bx_user,
        bx_user_token=bx_user_token,
        **fmt_response(requests_response)
    ))
