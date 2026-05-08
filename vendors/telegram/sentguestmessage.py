#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
#
"""This module contains an object that represents a Telegram Sent Guest Message."""

from typing import Any

from . import TelegramObject


class SentGuestMessage(TelegramObject):
    """
    1) Описывает ответ guest-бота, отправленный через `answerGuestQuery`.
    2) Используется в `telegram.Bot.answer_guest_query()`, чтобы результат нового Bot API 10.0 выглядел так же типизированно, как и остальные методы vendor-клиента.
    """

    __slots__ = ("inline_message_id",)

    def __init__(self, inline_message_id: str = None, **_kwargs: Any):
        self.inline_message_id = inline_message_id
        self._id_attrs = (self.inline_message_id,)
