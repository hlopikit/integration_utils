"""Метаданные транспортных логов без тел запросов и учётных данных из адресов."""

import re
from collections.abc import Mapping
from urllib.parse import urlsplit


_KNOWN_ERROR_CODES = {
    'ACCESS_DENIED', 'ACCESS_ERROR', 'ERROR_ARGUMENT', 'ERROR_CORE',
    'ERROR_METHOD_NOT_FOUND', 'ERROR_NOT_FOUND', 'QUERY_LIMIT_EXCEEDED',
    'OPERATION_TIME_LIMIT', 'INTERNAL_SERVER_ERROR', 'CONNECTION_ERROR',
    'ConnectionToBitrixError', 'NO_AUTH_FOUND', 'APPLICATION_NOT_FOUND',
    'PAYMENT_REQUIRED', 'PORTAL_DELETED', 'PORTAL_BLOCKED_BY_LICENSE_SCANNER',
    'WRONG_ENCODING', 'WRONG_REQUEST', 'NOT_INSTALLED',
    'invalid_token', 'expired_token', 'authorization_error', 'user_access_error',
    'insufficient_scope', 'wrong_client', 'invalid_grant',
    'Nginx 403 Forbidden', 'Bitrix 500 Internal Server Error',
}


def _error_code(value):
    """Оставить известный код, исключив произвольный текст ответа сервера."""
    return value if type(value) is str and value in _KNOWN_ERROR_CODES else 'unknown'


def _batch_error_codes(errors):
    """Выбрать коды ошибок без пользовательских ключей и содержимого результатов."""
    if not isinstance(errors, Mapping):
        return {'reason_type': type(errors).__name__}
    if type(errors.get('error')) is str:
        return {'error': _error_code(errors['error'])}
    return {'errors': [
        _error_code(error.get('error')) if isinstance(error, Mapping) else 'unknown'
        for error in errors.values()
    ]}


def _log_context(domain, api_method=None):
    """Оставляет домен с портом и проверенное имя REST-метода."""
    try:
        parsed = urlsplit(domain if '://' in domain else f'//{domain}')
        hostname = parsed.hostname or ''
        if ':' in hostname:
            hostname = f'[{hostname}]'
        if parsed.port is not None:
            hostname = f'{hostname}:{parsed.port}'
    except (TypeError, ValueError):
        hostname = ''
    context = {'portal_domain': hostname if re.fullmatch(r'[A-Za-z0-9.\[\]:-]{1,261}', hostname) else '[invalid-host]'}
    if api_method is not None:
        context['method_name'] = api_method if isinstance(api_method, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,127}', api_method) else '[invalid-method]'
    return context


def _response_log_metadata(response):
    """Сохраняет статус и размер ответа без его содержимого."""
    return {'status_code': response.status_code, 'body_bytes': len(response.content)}
