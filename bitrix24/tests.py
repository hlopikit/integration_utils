from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import EmptyCookie
from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.exceptions import BitrixApiError
from integration_utils.bitrix24.views.start import _get_index_path, start


class MainAuthTests(SimpleTestCase):
    def test_invalid_start_token_returns_authorization_page(self):
        request = RequestFactory().post('/tasks/task_start_bp_open_placement/', {'AUTH_ID': 'invalid'})
        error = BitrixApiError(
            has_resp='deprecated',
            json_response={'error': 'invalid_token', 'error_description': 'Unable to get application by token'},
            status_code=401,
            message='invalid token',
        )
        view = main_auth(on_start=True)(lambda _: HttpResponse('ok'))

        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.authenticate_on_start_application', side_effect=error):
            response = view(request)

        self.assertEqual(response.status_code, 401)
        self.assertContains(response, 'Не удалось авторизовать приложение', status_code=401)

    def test_missing_cookie_on_get_opens_marketplace_and_preserves_relative_path(self):
        request = RequestFactory().get('/hr/absense?users=1&users=2')
        view = main_auth(on_cookies=True)(lambda _: HttpResponse('ok'))

        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.get_bitrix_user_token_from_cookie', side_effect=EmptyCookie):
            response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://b24.it-solution.ru/marketplace/app/80/?return_to=%2Fhr%2Fabsense%3Fusers%3D1%26users%3D2')

    @override_settings(BITRIX_MARKETPLACE_AUTH_APP_ID=123)
    def test_missing_cookie_uses_marketplace_app_id_from_project_settings(self):
        request = RequestFactory().get('/protected/')
        view = main_auth(on_cookies=True)(lambda _: HttpResponse('ok'))

        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.get_bitrix_user_token_from_cookie', side_effect=EmptyCookie):
            response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://b24.it-solution.ru/marketplace/app/123/?return_to=%2Fprotected%2F')

    def test_missing_cookie_on_post_keeps_authorization_error(self):
        request = RequestFactory().post('/tasks/api/')
        view = main_auth(on_cookies=True)(lambda _: HttpResponse('ok'))

        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.get_bitrix_user_token_from_cookie', side_effect=EmptyCookie):
            response = view(request)

        self.assertEqual(response.status_code, 401)
        self.assertContains(response, 'Ошибка авторизации по cookie', status_code=401)

    @override_settings(BITRIX_MARKETPLACE_AUTH_APP_ID=None)
    def test_missing_marketplace_app_configuration_keeps_authorization_error(self):
        request = RequestFactory().get('/hr/absense')
        view = main_auth(on_cookies=True)(lambda _: HttpResponse('ok'))

        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.get_bitrix_user_token_from_cookie', side_effect=EmptyCookie):
            response = view(request)

        self.assertEqual(response.status_code, 401)


class StartViewTests(SimpleTestCase):
    """Проверяет безопасный возврат на экран itsis после Marketplace-входа."""

    def test_relative_return_to_is_used(self):
        request = RequestFactory().get('/?return_to=/hr/absense?date=2026-10-08')

        self.assertEqual(_get_index_path(request), '/hr/absense?date=2026-10-08')

    def test_external_return_to_is_ignored(self):
        request = RequestFactory().get('/?return_to=https://example.com/')

        self.assertNotEqual(_get_index_path(request), 'https://example.com/')

    def test_protocol_relative_return_to_is_ignored(self):
        request = RequestFactory().get('/?return_to=//example.com/')

        self.assertNotEqual(_get_index_path(request), '//example.com/')

    def test_return_to_is_not_repeated_or_rendered_as_raw_javascript(self):
        request = RequestFactory().post('/?return_to=/hr/absense?users=1%26users=2', {'AUTH_ID': 'test-token'})
        request.bitrix_user_token = Mock()
        request.bitrix_user_token.signed_pk.return_value = 'test-signed-token'
        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.authenticate_on_start_application'), \
                patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.set_auth_cookie', side_effect=lambda response, _: response):
            response = start.__wrapped__(request)

        self.assertContains(response, "location.href = '/hr/absense?users\\u003D1\\u0026users\\u003D2'")
        self.assertNotContains(response, 'return_to=')
