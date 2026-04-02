import requests
from typing import Dict, Any, List, Optional

from .core.network.client import Client


proxy = None
ignore_warnings = True


class Api:
    """
    Клиент для рабты с api MAX
    """
    def __init__(self, token: str):
        """
        Docstring for __init__

        :param token: Токен бота
        :type token: str
        """
        if ignore_warnings:
            requests.packages.urllib3.disable_warnings()
        self.client = Client(token=token, proxy=proxy)

    def get_my_info(self) -> Dict[str, Any]:
        """
        Получает информацию о текущем боте

        :return: Информация о боте
        :rtype: Dict[str, Any]
        """
        return self.client.request("GET", "/me")

    def get_updates(self, allowed_updates: List[str], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Получает новые обновления от API через лонгполлинг

        :param allowed_updates: Список типов обновлений, которые нужно получать
        :param extra: Дополнительные параметры запроса

        :return: Список обновлений
        :rtype: Dict[str, Any]
        """
        params = extra or {}

        if allowed_updates:
            params["types"] = ",".join(allowed_updates)

        return self.client.request("GET", "/updates", params=params)

    def get_message(self, msg_id: str):
        """
        Получает сообщение по `msg_id`
        """
        return self.client.request("GET", f"/messages/{msg_id}")

    def send_message(
        self,
        chat_id: str = None,
        msg_id: str = None,
        text: str = None,
        method: str = "POST",
        attachments: Optional[List[Dict[str, Any]]] = None,
        parse_mode: str = "markdown",
        notify: bool = True
    ) -> Dict[str, Any]:
        """
        Отправляет/удаляет/обновляет сообщение в чате

        :param chat_id: Идентификатор чата
        :type chat_id: str

        :param text: Текст сообщения
        :type text: str

        :param attachments: Вложения сообщения
        :type text: Optional[List[Dict[str, Any]]]

        :return: Информация об отправленном сообщении
        :rtype: Dict[str, Any]
        """
        # query параметры запроса
        params = {}
        if chat_id:
            params = {"chat_id": chat_id}
        elif msg_id and method in ("DELETE", "PUT"):
            params = {"message_id": msg_id}

        data = {}
        if text:
            data = {"text": text}

        if attachments:
            data["attachments"] = attachments
        else:
            data["attachments"] = []

        if parse_mode:
            data["format"] = parse_mode

        if notify:
            data["notify"] = notify

        return self.client.request(method, "/messages", params=params, data=data)

    def get_upload_file_url(self, type_attach: str):
        """
        Апи метод для получения url загрузки файла.

        :param type_attach: Тип файла, который требуется загрузить
        :type type_attach: str

        :return: Json с url для загрузки файла
        :rtype: Dict[str: Any]
        """
        return self.client.request("POST", f"/uploads?type={type_attach}")

    def get_chat_info(self, chat_id: str):
        """
        Апи метод для получения инфомрации о чате.

        :param chat_id: Айди чата
        :type chat_id: str

        :return: Json
        :rtype: Dict[str: Any]
        """
        return self.client.request("GET", f"/chats/{chat_id}")

    def get_bot_info(self):
        """
        Апи метод для получения информации о боте

        :return: Json
        :rtype: Dict[str: Any]
        """
        return self.client.request("GET", "/me")

    def leave_chat(self, chat_id: str):
        """
        Апи метод для получения информации о боте

        :return: Json
        :rtype: Dict[str: Any]
        """
        return self.client.request("DELETE", f"/chats/{chat_id}/members/me")

    def load_file(self, url: str, files: Dict, content_types: str = None):
        """
        Апи метод для получения url загрузки файла.

        :param type_attach: Тип файла, который требуется загрузить
        :type type_attach: str

        :return: Json с url для загрузки файла
        :rtype: Dict[str: Any]
        """
        return self.client.request(method="POST", url=url, files=files, content_types=content_types)

    def answer_callback(
            self,
            callback_id: str,
            text: Optional[str] = None,
            notification: Optional[str] = None,
            attachments: Optional[List[Dict[str, Any]]] = None,
            link: Optional[Dict[str, Any]] = None,
            notify: bool = True,
            format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Метод позволяет отправить уведомление пользователю и/или обновить
        исходное сообщение после нажатия на inline-кнопку.

        :param callback_id: Уникальный идентификатор callback-запроса.
                            Получается из поля `callback.callback_id` в обновлении
        :type callback_id: str

        :param text: Новый текст сообщения. Если указан, сообщение будет обновлено
        :type text: Optional[str]

        :param notification: Текст всплывающего уведомления для пользователя. 
                             Пользователь увидит это уведомление как всплывающее сообщение
                             Пока не очень работает, в тесте :)
        :type notification: Optional[str]

        :param attachments: Новые вложения сообщения. Если указаны, сообщение будет обновлено.
                            Для полной замены вложений передайте новый список.
                            Чтобы удалить все вложения, передайте пустой список.
        :type attachments: Optional[List[Dict[str, Any]]]

        :param link: Ссылка на сообщение для reply/forward формата.
                     Должен содержать поля `type` ("reply" или "forward") и `mid`
        :type link: Optional[Dict[str, Any]]

        :param notify: Отправлять ли системное уведомление в чат об изменении сообщения.
                       По умолчанию True - участники увидят "Сообщение было изменено"
        :type notify: bool

        :param format: Формат текста сообщения. Доступные значения: "markdown", "html"
        :type format: Optional[str]

        :return: Ответ от MAX API
        :rtype: Dict[str, Any]

        :raises HTTPError: При ошибке HTTP запроса

        Примеры использования:

        1. Только уведомление:
        api.answer_callback(
            callback_id="callback123",
            notification="Действие выполнено!"
        )

        2. Обновление сообщения с уведомлением:
        api.answer_callback(
            callback_id="callback123",
            text="**Сообщение обновлено!**",
            notification="Обновление выполнено",
            format="markdown",
            notify=False  # Не показывать "Сообщение было изменено" в чате
        )

        3, 4. Пока в тесте
        3. Обновление с новыми вложениями:
        api.answer_callback(
            callback_id="callback123",
            text="Вот новые вложения:",
            attachments=[
                {
                    "type": "photo",
                    "payload": {"url": "https://example.com/photo.jpg"}
                }
            ],
            notification="Фотография добавлена"
        )

        4. Удаление всех вложений (оставить только текст):
        api.answer_callback(
            callback_id="callback123",
            text="Вложения удалены",
            attachments=[],  # Пустой список удалит все вложения
            notification="Вложения удалены"
        )
        """
        params = {"callback_id": callback_id}
        data: Dict[str, Any] = {}

        # Если нужно изменить сообщение (text, attachments, link, format)
        if text is not None or attachments is not None or link is not None or format is not None:
            msg: Dict[str, Any] = {"notify": notify}
            if text is not None:
                msg["text"] = text
            if attachments is not None:
                msg["attachments"] = attachments
            if link is not None:
                msg["link"] = link
            if format is not None:
                msg["format"] = format
            data["message"] = msg

        # Если нужно отправить уведомление
        if notification is not None:
            data["notification"] = notification

        # print(f"Answer params: {params}")
        # print(f"Answer data: {data}")

        # Если data пустой, отправляем пустой объект
        if not data:
            data = {}

        return self.client.request("POST", "/answers", params=params, data=data)
