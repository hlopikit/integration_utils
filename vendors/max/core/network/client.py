import requests
import json

from typing import Dict, Any, Optional


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
        url = f"{self.BASE_URL}{path}"
        # if "?" in url:
        #     url += f"&access_token={self.token}"
        # else:
        #     url += f"?access_token={self.token}"
        return url

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
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36",
            "Authorization": self.token
        }
        if content_types:
            header["Content-Type"] = content_types
        if data and not files:
            header["Content-Type"] = "application/json"
            data = json.dumps(data)
        # print(f"Request: {method} {url}")
        # if params:
        # print(f"Params: {params}")
        # if data:
        # print(f"Data: {data}")

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            files=files,
            headers=header,
            verify=False,
            proxies=self.proxy,
            timeout=60
        )
        try:
            response.raise_for_status()
            result = response.json()
            # print(f"Response: {result}")
            return result
        except requests.exceptions.HTTPError as e:
            error_text = f"HTTP error: {e}"
            try:
                error_json = response.json()
                error_text = f"{error_text}, API response: {error_json}"
            except Exception:
                error_text = f"{error_text}, Response text: {response.text}"

            print(error_text)
            # raise Exception(error_text)
            return error_text
        except Exception as e:
            print(f"Request error: {e}")
            raise
