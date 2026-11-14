import importlib
import json
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

import requests
from django.test import SimpleTestCase, override_settings
from django.views.debug import ExceptionReporter

from integration_utils.bitrix24.exceptions import BatchFailed, BitrixApiError, BitrixConnectionError, BitrixTimeout, JsonDecodeBatchFailed
from integration_utils.bitrix24.models import BitrixUserToken


api = importlib.import_module('integration_utils.bitrix24.functions.api_call')
batch = importlib.import_module('integration_utils.bitrix24.functions.batch_api_call')
token_module = importlib.import_module('integration_utils.bitrix24.models.bitrix_user_token')


@override_settings(B24_HTTP_BASIC_AUTH=None)
class TransportLoggingTests(SimpleTestCase):
    access = 'fake-access-secret-sentinel'
    refresh = 'fake-refresh-secret-sentinel'
    hook = 'fake-webhook-secret-sentinel'
    client_secret = 'fake-client-secret-sentinel'
    password = 'fake-password-secret-sentinel'
    custom = 'fake-unknown-field-secret-sentinel'

    def setUp(self):
        self.logger = Mock()
        for target in (api, batch, token_module):
            logger_patch = patch.object(target, 'ilogger', self.logger)
            logger_patch.start()
            self.addCleanup(logger_patch.stop)
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('Real network is forbidden'))
        network.start()
        self.addCleanup(network.stop)

    def _response(self, payload=None, *, status=200, text=None, headers=None):
        response = requests.Response()
        response.status_code = status
        response.encoding = 'utf-8'
        response._content = (text if text is not None else json.dumps(payload)).encode('utf-8')
        response.headers.update(headers or {})
        return response

    def _assert_safe_logs(self):
        captured = repr(self.logger.mock_calls)
        self.assertTrue(self.logger.mock_calls)
        for secret in (self.access, self.refresh, self.hook, self.client_secret, self.password, self.custom):
            self.assertNotIn(secret, captured)
        self.assertNotIn('exc_info=True', captured)

    def test_oauth_and_webhook_requests_keep_payload_but_do_not_log_any_values(self):
        params = {'password': self.password, 'unknown_field': self.custom, 'nested': {'refresh_token': self.refresh}}
        payload = {'result': {'access_token': self.access, 'arbitrary': self.custom}, 'time': {'operating': 301}}
        response = self._response(payload)
        for webhook in (False, True):
            with self.subTest(webhook=webhook), patch.object(api.requests, 'post', return_value=response) as post:
                result = api.api_call('portal.example.test', 'profile', '1/' + self.hook if webhook else self.access, params=params, webhook=webhook)
                self.assertIs(result, response)
                outgoing = parse_qs(post.call_args.args[1].decode())
                self.assertEqual(outgoing['password'], [self.password])
                self.assertEqual(outgoing['unknown_field'], [self.custom])
                if webhook:
                    self.assertIn(self.hook, post.call_args.args[0])
                else:
                    self.assertEqual(outgoing['auth'], [self.access])
                self.assertNotIn('auth', params)
                self.assertEqual(result.json(), payload)
                self._assert_safe_logs()

    def test_rest3_oauth_and_webhook_keep_json_and_mask_all_logged_values(self):
        params = {'client_secret': self.client_secret, 'other': self.custom}
        payload = {'result': {'auth': self.access, 'refresh_token': self.refresh}}
        response = self._response(payload)
        for webhook in (False, True):
            with self.subTest(webhook=webhook), patch.object(api.requests, 'post', return_value=response) as post:
                result = api.api_call_v3('portal.example.test', 'tasks.task.get', auth_token=self.access,
                                         web_hook_auth='1/' + self.hook if webhook else None, params=params)
                self.assertEqual(result, payload)
                self.assertEqual(post.call_args.kwargs['json']['other'], self.custom)
                if webhook:
                    self.assertIn(self.hook, post.call_args.args[0])
                else:
                    self.assertEqual(post.call_args.kwargs['json']['auth'], self.access)
                self.assertNotIn('auth', params)
                self._assert_safe_logs()

    def test_non_json_response_and_parser_exception_never_log_body_or_exception_text(self):
        response = self._response(text=f'<html>auth={self.access}; {self.custom}</html>', status=502)
        with patch.object(api.requests, 'post', return_value=response):
            self.assertIs(api.api_call('portal.example.test', 'profile', self.access), response)
        self._assert_safe_logs()
        response.json = Mock(side_effect=RuntimeError(self.password))
        with patch.object(api.requests, 'post', return_value=response):
            api.api_call('portal.example.test', 'profile', self.access)
        self._assert_safe_logs()

    def test_retry_exhaustion_and_redirect_logs_drop_credentials_in_paths_and_queries(self):
        url = f'https://user:{self.password}@portal.example.test:443/rest/1/{self.hook}/profile.json?auth={self.access}'
        for retries in (0, 1):
            with patch.object(api.requests, 'post', return_value=self._response({}, status=503)):
                api.call_with_retries(url, b'auth=opaque', retries_on_503=retries, sleep_on_503_time=0)
            self._assert_safe_logs()
        # Смена порта должна по-прежнему обрабатываться как смена netloc.
        location = f'https://user:{self.password}@portal.example.test:8443/rest/1/{self.hook}/profile.json?token={self.refresh}'
        redirect = self._response({}, status=302, headers={'location': location})
        with patch.object(api.requests, 'post', side_effect=[redirect, self._response({'result': True})]) as post:
            api.call_with_retries(url, b'auth=opaque')
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.args[0], location)
        self._assert_safe_logs()
        with patch.object(api.requests, 'post', return_value=self._response({}, status=302)):
            api.call_with_retries(url, b'auth=opaque')
        self._assert_safe_logs()

    def test_network_exception_strings_repr_and_traceback_do_not_reveal_credentials(self):
        for function in (api.api_call, api.api_call_v3):
            for exception, expected in ((requests.ConnectionError, BitrixConnectionError), (requests.Timeout, BitrixTimeout)):
                with self.subTest(function=function.__name__, exception=exception.__name__), patch.object(api.requests, 'post', side_effect=exception(self.access)):
                    try:
                        function('portal.example.test', 'profile', self.access)
                    except expected as error:
                        rendered = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
                        self.assertNotIn(self.access, str(error))
                        self.assertNotIn(self.access, repr(error))
                        self.assertNotIn(self.access, rendered)
                        self.assertIsInstance(error.requests_exception, exception)
                    else:
                        self.fail('Expected network error')

    def test_api_and_batch_exception_representations_keep_details_in_attributes_only(self):
        payload = {'error': self.access, 'error_description': self.password}
        error = BitrixApiError('deprecated', payload, 401, self.custom, token=self.refresh)
        for value in (str(error), repr(error), str(BatchFailed(self.access)), repr(BatchFailed(self.access))):
            for secret in (self.access, self.password, self.custom, self.refresh):
                self.assertNotIn(secret, value)
        self.assertIs(error.json_response, payload)
        self.assertEqual(error.error_description, self.password)
        self.assertEqual(error.token, self.refresh)

    @override_settings(DEBUG=False)
    def test_production_exception_reporter_hides_transport_locals(self):
        for function in (api.api_call, api.api_call_v3):
            with patch.object(api.requests, 'post', side_effect=requests.ConnectionError(self.access)):
                try:
                    function('portal.example.test', 'profile', self.access, params={'password': self.password})
                except BitrixConnectionError:
                    frames = ExceptionReporter(None, *sys.exc_info()).get_traceback_frames()
                    transport_frames = [frame for frame in frames if str(frame.get('filename', '')).endswith('functions/api_call.py') or
                                        str(frame.get('filename', '')).endswith('functions\\api_call.py')]
                    self.assertTrue(transport_frames)
                    for frame in transport_frames:
                        variables = repr(list(frame['vars']))
                        self.assertNotIn(self.access, variables)
                        self.assertNotIn(self.password, variables)

    @override_settings(APP_SETTINGS=SimpleNamespace(application_bitrix_client_id='test-client', application_bitrix_client_secret=client_secret))
    def test_refresh_network_errors_hide_oauth_url_from_traceback(self):
        token = BitrixUserToken(pk=123, user_id=20, refresh_token=self.refresh)
        with patch.object(token_module.requests, 'get', side_effect=requests.ConnectionError(self.refresh)):
            try:
                token.refresh()
            except token_module.BitrixOauthRefreshConnectionError as error:
                rendered = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
                self.assertNotIn(self.refresh, rendered)
                self.assertNotIn(self.client_secret, rendered)
            else:
                self.fail('Expected refresh connection error')

    def test_batch_bad_json_and_operating_error_do_not_log_raw_data(self):
        token = SimpleNamespace(domain='portal.example.test', auth_token=self.access, web_hook_auth=None, application=None)
        for response, expected_error in [(self._response(text=self.custom), JsonDecodeBatchFailed),
                                         (self._response({'result': {'result': {'data_0': self.custom}, 'result_error': {}, 'result_time': {'data_0': {'operating': self.custom}}}}), None)]:
            with patch.object(batch, 'api_call', return_value=response):
                if expected_error:
                    with self.assertRaises(expected_error):
                        batch.batch_api_call([('profile', {})], token)
                else:
                    batch.batch_api_call([('profile', {})], token)
            self._assert_safe_logs()

    @override_settings(APP_SETTINGS=SimpleNamespace(application_bitrix_client_id='test-client', application_bitrix_client_secret=client_secret))
    def test_refresh_success_error_and_unknown_error_code_log_no_credentials(self):
        cases = [({'access_token': self.access, 'refresh_token': self.refresh}, 200, True),
                 ({'error': 'invalid_grant', 'error_description': self.custom}, 400, False),
                 ({'error': self.password}, 400, False), ({'message': self.custom}, 503, False)]
        for payload, status, expected in cases:
            token = BitrixUserToken(pk=123, user_id=20, is_active=True, auth_token=self.access, refresh_token=self.refresh)
            response = self._response(payload, status=status)
            with self.subTest(status=status, expected=expected), patch.object(token_module.requests, 'get', return_value=response) as get, patch.object(token, 'save'):
                self.assertEqual(token.refresh(check_api_call=False), expected)
                self.assertIn(self.client_secret, get.call_args.args[0])
                self.assertIn(self.refresh, get.call_args.args[0])
                self._assert_safe_logs()
