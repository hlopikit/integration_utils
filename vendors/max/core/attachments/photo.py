import mimetypes
from pathlib import Path
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
            self.token_dict = self._extract_upload_payload(load_file_result)
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
        if isinstance(self.photo, str):
            photo_path = Path(self.photo)
            if photo_path.is_file():
                media_type = mimetypes.guess_type(photo_path.name)[0] or "application/octet-stream"
                with photo_path.open("rb") as photo_file:
                    files = {"data": (photo_path.name, photo_file.read(), media_type)}
                    return self.api.load_file(url=url, files=files, content_types=None)

        files = {"data": self.photo}
        return self.api.load_file(url=url, files=files)

    @staticmethod
    def _extract_upload_payload(load_file_result):
        if load_file_result.get("token"):
            return {"token": load_file_result["token"]}

        for value in load_file_result.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
            if isinstance(value, dict):
                if value.get("token"):
                    return {"token": value["token"]}
                for nested_value in value.values():
                    if isinstance(nested_value, dict) and nested_value.get("token"):
                        return {"token": nested_value["token"]}

        raise ValueError(f"Unexpected upload response format: {load_file_result}")

    def to_dict(self):
        """
        Метод формирования необходимого для API MAX форматат attachments для image
        """
        return {
            "type": "image",
            "payload": self.token_dict
        }
