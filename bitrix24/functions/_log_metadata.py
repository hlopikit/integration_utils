"""Разрешенные метаданные транспортных логов. Тела, query, webhook-пути и исключения сюда не передаются."""

import re
from urllib.parse import urlsplit


def _log_context(domain, api_method=None):
    """Оставляет hostname и синтаксически корректное имя REST-метода без credentials URL."""
    try:
        hostname = urlsplit(domain if '://' in domain else f'//{domain}').hostname or ''
    except (TypeError, ValueError):
        hostname = ''
    context = {'portal_domain': hostname if re.fullmatch(r'[A-Za-z0-9.:-]{1,253}', hostname) else '[invalid-host]'}
    if api_method is not None:
        context['method_name'] = api_method if isinstance(api_method, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,127}', api_method) else '[invalid-method]'
    return context


def _response_log_metadata(response):
    """Тело ответа может содержать access/refresh tokens, пароль или произвольный секрет; сохраняется только его размер."""
    return {'status_code': response.status_code, 'body_bytes': len(response.content)}
