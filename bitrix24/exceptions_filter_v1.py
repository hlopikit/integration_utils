from integration_utils.bitrix24.exceptions import BitrixApiException


def is_not_logic_error(exception: BitrixApiException):
    """
    Deprecated.
    Используйте свойство BitrixApiException вместо этой функции.
    """
    return exception.is_not_logic_error
