from datetime import datetime as dt
from typing import Any, Callable, Dict, Literal, Optional, overload

from integration_utils.bitrix_events.functions.offline_events import collect_offline_events


class BaseBitrixEventObject:
    """
    Базовый класс для события Битрикс24.
    Для обработки события через process нужно добавить handler-метод.
    """

    PROCESS_WHEN_RECEIVED: bool = True
    '''
    Обрабатывать ли событие в момент получения.
    Для объектного события нет смысла ставить False.
    Иначе событие не сохранится и не обработается.
    '''

    def __init__(self, event_name: str, datetime: dt, data: Optional[Dict[str, Any]] = None):
        self.event_name = event_name
        self.data = data if data is not None else {}
        self.datetime = datetime

    def process(self) -> Any:
        """
        Вызвать метод-обработчик по имени события.
        """
        handler = getattr(self, f'{self.event_name.lower()}_handler', None)
        if handler is None:
            return self.default_handler()
        return handler()

    def default_handler(self):
        raise NotImplementedError(f'Handler for {self.event_name} is not implemented')

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BaseBitrixEventObject":
        """
        Создать объект события из словаря с Битрикс-данными.
        """
        return cls(
            event_name=data['EVENT_NAME'],
            data=data,
            datetime=dt.fromisoformat(data['TIMESTAMP_X']),
        )

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[False] = False,
        clear_error: Literal[True] = True,
        recover: bool = False,
    ) -> Callable[[], str]:
        """
        Собираем события без очистки при сборе, с пометкой ошибок в очереди.
        Параметр recover можно ставить любой.
        """

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[False] = False,
        clear_error: Literal[False],
        recover: Literal[True],
    ) -> Callable[[], str]:
        """
        Собираем события без очистки при сборе, без пометки ошибок в очереди.
        Параметр recover нужно ставить True, чтобы дособрать ошибки из очереди.
        """

    @classmethod
    @overload
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: Literal[True],
        clear_error: bool = True,
        recover: Literal[False] = False,
    ) -> Callable[[], str]:
        """
        Собираем события с очисткой при сборе.
        Параметр recover должен быть False, clear_error не влияет на выполнение.
        """

    @classmethod
    def make_cron_collect_offline_events(
        cls,
        *,
        clear_on_get: bool = False,
        clear_error: bool = True,
        recover: bool = False,
    ) -> Callable[[], str]:
        def cron_collect_offline_events() -> str:
            return collect_offline_events(cls, clear_on_get=clear_on_get, clear_error=clear_error, recover=recover)
        return cron_collect_offline_events
