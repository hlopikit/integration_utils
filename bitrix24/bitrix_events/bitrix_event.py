from datetime import datetime
from typing import Any, Dict, Optional


class BitrixEvent:
    """Событие Bitrix24."""

    def __init__(self, event_name: str, data: Optional[Dict[str, Any]] = None,
                 datetime: Optional[datetime] = None):
        self.event_name = event_name
        self.data = data if data is not None else {}
        self.datetime = datetime

    def process(self) -> Any:
        """Вызывает on_<имя события без ON>; исключения передаются вызывающему коду."""
        event_name = self.event_name.lower()
        if event_name.startswith('on'):
            event_name = event_name[2:]
        handler = getattr(self, 'on_{}'.format(event_name), None)
        if handler is not None:
            return handler()
        return None
