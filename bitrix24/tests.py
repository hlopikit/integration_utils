from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.exceptions import BitrixApiError


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
