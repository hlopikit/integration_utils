import asyncio
# import json
import re
import time
import traceback

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable, Union

from .apihelper import Api
from .errors import MaxError
from .types import Message, CallbackQuery, InputMedia
from .types import UpdateType, InlineKeyboardMarkup
from .util import extract_command, get_text, get_parse_mode, get_edit_message_data
from .core.network.polling import Polling


HandlerFunc = Callable[[Message], None]


@dataclass
class StepHandler:
    callback: Callable
    args: tuple
    kwargs: dict
    timestamp: float


class MaxiBot:
    """
    Главный класс бота
    """
    def __init__(self, token: str):
        """
        Метод инициализации бота
        :param token: Токен бота
        :type token: str
        """
        self.api = Api(token=token)
        self.handlers = {
            "update": [],  # Общие обработчики для всех типов обновлений
            UpdateType.MESSAGE_CREATED: [],
            UpdateType.MESSAGE_CALLBACK: [],
            UpdateType.BOT_STARTED: [],
            UpdateType.MESSAGE_EDITED: [],
            UpdateType.MESSAGE_DELETED: [],
            UpdateType.MESSAGE_CHAT_CREATED: [],
            UpdateType.CHAT_TITLE_CHANGED: [],
        }
        self.message_handlers = []
        self.callback_query_handlers = []
        self.poll = None
        self.is_running = False
        self.count_retries = 10
        self._next_steps: Dict[int, StepHandler] = {}

    @staticmethod
    def _build_handler_dict(handler: HandlerFunc, **filters):
        """
        Функция, которая формирует словарь для добавления в список обработчиков событий (handler)

        :param handler: Description
        :type handler: HandlerFunc
        :param filters: Description
        """
        return {
            'function': handler,
            'filters': {ftype: fvalue for ftype, fvalue in filters.items() if fvalue is not None}
        }

    def polling(self, allowed_updates: Optional[List[str]] = None):
        """
        Функция, которая запускает корутину
        """
        asyncio.run(self.start(allowed_updates=allowed_updates))

    def stop(self):
        """
        Метод останавливает поллинг бота
        """
        if not self.is_running:
            print("Bot is not running")
            return None
        if self.poll:
            self.poll.stop()
        self.is_running = False

    async def start(self, allowed_updates: Optional[List[str]] = None):
        """
        Метод запускает получение обновлений по боту

        :param allowed_updates: Description
        :type allowed_updates: Optional[List[str]]
        """
        if self.is_running:
            print("Bot is already running")
            return None
        self.is_running = True
        self.poll = Polling(api=self.api, allowed_updates=allowed_updates)
        await self.poll.loop(self._process_update)

    # def on(self, update_type: str):
    #     """
    #     Декоратор для регистрации обработчика определенного типа обновлений

    #     :param update_type: Тип обновления (см. UpdateType)
    #     """
    #     def decorator(func: HandlerFunc):
    #         self.handlers.setdefault(update_type, []).append(func)
    #         return func
    #     return decorator

    def message_handler(
        self,
        commands: Optional[List[str]] = None,
        regexp: Optional[str] = None,
        func: Optional[Callable] = None,
        content_types: Optional[List[str]] = None,
        chat_types: Optional[List[str]] = None
    ):
        """
        Декоратор для регистрации обработчика текстовых сообщений по шаблону

        :param pattern: Шаблон текста (точное совпадение или регулярное выражение)
        :type pattern: str
        """
        def decorator(funcs: HandlerFunc):
            handler_dict = self._build_handler_dict(
                funcs,
                commands=commands,
                regexp=regexp,
                func=func,
                content_types=content_types,
                chat_types=chat_types
            )
            self.message_handlers.append(handler_dict)
            return funcs
        return decorator

    def run_handler(self, context: Message, message_handlers: List[Dict]):
        """
        Метод запуска обработчиков событий текстового сообщения

        :param context: Description
        :type context: Context
        """
        for handler in message_handlers:
            if self._check_filters(context=context, handler=handler):
                handler.get("function")(context)
                break

    def _test_filter(self, message_filter: str, filter_value: List, context: Message):
        """
        Метод проверки соответствия сообщения всем фильтрам текстовых сообщений

        :param message_filter: Description
        :type message_filter: str
        :param filter_value: Description
        :type filter_value: List
        :param context: Description
        :type context: Context
        """

        text = context.text
        if message_filter == 'content_types':
            return context.content_type in filter_value
        if message_filter == 'regexp':
            return re.search(filter_value, text, re.IGNORECASE)
        elif message_filter == 'commands':
            return extract_command(text) in filter_value
        elif message_filter == 'chat_types':
            return context.chat.type in filter_value
        elif message_filter == 'func':
            # print("FUUUUUUUUUUUUUUUUUUUUUUUUNCCCCCCCCCCCCCCCCC")
            return filter_value(context)
        return False

    def _check_filters(self, context, handler: Dict):
        """
        Проверка текстового сообщения на фильтры

        :param context: Сообщение
        :type context: Context
        """
        if handler['filters']:
            if isinstance(context, CallbackQuery):
                # Сначала проверяем фильтр по data
                if 'data' in handler['filters']:
                    filter_data = handler['filters']['data']
                    if context.data != filter_data:
                        return False
                func_filter = handler['filters'].get('func')
                if func_filter:
                    try:
                        return func_filter(context)
                    except Exception as e:
                        print(f"Error in filter function: {e}")
                        return False

                return True
            elif isinstance(context, Message):
                for message_filter, filter_value in handler['filters'].items():
                    if filter_value is None:
                        continue
                    if not self._test_filter(message_filter, filter_value, context):
                        return False
                return True
            return False

    def _process_text_message(self, context: Message):
        """
        Обрабатывает входящее сообщение

        :param context: Контекст обновления
        :type context: Context
        """
        # if text.startswith("/"):
        #     print("Command send. Do nothing now))")
        self.run_handler(context=context, message_handlers=self.message_handlers)
        # for pattern, handler in self.message_handlers:
        #     if pattern == text or re.search(pattern, text):
        #         handler(context)

    def _process_update(self, update: Dict[str, Any]):
        """
        Метод для обработки входящего полученного обновления

        :param update: Данные по обновлениям
        :type update: Dict[str, Any]
        """
        try:
            # print("===============\nUPDATE RECEIVED\n===============")
            # print(f"Update type: {update.get('update_type')}")
            # print(f"Full update: {json.dumps(update, indent=2)}")

            update_type = update.get("update_type")
            if update_type == UpdateType.MESSAGE_CREATED and "message" in update.keys() or \
               update_type == UpdateType.BOT_STARTED or update_type == UpdateType.BOT_ADDED or \
               update_type == UpdateType.CHAT_TITLE_CHANGED:
                context = Message(update, self.api)
                if context.from_user.id in self._next_steps:
                    handler = self._next_steps.pop(context.from_user.id)
                    handler.callback(context, *handler.args, **handler.kwargs)
                else:
                    self._process_text_message(context)
            elif update_type == UpdateType.MESSAGE_CALLBACK:
                print("Processing message_callback...")
                if "callback" in update:
                    callback = CallbackQuery(update, self.api)
                    # print(f"Created callback: id={callback.id}, data={callback.data}")
                    self._process_callback_query(callback)
        except Exception:
            print(f"Error while processing update: {traceback.format_exc()}")

    def _check_text_length(self, text):
        """
        Проверки длины строки
        """
        return text is not None and not (len(text) < 4000)

    def register_next_step_handler(self, message: Message, callback: Callable, *args, **kwargs):
        """
        Регистрирует функцию обратного вызова для получения уведомления о поступлении нового сообщения после `message`.

        Предупреждение: Если `callback` используется как лямбда-функция,
        сохранение обработчиков следующего шага работать не будет.

        :param message: Объект сообщения
        :type message: Message
        :param callback: Функция обратного вызова
        :type callback: Callable
        :param args:
        :param kwargs:
        """

        handler = StepHandler(
            callback=callback,
            args=args,
            kwargs=kwargs,
            timestamp=time.time()
        )
        self._next_steps[message.from_user.id] = handler

    def send_photo(
        self,
        chat_id: Union[int, str],
        photo: Union[Any, str],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None
    ):
        """
        Отправляет сообщение с фото

        :param chat_id: Чат, куда надо отправить сообщение
        :type chat_id: Union[int, str]

        :param photo: Объект фото
        :type photo: Union[Any, str]

        :param caption: Текст сообщения под фото
        :type caption: Optional[str]

        :param parse_mode: Разметка сообщения
        :type parse_mode: Optional[str]

        :return: Информация об отправленном сообщении
        :rtype: Dict[str, Any]
        """

        if self._check_text_length(text=caption):
            raise ValueError(f'caption должен быть меньше 4000 символов.\nСейчас их {len(caption)}')
        final_attachments = []
        if isinstance(photo, InputMedia):
            final_attachments.append(photo.to_dict(api=self.api))
        final_attachments.append(InputMedia(media=photo).to_dict(api=self.api))
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)
        return Message(
            update=self.api.send_message(
                chat_id=chat_id,
                text=caption,
                attachments=final_attachments,
                parse_mode=parse_mode
            ),
            api=self.api
        )

    def send_media_group(
        self,
        chat_id: Union[int, str],
        media: list,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None
    ):
        """
        Отправляет сообщение с фото

        :param chat_id: Чат, куда надо отправить сообщение
        :type chat_id: Union[int, str]

        :param photo: Объект фото
        :type photo: Union[Any, str]

        :param caption: Текст сообщения под фото
        :type caption: Optional[str]

        :param parse_mode: Разметка сообщения
        :type parse_mode: Optional[str]

        :return: Информация об отправленном сообщении
        :rtype: Dict[str, Any]
        """

        if self._check_text_length(text=caption):
            raise ValueError(f'caption должен быть меньше 4000 символов.\nСейчас их {len(caption)}')
        final_attachments = []
        for photo in media:
            if isinstance(photo, InputMedia):
                final_attachments.append(photo.to_dict(api=self.api))
            else:
                final_attachments.append(InputMedia(media=photo).to_dict(api=self.api))
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)
        return Message(
            update=self.api.send_message(
                chat_id=chat_id,
                text=caption,
                attachments=final_attachments,
                parse_mode=parse_mode
            ),
            api=self.api
        )

    def send_document(
        self,
        chat_id: Union[int, str],
        document: Union[Any, str],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None,
        visible_file_name: Optional[str] = None
    ):
        """
        Отправляет сообщение с файлом

        :param chat_id: Чат, куда надо отправить сообщение
        :type chat_id: Union[int, str]

        :param document: Объект файла
        :type document: Union[Any, str]

        :param caption: Текст сообщения под фото
        :type caption: Optional[str]

        :param parse_mode: Разметка сообщения
        :type parse_mode: Optional[str]

        :return: Информация об отправленном сообщении
        :rtype: Dict[str, Any]
        """

        if self._check_text_length(text=caption):
            raise ValueError(f'caption должен быть меньше 4000 символов.\nСейчас их {len(caption)}')
        final_attachments = []
        if isinstance(document, InputMedia) and document.type == "file":
            final_attachments.append(document.to_dict(api=self.api))
        else:
            final_attachments.append(
                InputMedia(type="file", media=document).to_dict(api=self.api, file_name=visible_file_name)
            )
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)
        for _ in range(self.count_retries):
            try:
                response = self.api.send_message(
                    chat_id=chat_id,
                    text=caption,
                    attachments=final_attachments,
                    parse_mode=parse_mode.lower() if parse_mode else None
                )
                break
            except MaxError as exc:
                if exc.error_code == "attachment.not.ready":
                    time.sleep(1)
                    continue
                raise
        return Message(update=response, api=self.api)

    def delete_message(
        self,
        chat_id: Union[str, int],
        message_id: str,
    ):
        """
        Метод удаления сообщения `message_id` в чате `chat_id`

        :param chat_id: Айди чата
        :type chat_id: Union[str, int]

        :param message_id: Айди сообщения
        :type message_id: int
        """
        self.api.send_message(msg_id=message_id, method="DELETE")
        return {}

    def edit_message_text(
        self,
        text: str,
        chat_id: Union[str, int],
        message_id: str,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None,
        parse_mode: Union[str, Any] = None
    ):
        """
        Метод изменения текстового сообщения `message_id` в чате `chat_id`

        :param text: Текст, на который надо заменить текущий
        :type text: str

        :param chat_id: Айди чата
        :type chat_id: Union[str, int]

        :param message_id: Айди сообщения
        :type message_id: int

        :return: Информация об отправленном сообщении
        :rtype: Message | {} (не успех)
        """
        final_attachments = []

        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)

        response = self.api.send_message(
            msg_id=message_id,
            text=text,
            method="PUT",
            attachments=final_attachments,
            parse_mode=parse_mode
        )

        if isinstance(response, dict) and response.get("success"):
            timestamp = int(time.time() * 1000)
            message_data = get_edit_message_data(text, chat_id, message_id, final_attachments, timestamp)
            return Message(update=message_data, api=self.api)

        return {}

    def edit_message_media(
        self,
        media: Any,
        chat_id: Union[str, int],
        message_id: str,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None,
        parse_mode: Union[str, Any] = "markdown"
    ):
        """
        Метод изменения медиа сообщения `message_id` в чате `chat_id`

        :param media: Медиа, на которое надо заменить текущее
        :type media: str

        :param chat_id: Айди чата
        :type chat_id: Union[str, int]

        :param message_id: Айди сообщения
        :type message_id: int

        :return: Информация об отправленном сообщении
        :rtype: Message | {} (не успех)
        """
        final_attachments = []
        # if isinstance(media, Photo):
        #     final_attachments.append(media.to_dict())
        if isinstance(media, InputMedia):
            final_attachments.append(media.to_dict(api=self.api))
        else:
            final_attachments.append(InputMedia(media=media).to_dict(api=self.api))
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)
        text = get_text(media=media)
        parse_mode = get_parse_mode(media=media, parse_mode=parse_mode)

        response = self.api.send_message(
            msg_id=message_id,
            text=text,
            method="PUT",
            attachments=final_attachments,
            parse_mode=parse_mode
        )

        if isinstance(response, dict) and response.get("success"):
            timestamp = int(time.time() * 1000)
            message_data = get_edit_message_data(text, chat_id, message_id, final_attachments, timestamp)
            return Message(update=message_data, api=self.api)

        return {}

    def edit_message_reply_markup(
        self,
        chat_id: Union[str, int],
        message_id: str,
        reply_markup: Union[InlineKeyboardMarkup, Any] = None,
        parse_mode: Union[str, Any] = "markdown"
    ):
        """
        Метод изменения клавиатуры сообщения `message_id` в чате `chat_id`

        :param chat_id: Айди чата
        :type chat_id: Union[str, int]

        :param message_id: Айди сообщения
        :type message_id: int

        :param reply_markup: Новая клавиатура
        :type reply_markup: Union[InlineKeyboardMarkup, Any]

        :return: Информация об отправленном сообщении
        :rtype: Message | {} (не успех)
        """
        final_attachments = []
        msg: Message = self.get_message(message_id=message_id)
        if msg.photo:
            final_attachments.append(msg.photo.to_dict())
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)

        response = self.api.send_message(
            msg_id=message_id,
            method="PUT",
            attachments=final_attachments,
            parse_mode=parse_mode
        )

        if isinstance(response, dict) and response.get("success"):
            timestamp = int(time.time() * 1000)
            message_data = get_edit_message_data(None, chat_id, message_id, final_attachments, timestamp)
            return Message(update=message_data, api=self.api)

        return None

    def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        reply_markup: Optional[Any] = None,
        parse_mode: str = "markdown",
        notify: bool = True,
        link: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Отправляет ответ на текущее сообщение/обновление

        :param text: Текст сообщения
        :type text:

        :param attachments: Вложения сообщения
        :type attachments:

        :param keyboard: Объект клавиатуры (будет добавлен к attachments)
        :type keyboard:

        :return: Информация об отправленном сообщении
        :rtype: Message
        """
        if self._check_text_length(text=text):
            raise ValueError(f'text должен быть меньше 4000 символов\nСейчас их {len(text)}')
        if isinstance(chat_id, int):
            chat_id = str(chat_id)

        final_attachments = attachments.copy() if attachments else []

        # Если передана клавиатура, добавляем её как вложение
        if reply_markup:
            if hasattr(reply_markup, 'to_attachment'):
                final_attachments.append(reply_markup.to_attachment())
            else:
                final_attachments.append(reply_markup)

        return Message(
            update=self.api.send_message(
                chat_id=chat_id,
                text=text,
                attachments=final_attachments,
                parse_mode=parse_mode.lower(),
                notify=notify,
                link=link,
            ),
            api=self.api
        )

    def get_message(self, message_id: str):
        """
        Метод получения сообщения по айди

        :param message_id: Айди сообщения
        :type message_id: str
        """
        msg = self.api.get_message(msg_id=message_id)
        update = {"update_type": "get_message"}
        update["message"] = msg
        return Message(update=update, api=self.api)

    def get_me(self):
        """
        Метод получения информации о боте
        """
        info = self.api.get_bot_info()
        return info

    def leave_chat(self, chat_id: str):
        """
        Метод получения информации о боте
        """
        return self.api.leave_chat(chat_id=chat_id)

    def callback_query_handler(self, data=None, **kwargs):
        """
        Декоратор для регистрации обработчиков callback-запросов от inline-кнопок

        :param data: Данные кнопки для фильтрации (callback_data)
        :type data: Optional[str]

        :param kwargs: Дополнительные фильтры для обработчика

        :return: Декоратор для функции-обработчика
        :rtype: Callable

        Пример использования:
        @bot.callback_query_handler(func=lambda cb: cb.data == "yes")
        def yes_handler(callback):
            callback.answer(notification="да да")
        """
        def decorator(handler):
            filters = {}
            if data:
                filters['data'] = data
            filters.update(kwargs)

            handler_dict = self._build_handler_dict(handler, **filters)
            self.callback_query_handlers.append(handler_dict)
            return handler

        return decorator

    def add_callback_query_handler(self, handler_dict):
        """
        Добавляет обработчик callback-запросов напрямую

        :param handler_dict: Словарь с описанием обработчика
        :type handler_dict: Dict[str, Any]

        :return: None
        """
        self.callback_query_handlers.append(handler_dict)

    def _process_callback_query(self, callback: CallbackQuery):
        """
        Обрабатывает входящий callback-запрос
        Метод ищет подходящий обработчик среди зарегистрированных и вызывает первый соответствующий фильтрам

        :param callback: Объект callback-запроса
        :type callback: CallbackQuery

        :return: None
        """
        # print(f"Processing callback: id={callback.id}, data={callback.data}")
        # print(f"Callback user: {callback.from_user}")

        for handler in self.callback_query_handlers:
            # print(f"Checking handler with filters: {handler['filters']}")
            if self._check_filters(callback, handler):
                # print("Handler matched! Calling function...")
                handler["function"](callback)
                break
        else:
            print("No matching handler found for callback")
