from integration_utils.bitrix24.exceptions import BitrixApiException, ConnectionToBitrixError

from integration_utils.bitrix24.exceptions import BitrixApiError

"""
Сгенерировано ИИшкой
Exception
└── BitrixApiException
    ├── BitrixApiError
    │   ├── ExpiredToken
    │   ├── BitrixTokenRefreshError
    │   ├── BitrixApiServerError
    │   ├── SnapiError
    │   └── BitrixApiErrorNotFound
    ├── ConnectionToBitrixError
    ├── BatchFailed
    │   └── BatchApiCallError
    │   └── JsonDecodeBatchFailed
    └── BaseTimeout
        ├── BitrixTimeout
        └── BitrixOauthRefreshTimeout
"""

def is_not_logic_error(exception: BitrixApiException):
    # Проверить ошибку на, то что она не логическая, а именно что-то с сетями, сервервами, лицензиями, сбоями, кодировками, настройками

    if isinstance(exception, ConnectionToBitrixError):
        return True

    if isinstance(exception, BitrixApiError):
        error_conditions = [
            exception.is_internal_server_error,
            exception.is_error_connecting_to_authorization_server,
            exception.is_connection_to_bitrix_error,
            exception.is_license_check_failed,
            exception.is_no_auth_found,
            exception.is_portal_deleted,
            exception.is_free_plan_error,
            exception.is_wrong_encoding,
            exception.is_authorization_error,
            exception.is_out_of_disc_space_error,
            exception.is_status_gte_500,
            exception.is_application_not_found,
        ]
        if any(error_conditions):
            return True
        else:
            return False
