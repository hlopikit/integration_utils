#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2025
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].
"""This module contains an object that represents a Telegram MessageReaction Update."""
import datetime as dtm
from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional

from . chat import Chat
from . import TelegramObject
from . reaction import ReactionType, ReactionCount
from . user import User
from . utils.helpers import from_timestamp

from . utils.types import JSONDict

if TYPE_CHECKING:
    from . import Bot


class MessageReactionCountUpdated(TelegramObject):
    """This class represents reaction changes on a message with anonymous reactions.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if the :attr:`chat`, :attr:`message_id`, :attr:`date` and :attr:`reactions`
    is equal.

    .. versionadded:: 20.8

    Args:
        chat (:class:`telegram.Chat`): The chat containing the message.
        message_id (:obj:`int`): Unique message identifier inside the chat.
        date (:class:`datetime.datetime`): Date of the change in Unix time
            |datetime_localization|
        reactions (Sequence[:class:`telegram.ReactionCount`]): List of reactions that are present
            on the message

    Attributes:
        chat (:class:`telegram.Chat`): The chat containing the message.
        message_id (:obj:`int`): Unique message identifier inside the chat.
        date (:class:`datetime.datetime`): Date of the change in Unix time
            |datetime_localization|
        reactions (tuple[:class:`telegram.ReactionCount`]): List of reactions that are present on
            the message
    """

    __slots__ = (
        "chat",
        "date",
        "message_id",
        "reactions",
        "_id_attrs"
    )

    def __init__(
        self,
        chat: Chat,
        message_id: int,
        date: dtm.datetime,
        reactions: Sequence[ReactionCount],
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        self.chat: Chat = chat
        self.message_id: int = message_id
        self.date: dtm.datetime = date
        self.reactions: tuple[ReactionCount, ...] = tuple(reactions) if reactions else ()

        self._id_attrs = (self.chat, self.message_id, self.date, self.reactions)

    @classmethod
    def de_json(cls, data: JSONDict, bot: Optional["Bot"] = None) -> Optional["MessageReactionCountUpdated"]:
        """See :meth:`telegram.TelegramObject.de_json`."""
        data = cls._parse_data(data)
        if not data:
            return None

        data["date"] = from_timestamp(data.get("date"))
        data["chat"] = Chat.de_json(data.get('chat'), bot)
        data["reactions"] = ReactionCount.de_list(data.get("reactions"), bot)

        return cls(**data)


class MessageReactionUpdated(TelegramObject):
    """This class represents a change of a reaction on a message performed by a user.

    Objects of this class are comparable in terms of equality. Two objects of this class are
    considered equal, if the :attr:`chat`, :attr:`message_id`, :attr:`date`, :attr:`old_reaction`
    and :attr:`new_reaction` is equal.

    .. versionadded:: 20.8

    Args:
        chat (:class:`telegram.Chat`): The chat containing the message.
        message_id (:obj:`int`): Unique message identifier inside the chat.
        date (:class:`datetime.datetime`): Date of the change in Unix time.
            |datetime_localization|
        old_reaction (Sequence[:class:`telegram.ReactionType`]): Previous list of reaction types
            that were set by the user.
        new_reaction (Sequence[:class:`telegram.ReactionType`]): New list of reaction types that
            were set by the user.
        user (:class:`telegram.User`, optional): The user that changed the reaction, if the user
            isn't anonymous.
        actor_chat (:class:`telegram.Chat`, optional): The chat on behalf of which the reaction was
            changed, if the user is anonymous.

    Attributes:
        chat (:class:`telegram.Chat`): The chat containing the message.
        message_id (:obj:`int`): Unique message identifier inside the chat.
        date (:class:`datetime.datetime`): Date of the change in Unix time.
            |datetime_localization|
        old_reaction (tuple[:class:`telegram.ReactionType`]): Previous list of reaction types
            that were set by the user.
        new_reaction (tuple[:class:`telegram.ReactionType`]): New list of reaction types that
            were set by the user.
        user (:class:`telegram.User`): Optional. The user that changed the reaction, if the user
            isn't anonymous.
        actor_chat (:class:`telegram.Chat`): Optional. The chat on behalf of which the reaction was
            changed, if the user is anonymous.
    """

    __slots__ = (
        "actor_chat",
        "chat",
        "date",
        "message_id",
        "new_reaction",
        "old_reaction",
        "user",
        "_id_attrs",
    )

    def __init__(
        self,
        chat: Chat,
        message_id: int,
        date: dtm.datetime,
        old_reaction: Sequence[ReactionType],
        new_reaction: Sequence[ReactionType],
        user: Optional[User] = None,
        actor_chat: Optional[Chat] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):

        self.chat: Chat = chat
        self.message_id: int = message_id
        self.date: dtm.datetime = date

        self.old_reaction: tuple[ReactionType, ...] = tuple(old_reaction) if old_reaction else ()
        self.new_reaction: tuple[ReactionType, ...] = tuple(new_reaction) if new_reaction else ()

        # Optional
        self.user: Optional[User] = user
        self.actor_chat: Optional[Chat] = actor_chat

        self._id_attrs = (
            self.chat,
            self.message_id,
            self.date,
            self.old_reaction,
            self.new_reaction,
        )

    @classmethod
    def de_json(cls, data: JSONDict, bot: Optional["Bot"] = None) -> Optional["MessageReactionUpdated"]:
        """See :meth:`telegram.TelegramObject.de_json`."""
        data = cls._parse_data(data)
        if not data:
            return None

        data["date"] = from_timestamp(data.get("date"))
        data['chat'] = Chat.de_json(data.get('chat'), bot)
        data["old_reaction"] = ReactionType.de_list(data.get("old_reaction"), bot)
        data["new_reaction"] = ReactionType.de_list(data.get("new_reaction"), bot)
        data['user'] = User.de_json(data.get('user'), bot)
        data['actor_chat'] = Chat.de_json(data.get('actor_chat'), bot)

        return cls(**data)
