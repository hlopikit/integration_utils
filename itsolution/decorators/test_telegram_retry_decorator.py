from unittest import TestCase
from unittest.mock import patch

from integration_utils.itsolution.decorators.telegram_retry_decorator import telegram_retry_decorator
from integration_utils.vendors.telegram.error import BadRequest, NetworkError


class TelegramRetryDecoratorTest(TestCase):
    def test_retries_network_error(self):
        calls = []

        @telegram_retry_decorator(attempts=3, timeout_delay=0)
        def unstable():
            calls.append(1)
            if len(calls) < 3:
                raise NetworkError('Bad Gateway')
            return 'ok'

        with patch('integration_utils.itsolution.decorators.telegram_retry_decorator.time.sleep'):
            self.assertEqual(unstable(), 'ok')

        self.assertEqual(len(calls), 3)

    def test_does_not_retry_bad_request(self):
        calls = []

        @telegram_retry_decorator(attempts=3, timeout_delay=0)
        def bad_request():
            calls.append(1)
            raise BadRequest('chat not found')

        with patch('integration_utils.itsolution.decorators.telegram_retry_decorator.time.sleep'):
            with self.assertRaises(BadRequest):
                bad_request()

        self.assertEqual(len(calls), 1)
