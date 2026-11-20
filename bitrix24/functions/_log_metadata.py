"""Метаданные транспортных логов без тел запросов и учётных данных из адресов."""

import re
from collections.abc import Mapping
from urllib.parse import urlsplit


def _error_details(error):
    """
    Выбирает error и error_description без остальных полей ответа.
    """
    if not isinstance(error, Mapping):
        return {'reason_type': type(error).__name__}
    return {field: error[field] for field in ('error', 'error_description') if field in error}


def _batch_error_details(errors):
    """
    Сохраняет ошибки команд без пользовательских ключей и успешных результатов.
    """
    if not isinstance(errors, Mapping):
        return _error_details(errors)
    is_single_error = isinstance(errors.get('error'), str) or isinstance(errors.get('error_description'), str)
    if is_single_error:
        return _error_details(errors)
    return {'errors': [_error_details(error) for error in errors.values()]}


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
