from integration_utils.bitrix_robots.models import BaseRobot


class ExampleRobot(BaseRobot):
    CODE = 'its_example_robot'
    NAME = 'Пример робота - отправить уведомление пользователю'

    PROPERTIES = {
        'to': {
            'Name': {'ru': 'Пользователь'},
            'Type': 'string',
            'Required': 'Y',
        },
        'message': {
            'Name': {'ru': 'Сообщение'},
            'Type': 'text',
            'Required': 'Y',
        },
    }

    RETURN_PROPERTIES = {
        'ok': {
            'Name': {'ru': 'ok'},
            'Type': 'bool',
            'Required': 'Y',
        },
        'error': {
            'Name': {'ru': 'error'},
            'Type': 'string',
            'Required': 'N',
        },
    }

    def process(self) -> dict:
        try:
            self.dynamic_token.call_api_method_v2('im.notify', {
                'to': self.props['to'],
                'message': self.props['message'],
                'type': 'SYSTEM'
            }, timeout=5)

        except Exception as exc:
            return dict(ok=False, error=str(exc))

        return dict(ok=True)
