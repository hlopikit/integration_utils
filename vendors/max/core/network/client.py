import json
from typing import Any, Dict, Optional

import requests

from ...errors import MaxError, MaxNetworkError, MaxUnauthorized


class Client:
    """
    Класс низкоуровневых запросов к API MAX
    """
    # BASE_URL = "https://botapi.max.ru"
    BASE_URL = "https://platform-api.max.ru"

    def __init__(self, token: str, proxy: Optional[dict] = {"https": "", "http": ""}):
        """
        Инициализация клиента

        :param token: Description
        :type token: str
        """
        self.token = token
        self.proxy = proxy
        self.session = requests.Session()

    def _make_url(self, path: str) -> str:
        """
        Метод формирует полную ссылку к API запросу

        :param path: API метод
        :type path: str
        :return: Полный URL запроса к API
        :rtype: str
        """
        return f"{self.BASE_URL}{path}"

    def request(
        self,
        method: str,
        path: str = None,
        url: str = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        content_types: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Главные метод по отправке запроса к API MAX

        :param method: HTTP-метод (GET, POST, PUT, DELETE)
        :type method: str

        :param path: Путь к методу API
        :type path: str

        :param params: Параметры запроса
        :type params: Optional[Dict[str, Any]]

        :param data: Данные для отправки в теле запроса
        :type data: Optional[Dict[str, Any]]

        :param files: Файлы для отправкиescription
        :type files: Optional[Dict[str, Any]]

        :return: Ответ API MAX на заданный метод
        :rtype: Dict[str, Any]
        """
        url = self._make_url(path) if not url else url
        headers = {
            "connection": "keep-alive",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36"
            ),
            "Authorization": self.token,
        }
        if content_types:
            headers["Content-Type"] = content_types
        if data and not files:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                files=files,
                headers=headers,
                verify=False,
                proxies=self.proxy,
                timeout=60,
            )
        except requests.exceptions.Timeout as exc:
            raise MaxNetworkError("Timed out") from exc
        except requests.exceptions.RequestException as exc:
            raise MaxNetworkError(f"requests RequestException {exc}") from exc

        if 200 <= response.status_code <= 299:
            return response.json()

        response_data = self._parse(response)
        error_code = response_data.get("code")
        message = response_data.get("message") or response_data.get("error_description") or "Unknown HTTPError"

        if response.status_code in (401, 403):
            raise MaxUnauthorized(
                message,
                status_code=response.status_code,
                error_code=error_code,
                response_data=response_data,
            )
        if response.status_code == 502:
            raise MaxNetworkError(
                "Bad Gateway",
                status_code=response.status_code,
                error_code=error_code,
                response_data=response_data,
            )
        if response.status_code in (408, 429, 500, 503, 504):
            raise MaxNetworkError(
                f"{message} ({response.status_code})",
                status_code=response.status_code,
                error_code=error_code,
                response_data=response_data,
            )
        raise MaxError(
            message,
            status_code=response.status_code,
            error_code=error_code,
            response_data=response_data,
        )

    @staticmethod
    def _parse(response: requests.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {"message": response.text or "Unknown HTTPError"}
