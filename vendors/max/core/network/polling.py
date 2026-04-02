import asyncio
import traceback

from typing import Callable, List, Optional, Dict, Any

# from api import Api


class Polling:
    """
    Класс получения обновлений из API MAX через поллинг
    """

    def __init__(self, api, allowed_updates: Optional[List[str]] = None):
        """
        Инициализация класса

        :param api: Клиент АПИ
        :type api: Api

        :param allowed_updates: Клиент АПИ
        :type allowed_updates: Optional[List[str]]
        """
        self.api = api
        self.allowed_updates = allowed_updates
        self.is_running = False
        self.marker = None
        self.is_prev_add = False

    def stop(self):
        """
        Метод остановки поллинга
        """
        self.is_running = False

    async def loop(self, handler: Callable[[Dict[str, Any]], None]):
        """
        Главный цикл поллинга

        :param handler: Description
        :type handler: Callable[[Dict[str, Any]], None]
        """
        self.is_running = True
        print("Starting polling loop")

        while self.is_running:
            try:
                updates_data = await self._get_updates()
                if "marker" in updates_data.keys():
                    self.marker = updates_data["marker"]
                updates = updates_data.get("updates", [])
                for update in updates:
                    try:
                        if update.get("update_type") == "bot_added" and self.is_prev_add:
                            continue
                        else:
                            if update.get("update_type") == "bot_added":
                                self.is_prev_add = True
                            else:
                                self.is_prev_add = False
                            handler(update)
                    except Exception:
                        print(f"Error handling update {traceback.format_exc()}")

            except Exception:
                print(f"Some error in get updates {traceback.format_exc()}")

    async def _get_updates(self) -> Dict[str, Any]:
        """
        Метод получения обновлений по боту из API MAX

        :return: Description
        :rtype: Dict[str, Any]
        """
        params = {}
        if self.marker is not None:
            params["marker"] = self.marker
        updates_data = await asyncio.to_thread(
            self.api.get_updates,
            self.allowed_updates or [],
            params
        )
        return updates_data
