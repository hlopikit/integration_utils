from datetime import datetime
from typing import Any, Dict, Optional

from dateutil.parser import isoparse


class BitrixEvent:
    """Событие Bitrix24."""

    def __init__(self, event_name: str, datetime: datetime, data: Optional[Dict[str, Any]] = None):
        self.event_name = event_name
        self.data = data if data is not None else {}
        self.datetime = datetime

    def process(self) -> Any:
        """Вызывает <event_name>_handler; исключения передаются вызывающему коду."""
        handler = getattr(self, '{}_handler'.format(self.event_name.lower()), None)
        if handler is not None:
            return handler()
        return None

    @classmethod
    def from_bitrix_data(cls, data: Dict[str, Any]) -> "BitrixEvent":
        return cls(
            event_name=data['EVENT_NAME'],
            data=data,
            datetime=isoparse(data['TIMESTAMP_X']),
        )
