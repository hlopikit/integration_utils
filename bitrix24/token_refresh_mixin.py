# -*- coding: UTF-8 -*-

from django.utils import timezone

from integration_utils.bitrix24.exceptions import (
    BaseConnectionError,
    BaseTimeout,
    BitrixApiError,
    BitrixTokenRefreshError,
    ExpiredToken,
)


class BitrixUserTokenRefreshMixin:
    """
    Общая логика BitrixUserToken, которую можно переиспользовать
    между integration_utils и bitrix_utils без привязки к конкретной модели.
    """

    def _save_refresh_error_only(self):
        if self.pk:
            self.save(update_fields=['refresh_error'])

    def _apply_refresh_tokens(self, response_json):
        self.auth_token = response_json.get('access_token')
        self.refresh_token = response_json.get('refresh_token')
        self.auth_token_date = timezone.now()

    def _handle_post_refresh_bitrix_unavailable(self, exc):
        """
        Hook для логирования/обработки сетевых проблем после refresh.
        По умолчанию ничего не делаем.
        """

    def _handle_post_refresh_api_check(self, check_api_call=True, timeout=10, v=1):
        if not check_api_call:
            return True

        try:
            # Токены, например, уволенных сотрудников успешно обновляются.
            # Но даже после обновления по токену будет кидаться ошибка из-за увольнения.
            # Делаем запрос profile, который не требует никаких разрешений.
            self.call_api_method('profile', timeout=timeout, refresh=False)
        except BitrixApiError as e:
            if e.is_unable_to_authorize_user:
                self.refresh_error = self.UNABLE_TO_AUTHORIZE_USER
            elif e.is_user_cant_be_authorized_in_context:
                self.refresh_error = self.USER_CANT_BE_AUTHORIZED_IN_CONTEXT
            elif e.is_authorization_error:
                self.refresh_error = self.AUTHORIZATION_ERROR
            elif e.is_user_access_error:
                self.refresh_error = self.USER_ACCESS_ERROR
            elif e.is_free_plan_error:
                self.refresh_error = self.FREE_PLAN_ERROR

            if self.refresh_error != self.NO_ERROR:
                # Деактивируем токен
                self.is_active = False
                self.save()
                if v == 2:
                    raise BitrixTokenRefreshError(True, e.json_response, e.status_code) from e
                return False
        except (BaseConnectionError, BaseTimeout) as e:
            self._handle_post_refresh_bitrix_unavailable(e)

        return True

    def _finalize_successful_refresh(self, response_json, check_api_call=True, timeout=10, v=1):
        self._apply_refresh_tokens(response_json)

        if not self._handle_post_refresh_api_check(check_api_call=check_api_call, timeout=timeout, v=v):
            return False

        self.is_active = True
        self.save()
        return True

    def _retry_call_after_refresh(self, refresh, timeout, retry_callback):
        if not refresh:
            raise ExpiredToken(status_code=401)

        if self.refresh(timeout=timeout):
            return retry_callback()

        return None
