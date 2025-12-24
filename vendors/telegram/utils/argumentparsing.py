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
"""This module contains helper functions related to parsing arguments for classes and methods.

Warning:
    Contents of this module are intended to be used internally by the library and *not* by the
    user. Changes to this module are not considered breaking changes and may not be documented in
    the changelog.
"""

from typing import TYPE_CHECKING, Optional, TypeVar

from .. import TelegramObject
from ..utils.types import JSONDict

if TYPE_CHECKING:
    from .. import Bot

Tele_co = TypeVar("Tele_co", bound=TelegramObject, covariant=True)


def de_json_optional(
        data: Optional[JSONDict], cls: type[Tele_co], bot: Optional["Bot"]
) -> Optional[Tele_co]:
    """Wrapper around TO.de_json that returns None if data is None."""
    if data is None:
        return None

    return cls.de_json(data, bot)
