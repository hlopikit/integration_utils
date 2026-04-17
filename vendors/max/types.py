# from dataclasses import dataclass
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Text, TypeAlias

from .apihelper import Api
from .util import is_pil_image, pil_image_to_bytes


__all__ = [
    "Attachment",
    "Api",
    "Body",
    "CallbackQuery",
    "Chat",
    "ChatLink",
    "FileAttachment",
    "ImageAttachment",
    "ImagePayload",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "InputMedia",
    "InputMediaPhoto",
    "InputMediaVideo",
    "JsonDeserializable",
    "Link",
    "Message",
    "Photo",
    "Recipient",
    "StickerAttachment",
    "Update",
    "UpdateType",
    "User",
]


Update: TypeAlias = Dict[Text, Any]


class JsonDeserializable(object):
    def __str__(self):
        d = {
            x: y.__dict__ if hasattr(y, '__dict__') else y
            for x, y in self.__dict__.items()
        }
        return str(d)


class UpdateType:
    """
    Типы обновлений, которые можно получать от MAX API
    """
    MESSAGE_CREATED = "message_created"
    MESSAGE_CALLBACK = "message_callback"
    BOT_STARTED = "bot_started"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_DELETED = "message_deleted"
    MESSAGE_CHAT_CREATED = "message_chat_created"
    CHAT_TITLE_CHANGED = "chat_title_changed"
    BOT_ADDED = "bot_added"


class InlineKeyboardButton:
    """
    Класс для создания inline-кнопок в сообщениях

    :param text: Текст на кнопке
    :type text: str

    :param url: URL ссылка для кнопки типа "link"
    :type url: Optional[str]

    :param callback_data: Данные для callback-кнопки
    :type callback_data: Optional[str]
    """
    MAX_URL_LEN = 2048

    def __init__(
            self,
            text: str,
            url: Optional[str] = None,
            callback_data: Optional[str] = None,
    ):
        self.text = text
        self.url = url
        self.callback_data = callback_data

        if not (url or callback_data):
            raise ValueError("url или callback_data обязан быть")
        if url and callback_data:
            raise ValueError("укажите что-то одно")
        if url and len(url) > self.MAX_URL_LEN:
            raise ValueError(f"url не может быть длиннее {self.MAX_URL_LEN} символов")

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует кнопку в словарь для отправки в MAX API

        :return: Словарь с данными кнопки в формате MAX API
        :rtype: Dict[str, Any]
        """
        if self.url:
            return {"type": "link", "text": self.text, "url": self.url}
        return {
            "type": "callback",
            "text": self.text,
            "payload": self.callback_data
        }

    def is_special(self) -> bool:
        """
        Проверяет, является ли кнопка специальной (ограничивает ряд до 3 кнопок)

        :return: True если кнопка специальная (link), False если обычная (callback)
        :rtype: bool
        """
        return self.url is not None  # link


class InlineKeyboardMarkup:
    """
    Класс для создания inline-клавиатур в сообщениях

    :param row_width: Ширина ряда по умолчанию (сколько кнопок в ряду)
    :type row_width: int
    """
    MAX_ROWS = 30
    MAX_BUTTONS = 210
    MAX_ROW_REGULAR = 7
    MAX_ROW_SPECIAL = 3

    def __init__(self, row_width: int = 1):
        self.row_width = row_width
        self.keyboard: List[List[InlineKeyboardButton]] = []

    def add(self, *args: InlineKeyboardButton, row_width=None) -> 'InlineKeyboardMarkup':
        """
        Добавляет кнопки в клавиатуру, автоматически разбивая на ряды

        :param args: Кнопки для добавления
        :type args: InlineKeyboardButton

        :param row_width: Ширина ряда для этих кнопок (если не указано, используется self.row_width)
        :type row_width: Optional[int]

        :return: Текущий объект клавиатуры (для цепочки вызовов)
        :rtype: InlineKeyboardMarkup
        """
        width = row_width or self.row_width
        row = []
        for btn in args:
            row.append(btn)
            if len(row) == width:
                self._append_row(row)
                row = []
        if row:
            self._append_row(row)
        return self

    def row(self, *args: InlineKeyboardButton) -> 'InlineKeyboardMarkup':
        """
        Добавляет ряд кнопок в клавиатуру

        :param args: Кнопки для добавления в ряд
        :type args: InlineKeyboardButton

        :return: Текущий объект клавиатуры (для цепочки вызовов)
        :rtype: InlineKeyboardMarkup
        """
        if args:
            self._append_row(list(args))
        return self

    def to_attachment(self) -> Dict[str, Any]:
        """
        Преобразует клавиатуру в attachment для отправки в сообщении

        :return: Словарь с данными клавиатуры в формате MAX API
        :rtype: Dict[str, Any]
        """
        self._validate()
        return {
            "type": "inline_keyboard",
            "payload": {"buttons": [[btn.to_dict() for btn in row] for row in self.keyboard]},
        }

    def _append_row(self, row: List[InlineKeyboardButton]):
        """
        Метод для добавления ряда кнопок

        :param row: Ряд кнопок для добавления
        :type row: List[InlineKeyboardButton]
        """
        self.keyboard.append(row)

    def _validate(self):
        """
        Метод для валидации клавиатуры

        :raises ValueError: Если превышены лимиты на количество кнопок или рядов
        """
        total = sum(len(r) for r in self.keyboard)
        if total > self.MAX_BUTTONS:
            raise ValueError(f"Максимум {self.MAX_BUTTONS} кнопок")
        if len(self.keyboard) > self.MAX_ROWS:
            raise ValueError(f"Максимум {self.MAX_ROWS} рядов")

        for row in self.keyboard:
            special_in_row = any(btn.is_special() for btn in row)
            limit = self.MAX_ROW_SPECIAL if special_in_row else self.MAX_ROW_REGULAR
            if len(row) > limit:
                raise ValueError(
                    f"Ряд содержит {len(row)} кнопок, но максимум {limit} "
                    f"(из-за special-кнопок)" if special_in_row else ""
                )


class ImagePayload(JsonDeserializable):
    """
    Класс для хранения данных изображения

    :param payload: Словарь с данными изображения
    :type payload: Dict[str, Any]
    """

    def __init__(self, payload: Dict[str, Any]):
        self.photo_id = payload.get("photo_id")
        self.token = payload.get("token")
        self.url = payload.get("url")


class Attachment(JsonDeserializable):
    """
    Класс для нормализации входящего MAX attachment

    :param attach: Словарь с данными вложения
    :type attach: Dict[str, Any]
    """

    @classmethod
    def from_dict(cls, attach: Dict[str, Any]) -> "Attachment":
        attachment_type = attach["type"]

        if attachment_type == "image":
            return ImageAttachment(attach=attach)

        if attachment_type == "file":
            return FileAttachment(attach=attach)

        if attachment_type == "sticker":
            return StickerAttachment(attach=attach)

        raise ValueError(f"Unknown attachment type: {attachment_type}")

    @classmethod
    def normalize_attachments(cls, attachments: List[Dict[str, Any]]) -> Optional[Dict[str, Any] | List[Dict[str, Any]]]:
        normalized_attachments = [cls.from_dict(attachment).to_normalized_dict() for attachment in attachments]
        if not normalized_attachments:
            return None
        if len(normalized_attachments) == 1:
            return normalized_attachments[0]
        return normalized_attachments

    def __init__(self, attach: Dict[str, Any]):
        self.raw = attach
        self.type = attach["type"]
        self.payload = attach["payload"]
        self.filename = attach.get("filename")
        self.size = attach.get("size")


class ImageAttachment(Attachment):
    """
    Класс для работы с вложениями типа "image"

    :param attach: Словарь с данными вложения
    :type attach: Dict[str, Any]
    """

    def __init__(self, attach: Dict[str, Any]):
        super().__init__(attach=attach)
        self.payload = ImagePayload(payload=attach["payload"])

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует объект в словарь

        :return: Словарь с данными изображения
        :rtype: Dict[str, Any]
        """
        return {
            "payload": {
                "photo_id": self.payload.photo_id,
                "token": self.payload.token,
                "url": self.payload.url
            },
            "type": self.type
        }

    def to_normalized_dict(self) -> Dict[str, Any]:
        return {
            "type": "image",
            "photo_id": self.payload.photo_id,
            "token": self.payload.token,
            "url": self.payload.url,
        }


class FileAttachment(Attachment):
    """Класс для работы с вложениями типа file"""

    def to_normalized_dict(self) -> Dict[str, Any]:
        return {
            "type": "file",
            "file_id": self.payload["fileId"],
            "token": self.payload["token"],
            "url": self.payload["url"],
            "filename": self.filename,
            "size": self.size,
        }


class StickerAttachment(Attachment):
    """Класс для работы с вложениями типа sticker"""

    def to_normalized_dict(self) -> Dict[str, Any]:
        return {
            "type": "sticker",
            "code": self.payload["code"],
        }


class Recipient(JsonDeserializable):
    """
    Класс получателя сообщения

    :param rec: Словарь recipient из ответа MAX API
    :type rec: Dict[str, Any]
    """

    def __init__(self, rec: Dict[str, Any]):
        self.chat_id = rec.get("chat_id")
        self.chat_type = rec.get("chat_type")
        self.user_id = rec.get("user_id")


class Body(JsonDeserializable):
    """
    Класс тела сообщения

    :param body: Словарь body из ответа MAX API
    :type body: Dict[str, Any]
    """

    def __init__(self, body: Dict[str, Any]):
        self.mid = body.get("mid")
        self.seq = body.get("seq")
        self.text = body.get("text")
        self.attachments = body.get("attachments")


class User(JsonDeserializable):
    """
    Класс пользователя

    :param update: Обновление от MAX API
    :type update: Dict[str, Any]
    """

    def __init__(self, update: Dict[str, Any]):
        if not isinstance(update, dict):
            pass
        elif update.get("callback"):
            self.id = update.get("message").get("recipient").get("chat_id")
            self.real_id = update.get("callback").get("user").get("user_id")
            self.is_bot = update.get("callback").get("user").get("is_bot")
            self.first_name = update.get("callback").get("user").get("first_name")
            self.username = update.get("callback").get("user").get("name")
            self.last_name = update.get("callback").get("user").get("last_name")
            self.language_code = update.get("user_locale")
        elif update.get("update_type") in (UpdateType.BOT_STARTED, UpdateType.BOT_ADDED, UpdateType.CHAT_TITLE_CHANGED):
            self.id = update.get("chat_id")
            self.real_id = update.get("user").get("user_id")
            self.is_bot = update.get("user").get("is_bot")
            self.first_name = update.get("user").get("first_name")
            self.username = update.get("user").get("name")
            self.last_name = update.get("user").get("last_name")
            self.language_code = update.get("user_locale")
        else:
            self.id = update.get("message").get("recipient").get("chat_id")
            self.real_id = update.get("message").get("sender").get("user_id")
            self.is_bot = update.get("message").get("sender").get("is_bot")
            self.first_name = update.get("message").get("sender").get("first_name")
            self.username = update.get("message").get("sender").get("name")
            self.last_name = update.get("message").get("sender").get("last_name")
            self.language_code = update.get("user_locale")


class Chat(JsonDeserializable):
    """
    Класс чата

    :param update: Обновление от MAX API
    :type update: Dict[str, Any]
    """

    def __init__(self, update: Dict[str, Any], api: Api):
        self.api = api
        if update.get("update_type") == UpdateType.BOT_STARTED:
            self.id = update.get("chat_id")
            self.title = self.get_chat_title(chat_id=self.id)
            self.type = "dialog"
            self.user_id = None
        elif update.get("update_type") == UpdateType.BOT_ADDED:
            self.id = update.get("chat_id")
            self.title = self.get_chat_title(chat_id=self.id)
            self.type = None
            self.user_id = None
        elif update.get("update_type") == UpdateType.CHAT_TITLE_CHANGED:
            self.id = update.get("chat_id")
            self.title = update.get("title")
            self.type = None
            self.user_id = None
        else:
            self.id = update.get("message").get("recipient").get("chat_id")
            self.title = self.get_chat_title(chat_id=self.id)
            self.type = update.get("message").get("recipient").get("chat_type")
            self.user_id = update.get("message").get("recipient").get("user_id")

    def get_chat_title(self, chat_id: str):
        """
        Получение заголовка чата

        :param chat_id: айди чата
        :type chat_id: Dict[str, Any]
        """
        info = self.api.get_chat_info(chat_id=chat_id)
        return info.get("title")


class ChatLink(JsonDeserializable):
    """
    Класс ссылки на чат

    :param update: Обновление от MAX API
    :type update: Dict[str, Any]
    """

    def __init__(self, update: Dict[str, Any]):
        self.id = update.get("chat_id")


class Link(JsonDeserializable):
    """
    Класс ссылки на сообщение

    :param link: Словарь с данными ссылки
    :type link: Dict[str, Any]
    """

    def __init__(self, link: Dict[str, Any]):
        if link:
            self.type = link.get("type")
            self.message_id: str = None
            self.from_user: Optional[User] = None
            self.chat: ChatLink = ChatLink(update=link)


class Photo(JsonDeserializable):
    """
    Класс для работы с фотографиями

    :param update: Обновление от MAX API
    :type update: Dict[str, Any]
    """

    def __init__(self, update: Dict[str, Any]):
        attach = update.get("message", {}).get("body", {}).get("attachments", None)
        if attach:
            for att in attach:
                if att.get("type") == "image":
                    self.file_id = att.get("payload").get("photo_id")
                    self.token: str = att.get("payload").get("token")
                    self.url: str = att.get("payload").get("url")


class InputMedia(JsonDeserializable):
    """
    Класс формирования объекта attachments для отправки медиа

    :param type: Тип медиа (photo/file)
    :type type: str

    :param media: Байты медиа
    :type media: bytes

    :param caption: Подпись к медиа
    :type caption: Optional[str]

    :param parse_mode: Режим парсинга текста (markdown/html)
    :type parse_mode: Optional[str]
    """
    compare_types = {
        "photo": "image",
        "file": "file"
    }

    def __init__(self, type: str = None, media: bytes = None, caption: str = None, parse_mode: str = None):
        self.type = type if type else "photo"
        self.media = media
        self.caption = caption
        self.parse_mode = parse_mode
        self.api = None

    def _get_upload_url(self, type_attach: str = "photo") -> Dict[str, Any]:
        """
        Шаг 1. Получение URL для загрузки файла

        :param type_attach: Тип вложения
        :type type_attach: str

        :return: Ответ API с URL для загрузки
        :rtype: Dict[str, Any]
        """
        return self.api.get_upload_file_url(type_attach=self.compare_types.get(type_attach))

    def _load_file_to_max(self, url: str, file_name: str = None) -> Dict[str, Any]:
        """
        Шаг 2. Загрузка файла на сервер MAX API

        :param url: URL для загрузки
        :type url: str

        :param file_name: Имя файла
        :type file_name: Optional[str]

        :return: Ответ API после загрузки
        :rtype: Dict[str, Any]
        """
        media = self.media
        media_name = file_name

        if isinstance(media, str):
            media_path = Path(media)
            if media_path.is_file():
                media_name = media_name or media_path.name
                media_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
                with media_path.open("rb") as media_file:
                    files = {"data": (media_name, media_file.read(), media_type)}
                    return self.api.load_file(url=url, files=files, content_types=None)

        if file_name:
            media_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            files = {"data": (file_name, media, media_type)}
            return self.api.load_file(url=url, files=files, content_types=None)

        files = {"data": media}
        return self.api.load_file(url=url, files=files)

    @staticmethod
    def _extract_upload_payload(load_file_result: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(load_file_result, dict):
            raise ValueError(f"Unexpected upload response type: {type(load_file_result)}")

        if load_file_result.get("token"):
            return {"token": load_file_result["token"]}

        for value in load_file_result.values():
            if isinstance(value, list) and value:
                first_item = value[0]
                if isinstance(first_item, dict):
                    return first_item
            if isinstance(value, dict):
                if value.get("token"):
                    return {"token": value["token"]}
                for nested_value in value.values():
                    if isinstance(nested_value, dict) and nested_value.get("token"):
                        return {"token": nested_value["token"]}

        raise ValueError(f"Unexpected upload response format: {load_file_result}")

    def to_dict(self, api: Api, file_name: str = None) -> Dict[str, Any]:
        """
        Формирование attachments для отправки медиа

        :param api: Объект API
        :type api: Api

        :param file_name: Имя файла
        :type file_name: Optional[str]

        :return: Словарь с данными вложения
        :rtype: Dict[str, Any]
        """
        self.api = api
        upload_url = self._get_upload_url(type_attach=self.type).get("url")
        if not upload_url:
            return []
        if is_pil_image(self.media):
            self.media = pil_image_to_bytes(self.media)
        load_file_result = self._load_file_to_max(url=upload_url, file_name=file_name)
        token_dict = self._extract_upload_payload(load_file_result)
        return {
            "type": self.compare_types.get(self.type),
            "payload": token_dict
        }


class InputMediaPhoto(InputMedia, JsonDeserializable):
    """
    Класс для отправки фотографий

    :param media: Байты изображения
    :type media: bytes

    :param caption: Подпись к фото
    :type caption: Optional[str]

    :param parse_mode: Режим парсинга текста
    :type parse_mode: Optional[str]
    """

    def __init__(self, media=None, caption=None, parse_mode=None):
        super().__init__(type="photo", media=media, caption=caption, parse_mode=parse_mode)


class InputMediaVideo(InputMedia, JsonDeserializable):
    """
    Класс для отправки видео

    :param media: Байты видео
    :type media: bytes

    :param caption: Подпись к видео
    :type caption: Optional[str]

    :param parse_mode: Режим парсинга текста
    :type parse_mode: Optional[str]
    """

    def __init__(self, media=None, caption=None, parse_mode=None):
        super().__init__(type="video", media=media, caption=caption, parse_mode=parse_mode)


class Message(JsonDeserializable):
    """
    Класс для работы с сообщениями (аналог telebot.types.Message)

    :param update: Обновление от MAX API
    :type update: Dict[str, Any]

    :param api: Объект API
    :type api: Api
    """

    @staticmethod
    def _get_photo_from_attachments(update: Dict[str, Any]) -> Optional[ImageAttachment]:
        """
        Извлечение фото из вложений сообщения

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: Объект ImageAttachment или None
        :rtype: Optional[ImageAttachment]
        """
        if update.get("message"):
            update = update.get("message")
            if update.get("body"):
                update = update.get("body")
                if update.get("attachments"):
                    attachs = update.get("attachments")
                    for attach in attachs:
                        if attach.get("type") == "image":
                            return ImageAttachment(attach=attach)
        return None

    @staticmethod
    def _get_content_type(update: Dict[str, Any]) -> str:
        """
        Определение типа контента сообщения

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: Тип контента
        :rtype: str
        """
        try:
            if update.get("message").get("body").get("attachments"):
                c_type = update.get("message").get("body").get("attachments")[0].get("type")
                if c_type == "image":
                    return "photo"
                else:
                    return c_type
            else:
                return "text"
        except Exception:
            if update.get("update_type") in (UpdateType.BOT_ADDED, UpdateType.CHAT_TITLE_CHANGED):
                return update.get("update_type")
            else:
                return "text"

    @staticmethod
    def _get_msg_id(update: Dict[str, Any]) -> Optional[str]:
        """
        Получение ID сообщения

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: ID сообщения или None
        :rtype: Optional[str]
        """
        try:
            if update.get("message").get("body"):
                return update.get("message").get("body").get("mid")
            elif update.get("message").get("mid"):
                return update.get("message").get("mid")
            else:
                return None
        except Exception:
            return None

    @staticmethod
    def _get_msg_timestamp(update: Dict[str, Any]) -> Optional[datetime]:
        """
        Получение времени сообщения

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: Время сообщения или None
        :rtype: Optional[datetime]
        """
        if update.get("timestamp"):
            time = str(update.get("timestamp"))
            main_time = time[:10]
            milisec = time[10:]
            alltime = float(main_time + "." + milisec)
            return datetime.fromtimestamp(alltime)
        else:
            return None

    @staticmethod
    def _get_msg_text(update: Dict[str, Any]) -> Optional[str]:
        """
        Получение текста сообщения

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: Текст сообщения или None
        :rtype: Optional[str]
        """
        if update.get("message", {}).get("body", None):
            return update.get("message").get("body").get("text")
        elif update.get("update_type") == UpdateType.BOT_STARTED:
            return "/start" + " " + update.get("payload", "")
        else:
            return None

    def __init__(self, update: Dict[str, Any], api: Api):
        """
        Инициализация объекта сообщения
        """
        self.update = update
        self.api = api
        self.content_type: str = self._get_content_type(update=update)
        self.id: Optional[str] = self._get_msg_id(update=update)
        self.message_id: Optional[str] = self._get_msg_id(update=update)
        self.from_user: Optional[User] = User(update=update)
        self.date: Optional[datetime] = self._get_msg_timestamp(update=update)
        self.chat: Chat = Chat(update=update, api=api)
        self.reply_to_message: Link = Link(link=update.get("message", {}).get("link", None))
        self.text: Optional[str] = self._get_msg_text(update=update)
        self.photo: Optional[ImageAttachment] = self._get_photo_from_attachments(update=update)
        self.photo_reply: Photo = Photo(update=update)
        self.update_type = update.get('update_type')

    # def reply(self, text: str, **kwargs) -> Dict[str, Any]:
    #     """
    #     Ответ на текущее сообщение
    #
    #     :param text: Текст ответа
    #     :type text: str
    #
    #     :param kwargs: Дополнительные параметры:
    #         - parse_mode: Режим парсинга (markdown/html)
    #         - reply_markup: Клавиатура
    #         - attachments: Вложения
    #
    #     :return: Ответ API
    #     :rtype: Dict[str, Any]
    #     """
    #     attachments = kwargs.get('attachments', [])
    #     reply_markup = kwargs.get('reply_markup')
    #
    #     if reply_markup:
    #         attachments.append(reply_markup.to_attachment())
    #
    #     return self.api.send_message(
    #         chat_id=self.chat.id,
    #         text=text,
    #         attachments=attachments,
    #         link=self.message_id
    #     )


class CallbackQuery:
    """
    Класс для обработки callback-запросов от inline-кнопок

    :param update: Обновление от MAX API с типом 'message_callback'
    :type update: Dict[str, Any]

    :param api: Объект API для отправки ответов
    :type api: Api
    """

    def __init__(self, update: Dict[str, Any], api: Api):
        self.api = api
        cb = update.get("callback", {})
        self.id: str = cb.get("callback_id", "")
        self.chat_instance: str = self.id
        self.data: Optional[str] = cb.get("payload")

        # Если нет в callback, пытаемся извлечь из message attachments
        if not self.data:
            self.data = self._extract_button_data_from_message(update)

        msg = update.get("message", {})
        self.from_user = User(update=update) if msg else None
        self.message = Message(update=update, api=api) if msg else None

    def _extract_button_data_from_message(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Извлечение данных кнопки из message attachments

        :param update: Обновление от MAX API
        :type update: Dict[str, Any]

        :return: Данные кнопки или None если не найдены
        :rtype: Optional[str]
        """
        callback_id = self.id
        message = update.get("message", {})

        if not message:
            return None

        body = message.get("body", {})
        attachments = body.get("attachments", [])

        for attachment in attachments:
            if attachment.get("callback_id") == callback_id:
                payload = attachment.get("payload", {})
                buttons = payload.get("buttons", [])

                for row in buttons:
                    for button in row:
                        if button.get("type") == "callback":
                            return button.get("text", "unknown")

        return None

    def answer(self, text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Ответ на нажатие inline-кнопки в Max API

        :param text: Текст для обновления сообщения
        :type text: Optional[str]

        :param kwargs: Дополнительные параметры:
            - notification: Текст уведомления для пользователя
            - attachments: Вложения для обновления сообщения
            - link: Ссылка на сообщение для reply/forward
            - notify: Отправлять ли уведомление о редактировании
            - format: Формат текста (markdown/html)

        :return: Ответ от API
        :rtype: Dict[str, Any]
        """
        notification = kwargs.pop('notification', None)
        attachments = kwargs.pop('attachments', None)
        link = kwargs.pop('link', None)
        notify = kwargs.pop('notify', True)
        format = kwargs.pop('format', None)

        should_update_message = (text is not None or
                                 attachments is not None or
                                 link is not None)

        try:
            if not should_update_message and notification:
                return self.api.answer_callback(
                    callback_id=self.id,
                    notification=notification
                )
            else:
                return self.api.answer_callback(
                    callback_id=self.id,
                    text=text,
                    notification=notification,
                    attachments=attachments,
                    link=link,
                    notify=notify,
                    format=format
                )
        except Exception as e:
            if notification:
                try:
                    return self.api.answer_callback(
                        callback_id=self.id,
                        notification=notification
                    )
                except:
                    return {"success": False, "error": str(e)}
            return {"success": False, "error": str(e)}

    def answer_notification(self, text: str) -> Dict[str, Any]:
        """
        Отправка только уведомления (без изменения сообщения)

        :param text: Текст уведомления
        :type text: str

        :return: Ответ от API
        :rtype: Dict[str, Any]
        """
        return self.answer(notification=text)

    def answer_update(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Обновление сообщения с опциональным уведомлением

        :param text: Текст для обновления сообщения
        :type text: str

        :param kwargs: Дополнительные параметры
        :type kwargs: Dict[str, Any]

        :return: Ответ от API
        :rtype: Dict[str, Any]
        """
        if 'notification' not in kwargs:
            kwargs['notification'] = "Обновлено!"
        return self.answer(text=text, **kwargs)
