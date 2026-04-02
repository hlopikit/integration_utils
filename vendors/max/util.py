from io import BytesIO
from typing import Union, List, Dict, Any, Optional

try:
    # noinspection PyPackageRequirements
    from PIL import Image
    pil_imported = True
except ImportError:
    pil_imported = False


MAX_MESSAGE_LENGTH = 4000


def is_command(text: str) -> bool:
    """
    Проверка, является ли строка командой

    :param text: строка
    :type text: str
    :return: Флаг, является ли строка командой
    :rtype: bool
    """
    if text is None:
        return False
    return text.startswith('/')


def extract_command(text: str) -> Union[str, None]:
    """
    Вытаскивает команду из текста сообщения

    :param text: Description
    :type text: str
    :return: Description
    :rtype: Union[str, None]
    """
    if text is None:
        return None
    return text.split()[0].split('@')[0][1:] if is_command(text) else None


def is_pil_image(var) -> bool:
    """
    Returns True if the given object is a PIL.Image.Image object.

    :param var: object to be checked
    :type var: :obj:`object`

    :return: True if the given object is a PIL.Image.Image object.
    :rtype: :obj:`bool`
    """
    return pil_imported and isinstance(var, Image.Image)


def pil_image_to_bytes(image, extension='JPEG', quality='web_low') -> bool:
    """
    Returns True if the given object is a PIL.Image.Image object.

    :param var: object to be checked
    :type var: :obj:`object`

    :return: True if the given object is a PIL.Image.Image object.
    :rtype: :obj:`bool`
    """
    if pil_imported:
        photoBuffer = BytesIO()
        image.convert('RGB').save(photoBuffer, extension, quality=quality)
        photoBuffer.seek(0)
        return photoBuffer
    else:
        raise RuntimeError('PIL module is not imported')


def get_text(media):
    """
    Метод получения текста из media

    :param media: Объект медиа
    """
    try:
        text = media.caption
    except Exception:
        text = None
    finally:
        return text


def get_parse_mode(media, parse_mode: str):
    """
    Метод получения parse_mode из media

    :param media: Объект медиа
    :param parse_mode: Тип парсинга раметки
    """
    try:
        parse_mode_res = media.parse_mode.lower()
    except Exception:
        parse_mode_res = parse_mode.lower()
    finally:
        return parse_mode_res


def smart_split(text: str, chars_per_string: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Разбивает одну строку на несколько строк с максимальным количеством символов chars_per_string на строку.
    Полезно для разбиения одного большого сообщения на несколько.
    Если chars_per_string > 4096: chars_per_string = 4096.
    Разбиение выполняется по '\n', '. ' или ' ', именно в таком порядке приоритета.

    :param text: Текст для разбиения
    :type text: str

    :param chars_per_string: Максимальное количество символов на одну часть, на которую разбивается текст.
    :type chars_per_string: int

    :return: Разбитый текст в виде списка строк.
    :rtype: List из str
    """

    def _text_before_last(substr: str) -> str:
        return substr.join(part.split(substr)[:-1]) + substr

    if chars_per_string > MAX_MESSAGE_LENGTH: chars_per_string = MAX_MESSAGE_LENGTH

    parts = []
    while True:
        if len(text) < chars_per_string:
            parts.append(text)
            return parts

        part = text[:chars_per_string]

        if "\n" in part:
            part = _text_before_last("\n")
        elif ". " in part:
            part = _text_before_last(". ")
        elif " " in part:
            part = _text_before_last(" ")

        parts.append(part)
        text = text[len(part):]


def get_edit_message_data(
    text: Optional[str],
    chat_id: Union[str, int],
    message_id: str,
    attachments: List[Dict[str, Any]],
    timestamp: int
) -> Dict[str, Any]:
    """
    Формирует структуру данных сообщения для метода редактирования сообщения.

    Создаёт словарь с форматом, аналогичным ответу MAX API при получении сообщения,
    чтобы объект Message мог корректно инициализироваться из этих данных.

    :param text: Новый текст сообщения. Может быть None, если текст не изменяется
    :type text: Optional[str]

    :param chat_id: Идентификатор чата
    :type chat_id: Union[str, int]

    :param message_id: Идентификатор сообщения (mid)
    :type message_id: str

    :param attachments: Список вложений сообщения (клавиатуры, медиа и т.д.)
    :type attachments: List[Dict[str, Any]]

    :param timestamp: Временная метка в миллисекундах (Unix timestamp * 1000)
    :type timestamp: int

    :return: Структура данных сообщения в формате MAX API
    :rtype: Dict[str, Any]
    """
    return {
        "message": {
            "recipient": {
                "chat_id": int(chat_id) if isinstance(chat_id, str) and chat_id.isdigit() else chat_id,
                "chat_type": "dialog",
                "user_id": None
            },
            "timestamp": timestamp,
            "body": {
                "mid": message_id,
                "seq": 0,
                "text": text,
                "attachments": attachments
            },
            "sender": {}
        },
        "timestamp": timestamp,
        "user_locale": "ru",
        "update_type": "message_edited"
    }
