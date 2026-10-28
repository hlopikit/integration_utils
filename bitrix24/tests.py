import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
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

    def _start_response(self, request):
        """Вызывает start в тестах без OAuth-запросов к порталу и возвращает сформированный адрес."""
        request.bitrix_user_token = Mock()
        request.bitrix_user_token.signed_pk.return_value = 'test-signed-token'
        with patch('integration_utils.bitrix24.bitrix_user_auth.main_auth.authenticate_on_start_application'), \
                patch('integration_utils.bitrix24.views.start.render', wraps=render) as render_start:
            response = start(request)
        return response, render_start.call_args.args[2]['index_path']

    def test_marketplace_cookie_login_returns_to_original_page(self):
        original_path = '/apps/test_integration_utils/cookie/?users=1&users=2'
        view = main_auth(on_cookies=True)(lambda _: HttpResponse('ok'))
        redirect_response = view(RequestFactory().get(original_path))
        marketplace_params = parse_qs(urlsplit(redirect_response.url).query)
        placement_options = {name: values[-1] for name, values in marketplace_params.items()}
        request = RequestFactory().post('/?DOMAIN=b24.it-solution.ru&APP_SID=session', {
            'AUTH_ID': 'test-token',
            'PLACEMENT': 'DEFAULT',
            'PLACEMENT_OPTIONS': json.dumps(placement_options),
        })

        response, index_path = self._start_response(request)

        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(index_path, f'{original_path}&DOMAIN=b24.it-solution.ru&APP_SID=session')
        self.assertEqual(response.cookies[f'b24app_auth_{settings.APP_SETTINGS.app_name}'].value, 'test-signed-token')
        self.assertContains(response, 'location.href = ')

    def test_placement_return_to_preserves_query_fragment_and_other_options(self):
        request = RequestFactory().post('/?LANG=ru&filter=a&filter=b', {
            'PLACEMENT_OPTIONS': json.dumps({'return_to': '/protected/?users=1&users=2#details', 'any': '328'}),
        })

        _, index_path = self._start_response(request)
        index_url = urlsplit(index_path)
        index_params = parse_qs(index_url.query)

        self.assertEqual(index_url.path, '/protected/')
        self.assertEqual(index_url.fragment, 'details')
        self.assertEqual(index_params, {
            'users': ['1', '2'],
            'LANG': ['ru'],
            'filter': ['a', 'b'],
            'bx_referer_params': [json.dumps({'any': '328'})],
        })

    def test_get_return_to_takes_precedence_over_placement_options(self):
        request = RequestFactory().post('/?return_to=/from-get/', {
            'PLACEMENT_OPTIONS': json.dumps({'return_to': '/from-placement/'}),
        })

        _, index_path = self._start_response(request)

        self.assertEqual(index_path, '/from-get/')

    @override_settings(APP_SETTINGS=SimpleNamespace(application_index_path='/index/', app_name='test-app'))
    def test_unsafe_or_non_string_placement_return_to_uses_application_index(self):
        for return_to in ('https://example.com/', '//example.com/', '/\\example.com/', None, 42, True, [], {}):
            with self.subTest(return_to=return_to):
                request = RequestFactory().post('/', {'PLACEMENT_OPTIONS': json.dumps({'return_to': return_to})})

                _, index_path = self._start_response(request)

                self.assertEqual(index_path, '/index/')

    def test_referer_return_to_is_used_when_placement_options_are_missing_or_invalid(self):
        for placement_options in (None, '{broken', 'null', '42', 'true', '[]', '["return_to"]'):
            with self.subTest(placement_options=placement_options):
                post_params = {} if placement_options is None else {'PLACEMENT_OPTIONS': placement_options}
                request = RequestFactory().post('/', post_params, HTTP_REFERER='https://b24.it-solution.ru/marketplace/app/80/?return_to=%2Ffrom-referer%2F')

                _, index_path = self._start_response(request)

                self.assertEqual(index_path, '/from-referer/')

    @override_settings(APP_SETTINGS=SimpleNamespace(application_index_path='/index/?tab=main#details', app_name='test-app'))
    def test_launch_without_return_to_preserves_application_index_and_placement_options(self):
        request = RequestFactory().post('/?LANG=ru', {'PLACEMENT_OPTIONS': json.dumps({'ID': '42'})})

        _, index_path = self._start_response(request)
        index_url = urlsplit(index_path)

        self.assertEqual(index_url.path, '/index/')
        self.assertEqual(index_url.fragment, 'details')
        self.assertEqual(parse_qs(index_url.query), {'tab': ['main'], 'bx_referer_params': [json.dumps({'ID': '42'})], 'LANG': ['ru']})

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
