import html
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional, Tuple, Type, Match, Text

from prettytable import PrettyTable

__all__ = [
    "bbcode_to_telegram",
]


def _replace_with_placeholders(text: Text, pattern: re.Pattern, protected_store: Dict[Text, Text]) -> Text:
    """Заменяет совпадения на токены, гарантируя уникальность ключа."""

    def _replacer(match: Match) -> Text:
        # Используем длину словаря для уникальности токена
        token = f"__PROTECTED_{len(protected_store)}__"
        protected_store[token] = match.group(0)
        return token

    return pattern.sub(_replacer, text)


class _BaseHandler(ABC):
    """
    Базовый обработчик тегов
    """

    __slots__ = ("_next_handler",)

    _next_handler: Optional['_BaseHandler']

    def __init__(self, next_handler: Optional['_BaseHandler'] = None):
        self._next_handler = next_handler

    @abstractmethod
    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        """Базовый метод обработки текста в цепочке."""
        if self._next_handler:
            return self._next_handler.handle(text, context)
        else:
            return text


class _ProtectedTagHandler(_BaseHandler):
    """
    Обрабатывает игнорируемые теги, временно скрывая их.
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        ignore_tags = context.get('ignore_tags')

        if not ignore_tags:
            return super().handle(text, context)

        protected_store: Dict[Text, Text] = {}
        processed_text = text

        for tag in ignore_tags:
            tag_escaped = re.escape(tag)

            # Шаблон для парных тегов: [tag]...[/tag]
            pattern_pair = re.compile(
                rf'\[{tag_escaped}[^]]*].*?\[/\s*{tag_escaped}\s*]',
                flags=re.DOTALL | re.IGNORECASE,
            )

            # Шаблон для одиночных тегов: [tag]
            pattern_single = re.compile(
                rf'\[{tag_escaped}[^]]*]',
                flags=re.IGNORECASE,
            )

            # Заменяем теги на токены-заглушки
            processed_text = _replace_with_placeholders(processed_text, pattern_pair, protected_store)
            processed_text = _replace_with_placeholders(processed_text, pattern_single, protected_store)

        # Пропускаем текст через остальную цепочку обработчиков
        processed_text = super().handle(processed_text, context)

        # Восстанавливаем оригинальные теги на место токенов
        for placeholder, original_content in protected_store.items():
            processed_text = processed_text.replace(placeholder, original_content)

        return processed_text


class _HTMLEncodeHandler(_BaseHandler):
    """
    Экранирует спецсимволы HTML.
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        # Экранируем HTML-символы для безопасности
        safe_text = html.escape(str(text or ""), quote=False)
        return super().handle(safe_text, context)


class _TableHandler(_BaseHandler):
    """
    Обрабатывает таблицы:
    [table] — таблица
    [tr] — строка таблицы
    [td] — ячейка таблицы
    [th] — заголовочная ячейка
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        """Ищет и преобразует BBCode таблицы в текстовые таблицы PrettyTable."""

        bbcode_tables = re.findall(
            pattern=r'\[table.*?](.*?)\[/table]',
            string=text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        for bbcode_content in bbcode_tables:
            ascii_table = self._convert_bbcode_to_ascii(bbcode_content)

            # Заменяем BBCode таблицу на HTML-представление
            text = re.sub(
                r'\[table.*?](.*?)\[/table]',
                f'\n<pre>{ascii_table}</pre>\n',
                text,
                count=1,
                flags=re.DOTALL | re.IGNORECASE,
            )

        return super().handle(text, context)

    @staticmethod
    def _convert_bbcode_to_ascii(bbcode_content: Text) -> Text:
        # Ищем все строки таблицы (теги [tr])
        rows = re.findall(r'\[tr](.*?)\[/tr]', bbcode_content, flags=re.DOTALL | re.IGNORECASE)

        if not rows:
            return ""

        parsed_data = []
        for row in rows:
            # Ищем все ячейки в строке (теги [td] или [th])
            cells = re.findall(r'\[t[dh].*?](.*?)\[/t[dh]]', row, flags=re.DOTALL | re.IGNORECASE)

            # Очищаем содержимое ячеек от вложенных тегов
            cleaned_row = [
                re.sub(r'\s+', ' ', re.sub(r'\[/?[a-z].*?]', '', cell, flags=re.IGNORECASE)).strip()
                for cell in cells
            ]

            if cleaned_row:
                parsed_data.append(cleaned_row)

        if not parsed_data:
            return ""

        pt = PrettyTable()
        pt.header = False

        max_cols = max(len(row) for row in parsed_data)
        for row in parsed_data:
            # Дополняем пустые ячейки для ровной таблицы
            row += [""] * (max_cols - len(row))
            pt.add_row(row)

        return pt.get_string()


class _LinkHandler(_BaseHandler):
    """
    Обрабатывает ссылки и контакты:
    [url] — гиперссылка
    [email] — ссылка на email
    [user] — ссылка на профиль пользователя
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        domain = context.get('domain')

        def _url_callback(match: Match) -> Text:
            groups = match.groups()

            # Два варианта: [url]ссылка[/url] или [url=ссылка]текст[/url]
            if len(groups) == 1:
                url_raw = groups[0]  # Первый случай: только ссылка
                link_text = url_raw
            else:
                attr_str = str(groups[0]).strip()
                url_raw = re.split(r'\s+', attr_str)[0].strip('"\'')  # Извлекаем ссылку из атрибута
                link_text = groups[1]

            # Нормализуем ссылку (добавляем протокол, домен и т.д.)
            final_url = self._normalize_url(url_raw, domain)

            if final_url:
                return f'<a href="{final_url}">{link_text}</a>'
            return link_text

        # Обрабатываем оба варианта тега [url]
        text = re.sub(r'\[url](.*?)\[/url]', _url_callback, text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\[url=(.*?)](.*?)\[/url]', _url_callback, text, flags=re.DOTALL | re.IGNORECASE)

        text = re.sub(
            r'\[email](.*?)\[/email]',
            lambda m: f'<a href="mailto:{m.group(1).strip()}">{m.group(1)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )

        text = re.sub(
            r'\[email=(.*?)](.*?)\[/email]',
            lambda m: f'<a href="mailto:{m.group(1).strip().strip(chr(34) + chr(39))}">{m.group(2)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )

        def _user_callback(match: Match) -> Text:
            user_id = match.group(1).strip('"\'')
            user_name = match.group(2)
            if domain:
                return f'<a href="https://{domain}/company/personal/user/{user_id}/">{user_name}</a>'
            return user_name

        text = re.sub(r'\[user=(.*?)](.*?)\[/user]', _user_callback, text, flags=re.DOTALL | re.IGNORECASE)

        return super().handle(text, context)

    @staticmethod
    def _normalize_url(url: Text, domain: Optional[Text]) -> Optional[Text]:
        """Приводит относительные ссылки к абсолютным с учетом домена."""

        url = url.strip()

        # Игнорируем специальные ссылки
        if not url or url.startswith(('#', 'javascript:', 'data:')):
            return None

        # Уже абсолютные ссылки оставляем как есть
        if url.startswith(('http://', 'https://', 'mailto:', 'tel:')):
            return url

        # Ссылка без протокола
        if url.startswith('//'):
            return f'https:{url}'

        # Относительная ссылка - добавляем домен
        if domain:
            separator = '/' if not url.startswith('/') else ''
            return f'https://{domain}{separator}{url}'

        return url


class _MediaHandler(_BaseHandler):
    """
    Обрабатывает изображения и видео:
    [img] — изображение
    [imgleft], [imgright], [imgcenter] — изображение с обтеканием
    [image] — большое изображение
    [imgmini] — миниатюра
    [video] — видео
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:
        domain = context.get('domain')

        def _get_full_url(url: Text) -> Text:
            url = url.strip().strip('"\'')
            # Если уже абсолютная ссылка, возвращаем как есть
            if not url or url.startswith(('http', 'data:')):
                return url

            # Относительная ссылка - добавляем домен
            if domain:
                separator = '/' if not url.startswith('/') else ''
                return f'https://{domain}{separator}{url}'

            return url

        # Обрабатываем различные теги изображений
        image_tags = ['img', 'imgleft', 'imgright', 'imgcenter', 'image', 'imgmini']
        for tag in image_tags:
            text = re.sub(
                rf'\[{tag}.*?](.*?)\[/{tag}]',
                lambda m: f'<a href="{_get_full_url(m.group(1))}">🖼 Изображение</a>',
                text, flags=re.DOTALL | re.IGNORECASE
            )

        # Тег [img] с альтернативным текстом
        text = re.sub(
            r'\[img=(.*?)](.*?)\[/img]',
            lambda m: f'<a href="{_get_full_url(m.group(1))}">🖼 {m.group(2)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )

        # Обрабатываем видео
        text = re.sub(
            r'\[video.*?](.*?)\[/video]',
            lambda m: f'🎥 <a href="{m.group(1).strip()}">Видео</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )

        return super().handle(text, context)


class _FormattingHandler(_BaseHandler):
    """
    Обрабатывает форматирование:
    [b], [bold] — жирный
    [i], [italic] — курсив
    [u], [ins] — подчёркнутый
    [s], [del], [strike] — зачёркнутый
    [tt] — моноширинный
    [sub], [sup] — индексы
    [h1]-[h6] — заголовки
    [quote], [q], [cite], [acronym], [abbr], [dfn] — цитаты
    [list], [ul], [ol], [*] — списки
    [code], [prog], [php], [html], [sql]... — код
    [p], [div], [br], [hr] — структура
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:

        # Обрабатываем код и скрипты в первую очередь
        text = self._process_code_blocks(text)
        text = self._process_sub_sup_scripts(text)

        # Простые замены форматирования
        simple_replacements = {
            r'\[b](.*?)\[/b]': r'<b>\1</b>',
            r'\[bold](.*?)\[/bold]': r'<b>\1</b>',
            r'\[i](.*?)\[/i]': r'<i>\1</i>',
            r'\[italic](.*?)\[/italic]': r'<i>\1</i>',
            r'\[u](.*?)\[/u]': r'<u>\1</u>',
            r'\[ins](.*?)\[/ins]': r'<u>\1</u>',
            r'\[s](.*?)\[/s]': r'<s>\1</s>',
            r'\[del](.*?)\[/del]': r'<s>\1</s>',
            r'\[strike](.*?)\[/strike]': r'<s>\1</s>',
            r'\[tt](.*?)\[/tt]': r'<code>\1</code>'
        }

        for pattern, replacement in simple_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)

        # Цитаты оформляем как код
        quote_tags = ['quote', 'q', 'cite', 'acronym', 'abbr', 'dfn']
        for tag in quote_tags:
            text = re.sub(rf'\[{tag}.*?](.*?)\[/{tag}]', r'<code>\1</code>', text, flags=re.DOTALL | re.IGNORECASE)

        # Заголовки
        for i in range(1, 7):
            text = re.sub(rf'\[h{i}](.*?)\[/h{i}]', r'<b>\1</b>\n', text, flags=re.DOTALL | re.IGNORECASE)

        # Структурные элементы
        text = re.sub(r'\[/?(?:list|ul|ol).*?]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\*]', '\n• ', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?(?:p|div)]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[br\s*/?]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[hr\s*/?]', '\n-------------------\n', text, flags=re.IGNORECASE)

        return super().handle(text, context)

    @staticmethod
    def _process_sub_sup_scripts(text: Text) -> Text:

        # Таблицы преобразования для подстрочных и надстрочных символов
        trans_sub = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
        trans_sup = str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")

        text = re.sub(r'\[sub](.*?)\[/sub]', lambda m: m.group(1).translate(trans_sub), text, flags=re.IGNORECASE)
        text = re.sub(r'\[sup](.*?)\[/sup]', lambda m: m.group(1).translate(trans_sup), text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _process_code_blocks(text: Text) -> Text:
        def _wrap_code(content: Text, lang: Optional[Text] = None) -> Text:

            content = content.strip('\n')

            if lang:
                # Код с указанием языка
                return f'<pre><code class="language-{lang}">{content}</code></pre>'

            # Код без указания языка
            return f'<code>{content}</code>'

        # Код с указанием языка через атрибут
        text = re.sub(
            r'\[code\s*=\s*["\']?(.*?)["\']?](.*?)\[/code]',
            lambda m: _wrap_code(m.group(2), m.group(1).lower().strip()),
            text, flags=re.DOTALL | re.IGNORECASE
        )

        # Тег [prog] для программного кода
        text = re.sub(
            r'\[prog(?:=|\s+lang=)["\']?(.*?)["\']?](.*?)\[/prog]',
            lambda m: _wrap_code(m.group(2), m.group(1).lower().strip()),
            text, flags=re.DOTALL | re.IGNORECASE
        )

        # Простой тег [code] без языка
        text = re.sub(r'\[code](.*?)\[/code]', lambda m: _wrap_code(m.group(1)), text, flags=re.DOTALL | re.IGNORECASE)

        # Специфические языки программирования
        specific_langs = ['php', 'html', 'sql', 'python', 'javascript', 'css', 'bash', 'java']
        for lang in specific_langs:
            text = re.sub(
                rf'\[{lang}](.*?)\[/{lang}]',
                lambda m, l=lang: _wrap_code(m.group(1), l),
                text, flags=re.DOTALL | re.IGNORECASE
            )

        return text


class _SpoilerHandler(_BaseHandler):
    """
    Обрабатывает спойлер:
    [spoiler] — скрытый текст
    """

    def handle(self, text: Text, context: Dict[Text, Any]) -> Text:

        # Оборачиваем спойлер в тег <tg-spoiler>
        text = re.sub(
            r'\[spoiler.*?](.*?)\[/spoiler]',
            r'<tg-spoiler>\1</tg-spoiler>',
            text, flags=re.DOTALL | re.IGNORECASE
        )
        return super().handle(text, context)


class _BBCodeConverter:
    """
    Основной конвертер BBCode в HTML для Telegram.
    """

    _HANDLER_CLASSES: Tuple[Type[_BaseHandler], ...] = (
        _ProtectedTagHandler,
        _HTMLEncodeHandler,
        _TableHandler,
        _LinkHandler,
        _MediaHandler,
        _FormattingHandler,
        _SpoilerHandler,
    )

    def __call__(
            self,
            text: Text,
            *,
            ignore_tags: Optional[Iterable[Text]] = None,
            domain: Optional[Text] = None,
    ) -> Text:
        """Запускает процесс конвертации через цепочку."""

        if not text:
            return ""

        handler_chain = None

        # Строим цепочку обработчиков в обратном порядке
        for handler_class in reversed(self._HANDLER_CLASSES):
            handler_chain = handler_class(handler_chain)

        # Подготавливаем контекст для обработчиков
        context = {
            'ignore_tags': tuple(ignore_tags) if ignore_tags else None,
            'domain': domain,
        }

        if handler_chain:
            return handler_chain.handle(text, context)
        return text


def bbcode_to_telegram(
        text: Text,
        domain: Optional[Text] = None,
        ignore_tags: Optional[Iterable[Text]] = None,
) -> Text:
    """Функция для перевода из bbcode в html для telegram"""
    converter = _BBCodeConverter()
    return converter(text, ignore_tags=ignore_tags, domain=domain)