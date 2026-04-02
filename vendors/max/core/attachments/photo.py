from typing import Any, Union

from ...apihelper import Api


class Photo:
    """
    Класс формирования объекта attachments для метода MaxiBot.send_photo
    """

    def __init__(self, photo: Union[Any, str], api: Api):
        try:
            self.api = api
            self.photo = photo
            upload_url = self._get_upload_url().get("url")
            if not upload_url:
                return []
            load_file_result = self._load_file_to_max(url=upload_url)
            self.token_dict = list(list(load_file_result.values())[0].values())[0]
        except Exception:
            return []

    def _get_upload_url(self, type_attach: str = "image"):
        """
        Шаг 1.
        Метод получения url для загрузки фото
        """
        return self.api.get_upload_file_url(type_attach=type_attach)

    def _load_file_to_max(self, url: str):
        """
        Шаг 2.
        Метод загрузки файла по url для загрузки фото
        """
        files = {"data": self.photo}
        return self.api.load_file(url=url, files=files)

    def to_dict(self):
        """
        Метод формирования необходимого для API MAX форматат attachments для image
        """
        return {
            "type": "image",
            "payload": self.token_dict
        }
