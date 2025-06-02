# python-telegram-bot - a Python interface to the Telegram Bot API
# Copyright (C) 2015-2022
# by the python-telegram-bot contributors <devs@python-telegram-bot.org>
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
"""Constants in the Telegram network.

The following constants were extracted from the
`Telegram Bots FAQ <https://core.telegram.org/bots/faq>`_ and
`Telegram Bots API <https://core.telegram.org/bots/api>`_.

Attributes:
    BOT_API_VERSION (:obj:`str`): `6.3`. Telegram Bot API version supported by this
        version of `python-telegram-bot`. Also available as ``telegram.bot_api_version``.

        .. versionadded:: 13.4
    MAX_MESSAGE_LENGTH (:obj:`int`): 4096
    MAX_CAPTION_LENGTH (:obj:`int`): 1024
    SUPPORTED_WEBHOOK_PORTS (List[:obj:`int`]): [443, 80, 88, 8443]
    MAX_FILESIZE_DOWNLOAD (:obj:`int`): In bytes (20MB)
    MAX_FILESIZE_UPLOAD (:obj:`int`): In bytes (50MB)
    MAX_PHOTOSIZE_UPLOAD (:obj:`int`): In bytes (10MB)
    MAX_MESSAGES_PER_SECOND_PER_CHAT (:obj:`int`): `1`. Telegram may allow short bursts that go
        over this limit, but eventually you'll begin receiving 429 errors.
    MAX_MESSAGES_PER_SECOND (:obj:`int`): 30
    MAX_MESSAGES_PER_MINUTE_PER_GROUP (:obj:`int`): 20
    MAX_INLINE_QUERY_RESULTS (:obj:`int`): 50
    MAX_ANSWER_CALLBACK_QUERY_TEXT_LENGTH (:obj:`int`): 200

        .. versionadded:: 13.2

The following constant have been found by experimentation:

Attributes:
    MAX_MESSAGE_ENTITIES (:obj:`int`): 100 (Beyond this cap telegram will simply ignore further
        formatting styles)
    ANONYMOUS_ADMIN_ID (:obj:`int`): ``1087968824`` (User id in groups for anonymous admin)
    SERVICE_CHAT_ID (:obj:`int`): ``777000`` (Telegram service chat, that also acts as sender of
        channel posts forwarded to discussion groups)
    FAKE_CHANNEL_ID (:obj:`int`): ``136817688`` (User id in groups when message is sent on behalf
        of a channel).

        .. versionadded:: 13.9

The following constants are related to specific classes and are also available
as attributes of those classes:

:class:`telegram.Chat`:

Attributes:
    CHAT_PRIVATE (:obj:`str`): ``'private'``
    CHAT_GROUP (:obj:`str`): ``'group'``
    CHAT_SUPERGROUP (:obj:`str`): ``'supergroup'``
    CHAT_CHANNEL (:obj:`str`): ``'channel'``
    CHAT_SENDER (:obj:`str`): ``'sender'``. Only relevant for
        :attr:`telegram.InlineQuery.chat_type`.

        .. versionadded:: 13.5

:class:`telegram.ChatAction`:

Attributes:
    CHATACTION_FIND_LOCATION (:obj:`str`): ``'find_location'``
    CHATACTION_RECORD_AUDIO (:obj:`str`): ``'record_audio'``

        .. deprecated:: 13.5
           Deprecated by Telegram. Use :const:`CHATACTION_RECORD_VOICE` instead.
    CHATACTION_RECORD_VOICE (:obj:`str`): ``'record_voice'``

        .. versionadded:: 13.5
    CHATACTION_RECORD_VIDEO (:obj:`str`): ``'record_video'``
    CHATACTION_RECORD_VIDEO_NOTE (:obj:`str`): ``'record_video_note'``
    CHATACTION_TYPING (:obj:`str`): ``'typing'``
    CHATACTION_UPLOAD_AUDIO (:obj:`str`): ``'upload_audio'``

        .. deprecated:: 13.5
           Deprecated by Telegram. Use :const:`CHATACTION_UPLOAD_VOICE` instead.
    CHATACTION_UPLOAD_VOICE (:obj:`str`): ``'upload_voice'``

        .. versionadded:: 13.5
    CHATACTION_UPLOAD_DOCUMENT (:obj:`str`): ``'upload_document'``
    CHATACTION_CHOOSE_STICKER (:obj:`str`): ``'choose_sticker'``

        .. versionadded:: 13.8
    CHATACTION_UPLOAD_PHOTO (:obj:`str`): ``'upload_photo'``
    CHATACTION_UPLOAD_VIDEO (:obj:`str`): ``'upload_video'``
    CHATACTION_UPLOAD_VIDEO_NOTE (:obj:`str`): ``'upload_video_note'``

:class:`telegram.ChatMember`:

Attributes:
    CHATMEMBER_ADMINISTRATOR (:obj:`str`): ``'administrator'``
    CHATMEMBER_CREATOR (:obj:`str`): ``'creator'``
    CHATMEMBER_KICKED (:obj:`str`): ``'kicked'``
    CHATMEMBER_LEFT (:obj:`str`): ``'left'``
    CHATMEMBER_MEMBER (:obj:`str`): ``'member'``
    CHATMEMBER_RESTRICTED (:obj:`str`): ``'restricted'``

:class:`telegram.Dice`:

Attributes:
    DICE_DICE (:obj:`str`): ``'🎲'``
    DICE_DARTS (:obj:`str`): ``'🎯'``
    DICE_BASKETBALL (:obj:`str`): ``'🏀'``
    DICE_FOOTBALL (:obj:`str`): ``'⚽'``
    DICE_SLOT_MACHINE (:obj:`str`): ``'🎰'``
    DICE_BOWLING (:obj:`str`): ``'🎳'``

        .. versionadded:: 13.4
    DICE_ALL_EMOJI (List[:obj:`str`]): List of all supported base emoji.

        .. versionchanged:: 13.4
            Added :attr:`DICE_BOWLING`

:class:`telegram.MessageEntity`:

Attributes:
    MESSAGEENTITY_MENTION (:obj:`str`): ``'mention'``
    MESSAGEENTITY_HASHTAG (:obj:`str`): ``'hashtag'``
    MESSAGEENTITY_CASHTAG (:obj:`str`): ``'cashtag'``
    MESSAGEENTITY_PHONE_NUMBER (:obj:`str`): ``'phone_number'``
    MESSAGEENTITY_BOT_COMMAND (:obj:`str`): ``'bot_command'``
    MESSAGEENTITY_URL (:obj:`str`): ``'url'``
    MESSAGEENTITY_EMAIL (:obj:`str`): ``'email'``
    MESSAGEENTITY_BOLD (:obj:`str`): ``'bold'``
    MESSAGEENTITY_ITALIC (:obj:`str`): ``'italic'``
    MESSAGEENTITY_CODE (:obj:`str`): ``'code'``
    MESSAGEENTITY_PRE (:obj:`str`): ``'pre'``
    MESSAGEENTITY_TEXT_LINK (:obj:`str`): ``'text_link'``
    MESSAGEENTITY_TEXT_MENTION (:obj:`str`): ``'text_mention'``
    MESSAGEENTITY_UNDERLINE (:obj:`str`): ``'underline'``
    MESSAGEENTITY_STRIKETHROUGH (:obj:`str`): ``'strikethrough'``
    MESSAGEENTITY_SPOILER (:obj:`str`): ``'spoiler'``

        .. versionadded:: 13.10
    MESSAGEENTITY_CUSTOM_EMOJI (:obj:`str`): ``'custom_emoji'``

        .. versionadded:: 13.14
    MESSAGEENTITY_ALL_TYPES (List[:obj:`str`]): List of all the types of message entity.

:class:`telegram.ParseMode`:

Attributes:
    PARSEMODE_MARKDOWN (:obj:`str`): ``'Markdown'``
    PARSEMODE_MARKDOWN_V2 (:obj:`str`): ``'MarkdownV2'``
    PARSEMODE_HTML (:obj:`str`): ``'HTML'``

:class:`telegram.Poll`:

Attributes:
    POLL_REGULAR (:obj:`str`): ``'regular'``
    POLL_QUIZ (:obj:`str`): ``'quiz'``
    MAX_POLL_QUESTION_LENGTH (:obj:`int`): 300
    MAX_POLL_OPTION_LENGTH (:obj:`int`): 100
:class:`telegram.Sticker`:

Attributes:

    STICKER_REGULAR (:obj:`str`)= ``'regular'``

        .. versionadded:: 13.14
    STICKER_MASK (:obj:`str`) = ``'mask'``

        .. versionadded:: 13.14
    STICKER_CUSTOM_EMOJI (:obj:`str`) = ``'custom_emoji'``

        .. versionadded:: 13.14

:class:`telegram.MaskPosition`:

Attributes:
    STICKER_FOREHEAD (:obj:`str`): ``'forehead'``
    STICKER_EYES (:obj:`str`): ``'eyes'``
    STICKER_MOUTH (:obj:`str`): ``'mouth'``
    STICKER_CHIN (:obj:`str`): ``'chin'``

:class:`telegram.Update`:

Attributes:
    UPDATE_MESSAGE (:obj:`str`): ``'message'``

        .. versionadded:: 13.5
    UPDATE_EDITED_MESSAGE (:obj:`str`): ``'edited_message'``

        .. versionadded:: 13.5
    UPDATE_CHANNEL_POST (:obj:`str`): ``'channel_post'``

        .. versionadded:: 13.5
    UPDATE_EDITED_CHANNEL_POST (:obj:`str`): ``'edited_channel_post'``

        .. versionadded:: 13.5
    UPDATE_INLINE_QUERY (:obj:`str`): ``'inline_query'``

        .. versionadded:: 13.5
    UPDATE_CHOSEN_INLINE_RESULT (:obj:`str`): ``'chosen_inline_result'``

        .. versionadded:: 13.5
    UPDATE_CALLBACK_QUERY (:obj:`str`): ``'callback_query'``

        .. versionadded:: 13.5
    UPDATE_SHIPPING_QUERY (:obj:`str`): ``'shipping_query'``

        .. versionadded:: 13.5
    UPDATE_PRE_CHECKOUT_QUERY (:obj:`str`): ``'pre_checkout_query'``

        .. versionadded:: 13.5
    UPDATE_POLL (:obj:`str`): ``'poll'``

        .. versionadded:: 13.5
    UPDATE_POLL_ANSWER (:obj:`str`): ``'poll_answer'``

        .. versionadded:: 13.5
    UPDATE_MY_CHAT_MEMBER (:obj:`str`): ``'my_chat_member'``

        .. versionadded:: 13.5
    UPDATE_CHAT_MEMBER (:obj:`str`): ``'chat_member'``

        .. versionadded:: 13.5
    UPDATE_CHAT_JOIN_REQUEST (:obj:`str`): ``'chat_join_request'``

        .. versionadded:: 13.8
    UPDATE_ALL_TYPES (List[:obj:`str`]): List of all update types.

        .. versionadded:: 13.5
        .. versionchanged:: 13.8

:class:`telegram.BotCommandScope`:

Attributes:
    BOT_COMMAND_SCOPE_DEFAULT (:obj:`str`): ``'default'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_ALL_PRIVATE_CHATS (:obj:`str`): ``'all_private_chats'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_ALL_GROUP_CHATS (:obj:`str`): ``'all_group_chats'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_ALL_CHAT_ADMINISTRATORS (:obj:`str`): ``'all_chat_administrators'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_CHAT (:obj:`str`): ``'chat'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_CHAT_ADMINISTRATORS (:obj:`str`): ``'chat_administrators'``

        ..versionadded:: 13.7
    BOT_COMMAND_SCOPE_CHAT_MEMBER (:obj:`str`): ``'chat_member'``

        ..versionadded:: 13.7

"""
from typing import List

from integration_utils.vendors.telegram.utils.enum import StringEnum

BOT_API_VERSION: str = '6.3'
MAX_MESSAGE_LENGTH: int = 4096
MAX_CAPTION_LENGTH: int = 1024
ANONYMOUS_ADMIN_ID: int = 1087968824
SERVICE_CHAT_ID: int = 777000
FAKE_CHANNEL_ID: int = 136817688

# constants above this line are tested

SUPPORTED_WEBHOOK_PORTS: List[int] = [443, 80, 88, 8443]
MAX_FILESIZE_DOWNLOAD: int = int(20e6)  # (20MB)
MAX_FILESIZE_UPLOAD: int = int(50e6)  # (50MB)
MAX_PHOTOSIZE_UPLOAD: int = int(10e6)  # (10MB)
MAX_MESSAGES_PER_SECOND_PER_CHAT: int = 1
MAX_MESSAGES_PER_SECOND: int = 30
MAX_MESSAGES_PER_MINUTE_PER_GROUP: int = 20
MAX_MESSAGE_ENTITIES: int = 100
MAX_INLINE_QUERY_RESULTS: int = 50
MAX_ANSWER_CALLBACK_QUERY_TEXT_LENGTH: int = 200

CHAT_SENDER: str = 'sender'
CHAT_PRIVATE: str = 'private'
CHAT_GROUP: str = 'group'
CHAT_SUPERGROUP: str = 'supergroup'
CHAT_CHANNEL: str = 'channel'

CHATACTION_FIND_LOCATION: str = 'find_location'
CHATACTION_RECORD_AUDIO: str = 'record_audio'
CHATACTION_RECORD_VOICE: str = 'record_voice'
CHATACTION_RECORD_VIDEO: str = 'record_video'
CHATACTION_RECORD_VIDEO_NOTE: str = 'record_video_note'
CHATACTION_TYPING: str = 'typing'
CHATACTION_UPLOAD_AUDIO: str = 'upload_audio'
CHATACTION_UPLOAD_VOICE: str = 'upload_voice'
CHATACTION_UPLOAD_DOCUMENT: str = 'upload_document'
CHATACTION_CHOOSE_STICKER: str = 'choose_sticker'
CHATACTION_UPLOAD_PHOTO: str = 'upload_photo'
CHATACTION_UPLOAD_VIDEO: str = 'upload_video'
CHATACTION_UPLOAD_VIDEO_NOTE: str = 'upload_video_note'

CHATMEMBER_ADMINISTRATOR: str = 'administrator'
CHATMEMBER_CREATOR: str = 'creator'
CHATMEMBER_KICKED: str = 'kicked'
CHATMEMBER_LEFT: str = 'left'
CHATMEMBER_MEMBER: str = 'member'
CHATMEMBER_RESTRICTED: str = 'restricted'

DICE_DICE: str = '🎲'
DICE_DARTS: str = '🎯'
DICE_BASKETBALL: str = '🏀'
DICE_FOOTBALL: str = '⚽'
DICE_SLOT_MACHINE: str = '🎰'
DICE_BOWLING: str = '🎳'
DICE_ALL_EMOJI: List[str] = [
    DICE_DICE,
    DICE_DARTS,
    DICE_BASKETBALL,
    DICE_FOOTBALL,
    DICE_SLOT_MACHINE,
    DICE_BOWLING,
]

MESSAGEENTITY_MENTION: str = 'mention'
MESSAGEENTITY_HASHTAG: str = 'hashtag'
MESSAGEENTITY_CASHTAG: str = 'cashtag'
MESSAGEENTITY_PHONE_NUMBER: str = 'phone_number'
MESSAGEENTITY_BOT_COMMAND: str = 'bot_command'
MESSAGEENTITY_URL: str = 'url'
MESSAGEENTITY_EMAIL: str = 'email'
MESSAGEENTITY_BOLD: str = 'bold'
MESSAGEENTITY_ITALIC: str = 'italic'
MESSAGEENTITY_CODE: str = 'code'
MESSAGEENTITY_PRE: str = 'pre'
MESSAGEENTITY_TEXT_LINK: str = 'text_link'
MESSAGEENTITY_TEXT_MENTION: str = 'text_mention'
MESSAGEENTITY_UNDERLINE: str = 'underline'
MESSAGEENTITY_STRIKETHROUGH: str = 'strikethrough'
MESSAGEENTITY_SPOILER: str = 'spoiler'
MESSAGEENTITY_CUSTOM_EMOJI: str = 'custom_emoji'
MESSAGEENTITY_ALL_TYPES: List[str] = [
    MESSAGEENTITY_MENTION,
    MESSAGEENTITY_HASHTAG,
    MESSAGEENTITY_CASHTAG,
    MESSAGEENTITY_PHONE_NUMBER,
    MESSAGEENTITY_BOT_COMMAND,
    MESSAGEENTITY_URL,
    MESSAGEENTITY_EMAIL,
    MESSAGEENTITY_BOLD,
    MESSAGEENTITY_ITALIC,
    MESSAGEENTITY_CODE,
    MESSAGEENTITY_PRE,
    MESSAGEENTITY_TEXT_LINK,
    MESSAGEENTITY_TEXT_MENTION,
    MESSAGEENTITY_UNDERLINE,
    MESSAGEENTITY_STRIKETHROUGH,
    MESSAGEENTITY_SPOILER,
    MESSAGEENTITY_CUSTOM_EMOJI,
]

PARSEMODE_MARKDOWN: str = 'Markdown'
PARSEMODE_MARKDOWN_V2: str = 'MarkdownV2'
PARSEMODE_HTML: str = 'HTML'

POLL_REGULAR: str = 'regular'
POLL_QUIZ: str = 'quiz'
MAX_POLL_QUESTION_LENGTH: int = 300
MAX_POLL_OPTION_LENGTH: int = 100

STICKER_REGULAR: str = "regular"
STICKER_MASK: str = "mask"
STICKER_CUSTOM_EMOJI: str = "custom_emoji"

STICKER_FOREHEAD: str = 'forehead'
STICKER_EYES: str = 'eyes'
STICKER_MOUTH: str = 'mouth'
STICKER_CHIN: str = 'chin'

UPDATE_MESSAGE = 'message'
UPDATE_EDITED_MESSAGE = 'edited_message'
UPDATE_CHANNEL_POST = 'channel_post'
UPDATE_EDITED_CHANNEL_POST = 'edited_channel_post'
UPDATE_INLINE_QUERY = 'inline_query'
UPDATE_CHOSEN_INLINE_RESULT = 'chosen_inline_result'
UPDATE_CALLBACK_QUERY = 'callback_query'
UPDATE_SHIPPING_QUERY = 'shipping_query'
UPDATE_PRE_CHECKOUT_QUERY = 'pre_checkout_query'
UPDATE_POLL = 'poll'
UPDATE_POLL_ANSWER = 'poll_answer'
UPDATE_MY_CHAT_MEMBER = 'my_chat_member'
UPDATE_CHAT_MEMBER = 'chat_member'
UPDATE_CHAT_JOIN_REQUEST = 'chat_join_request'
UPDATE_ALL_TYPES = [
    UPDATE_MESSAGE,
    UPDATE_EDITED_MESSAGE,
    UPDATE_CHANNEL_POST,
    UPDATE_EDITED_CHANNEL_POST,
    UPDATE_INLINE_QUERY,
    UPDATE_CHOSEN_INLINE_RESULT,
    UPDATE_CALLBACK_QUERY,
    UPDATE_SHIPPING_QUERY,
    UPDATE_PRE_CHECKOUT_QUERY,
    UPDATE_POLL,
    UPDATE_POLL_ANSWER,
    UPDATE_MY_CHAT_MEMBER,
    UPDATE_CHAT_MEMBER,
    UPDATE_CHAT_JOIN_REQUEST,
]

BOT_COMMAND_SCOPE_DEFAULT = 'default'
BOT_COMMAND_SCOPE_ALL_PRIVATE_CHATS = 'all_private_chats'
BOT_COMMAND_SCOPE_ALL_GROUP_CHATS = 'all_group_chats'
BOT_COMMAND_SCOPE_ALL_CHAT_ADMINISTRATORS = 'all_chat_administrators'
BOT_COMMAND_SCOPE_CHAT = 'chat'
BOT_COMMAND_SCOPE_CHAT_ADMINISTRATORS = 'chat_administrators'
BOT_COMMAND_SCOPE_CHAT_MEMBER = 'chat_member'

MENU_BUTTON_COMMANDS = 'commands'
MENU_BUTTON_WEB_APP = 'web_app'
MENU_BUTTON_DEFAULT = 'default'

BOT_ALLOWED_REACTIONS = {"👍", "👎", "❤", "🤡", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌",
                         "🕊", "🤡", "🥱", "🥴", "😍", "🐳", "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾",
                         "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄",
                         "☃", "💅", "🤪", "🗿", "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀", "😡"}


class ReactionType(StringEnum):
    """This enum contains the available types of :class:`telegram.ReactionType`. The enum
    members of this enumeration are instances of :class:`str` and can be treated as such.

    .. versionadded:: 20.8
    """

    __slots__ = ()

    EMOJI = "emoji"
    """:obj:`str`: A :class:`telegram.ReactionType` with a normal emoji."""
    CUSTOM_EMOJI = "custom_emoji"
    """:obj:`str`: A :class:`telegram.ReactionType` with a custom emoji."""
    PAID = "paid"
    """:obj:`str`: A :class:`telegram.ReactionType` with a paid reaction.

    .. versionadded:: 21.5
    """


class ReactionEmoji(StringEnum):
    """This enum contains the available emojis of :class:`telegram.ReactionTypeEmoji`. The enum
    members of this enumeration are instances of :class:`str` and can be treated as such.

    .. versionadded:: 20.8
    """

    __slots__ = ()

    THUMBS_UP = "👍"
    """:obj:`str`: Thumbs Up"""
    THUMBS_DOWN = "👎"
    """:obj:`str`: Thumbs Down"""
    RED_HEART = "❤"
    """:obj:`str`: Red Heart"""
    FIRE = "🔥"
    """:obj:`str`: Fire"""
    SMILING_FACE_WITH_HEARTS = "🥰"
    """:obj:`str`: Smiling Face with Hearts"""
    CLAPPING_HANDS = "👏"
    """:obj:`str`: Clapping Hands"""
    GRINNING_FACE_WITH_SMILING_EYES = "😁"
    """:obj:`str`: Grinning face with smiling eyes"""
    THINKING_FACE = "🤔"
    """:obj:`str`: Thinking face"""
    SHOCKED_FACE_WITH_EXPLODING_HEAD = "🤯"
    """:obj:`str`: Shocked face with exploding head"""
    FACE_SCREAMING_IN_FEAR = "😱"
    """:obj:`str`: Face screaming in fear"""
    SERIOUS_FACE_WITH_SYMBOLS_COVERING_MOUTH = "🤬"
    """:obj:`str`: Serious face with symbols covering mouth"""
    CRYING_FACE = "😢"
    """:obj:`str`: Crying face"""
    PARTY_POPPER = "🎉"
    """:obj:`str`: Party popper"""
    GRINNING_FACE_WITH_STAR_EYES = "🤩"
    """:obj:`str`: Grinning face with star eyes"""
    FACE_WITH_OPEN_MOUTH_VOMITING = "🤮"
    """:obj:`str`: Face with open mouth vomiting"""
    PILE_OF_POO = "💩"
    """:obj:`str`: Pile of poo"""
    PERSON_WITH_FOLDED_HANDS = "🙏"
    """:obj:`str`: Person with folded hands"""
    OK_HAND_SIGN = "👌"
    """:obj:`str`: Ok hand sign"""
    DOVE_OF_PEACE = "🕊"
    """:obj:`str`: Dove of peace"""
    CLOWN_FACE = "🤡"
    """:obj:`str`: Clown face"""
    YAWNING_FACE = "🥱"
    """:obj:`str`: Yawning face"""
    FACE_WITH_UNEVEN_EYES_AND_WAVY_MOUTH = "🥴"
    """:obj:`str`: Face with uneven eyes and wavy mouth"""
    SMILING_FACE_WITH_HEART_SHAPED_EYES = "😍"
    """:obj:`str`: Smiling face with heart-shaped eyes"""
    SPOUTING_WHALE = "🐳"
    """:obj:`str`: Spouting whale"""
    HEART_ON_FIRE = "❤️‍🔥"
    """:obj:`str`: Heart on fire"""
    NEW_MOON_WITH_FACE = "🌚"
    """:obj:`str`: New moon with face"""
    HOT_DOG = "🌭"
    """:obj:`str`: Hot dog"""
    HUNDRED_POINTS_SYMBOL = "💯"
    """:obj:`str`: Hundred points symbol"""
    ROLLING_ON_THE_FLOOR_LAUGHING = "🤣"
    """:obj:`str`: Rolling on the floor laughing"""
    HIGH_VOLTAGE_SIGN = "⚡"
    """:obj:`str`: High voltage sign"""
    BANANA = "🍌"
    """:obj:`str`: Banana"""
    TROPHY = "🏆"
    """:obj:`str`: Trophy"""
    BROKEN_HEART = "💔"
    """:obj:`str`: Broken heart"""
    FACE_WITH_ONE_EYEBROW_RAISED = "🤨"
    """:obj:`str`: Face with one eyebrow raised"""
    NEUTRAL_FACE = "😐"
    """:obj:`str`: Neutral face"""
    STRAWBERRY = "🍓"
    """:obj:`str`: Strawberry"""
    BOTTLE_WITH_POPPING_CORK = "🍾"
    """:obj:`str`: Bottle with popping cork"""
    KISS_MARK = "💋"
    """:obj:`str`: Kiss mark"""
    REVERSED_HAND_WITH_MIDDLE_FINGER_EXTENDED = "🖕"
    """:obj:`str`: Reversed hand with middle finger extended"""
    SMILING_FACE_WITH_HORNS = "😈"
    """:obj:`str`: Smiling face with horns"""
    SLEEPING_FACE = "😴"
    """:obj:`str`: Sleeping face"""
    LOUDLY_CRYING_FACE = "😭"
    """:obj:`str`: Loudly crying face"""
    NERD_FACE = "🤓"
    """:obj:`str`: Nerd face"""
    GHOST = "👻"
    """:obj:`str`: Ghost"""
    MAN_TECHNOLOGIST = "👨‍💻"
    """:obj:`str`: Man Technologist"""
    EYES = "👀"
    """:obj:`str`: Eyes"""
    JACK_O_LANTERN = "🎃"
    """:obj:`str`: Jack-o-lantern"""
    SEE_NO_EVIL_MONKEY = "🙈"
    """:obj:`str`: See-no-evil monkey"""
    SMILING_FACE_WITH_HALO = "😇"
    """:obj:`str`: Smiling face with halo"""
    FEARFUL_FACE = "😨"
    """:obj:`str`: Fearful face"""
    HANDSHAKE = "🤝"
    """:obj:`str`: Handshake"""
    WRITING_HAND = "✍"
    """:obj:`str`: Writing hand"""
    HUGGING_FACE = "🤗"
    """:obj:`str`: Hugging face"""
    SALUTING_FACE = "🫡"
    """:obj:`str`: Saluting face"""
    FATHER_CHRISTMAS = "🎅"
    """:obj:`str`: Father christmas"""
    CHRISTMAS_TREE = "🎄"
    """:obj:`str`: Christmas tree"""
    SNOWMAN = "☃"
    """:obj:`str`: Snowman"""
    NAIL_POLISH = "💅"
    """:obj:`str`: Nail polish"""
    GRINNING_FACE_WITH_ONE_LARGE_AND_ONE_SMALL_EYE = "🤪"
    """:obj:`str`: Grinning face with one large and one small eye"""
    MOYAI = "🗿"
    """:obj:`str`: Moyai"""
    SQUARED_COOL = "🆒"
    """:obj:`str`: Squared cool"""
    HEART_WITH_ARROW = "💘"
    """:obj:`str`: Heart with arrow"""
    HEAR_NO_EVIL_MONKEY = "🙉"
    """:obj:`str`: Hear-no-evil monkey"""
    UNICORN_FACE = "🦄"
    """:obj:`str`: Unicorn face"""
    FACE_THROWING_A_KISS = "😘"
    """:obj:`str`: Face throwing a kiss"""
    PILL = "💊"
    """:obj:`str`: Pill"""
    SPEAK_NO_EVIL_MONKEY = "🙊"
    """:obj:`str`: Speak-no-evil monkey"""
    SMILING_FACE_WITH_SUNGLASSES = "😎"
    """:obj:`str`: Smiling face with sunglasses"""
    ALIEN_MONSTER = "👾"
    """:obj:`str`: Alien monster"""
    MAN_SHRUGGING = "🤷‍♂️"
    """:obj:`str`: Man Shrugging"""
    SHRUG = "🤷"
    """:obj:`str`: Shrug"""
    WOMAN_SHRUGGING = "🤷‍♀️"
    """:obj:`str`: Woman Shrugging"""
    POUTING_FACE = "😡"
    """:obj:`str`: Pouting face"""
