import html
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Text, Any, Iterable
from prettytable import PrettyTable


class BaseHandler(ABC):
    def __init__(self, next_handler: Optional['BaseHandler'] = None):
        self._next_handler = next_handler

    @abstractmethod
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Базовый метод обработки текста в цепочке."""
        if self._next_handler:
            return self._next_handler.handle(text, context)
        return text


def _replace_with_placeholders(text: Text, pattern: re.Pattern, protected: Dict[str, Text]) -> Text:
    while True:
        match = pattern.search(text)
        if not match:
            return text
        placeholder = f"__PROTECTED_{len(protected)}__"
        protected[placeholder] = match.group(0)
        text = text[:match.start()] + placeholder + text[match.end():]


class ProtectedTagHandler(BaseHandler):
    """Обработчик для защиты игнорируемых тегов"""

    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        ignore_tags = context.get('ignore_tags')
        if not ignore_tags:
            return super().handle(text, context)

        protected = {}
        result = text

        for tag in ignore_tags:
            if not tag:
                continue

            tag_escaped = re.escape(tag)
            pattern_pair = re.compile(
                rf'\[{tag_escaped}[^]]*].*?\[/\s*{tag_escaped}\s*]',
                flags=re.DOTALL | re.IGNORECASE
            )
            pattern_open = re.compile(
                rf'\[{tag_escaped}[^]]*]',
                flags=re.IGNORECASE
            )
            result = _replace_with_placeholders(result, pattern_pair, protected)
            result = _replace_with_placeholders(result, pattern_open, protected)

        context['_protected_tags'] = protected

        processed = super().handle(result, context)

        for placeholder, original in protected.items():
            processed = processed.replace(placeholder, original)

        return processed


class HTMLEncodeHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Кодирует HTML-сущности для предотвращения конфликтов с разметкой."""
        text = html.escape(str(text or ""), quote=False)
        return super().handle(text, context)


class TableHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Ищет и преобразует BBCode таблицы в текстовые таблицы PrettyTable."""
        tables = re.findall(r'\[table.*?](.*?)\[/table]', text, flags=re.DOTALL | re.IGNORECASE)
        for table_bbcode in tables:
            formatted = self._convert_bbcode_table_to_pretty_table(table_bbcode)
            text = re.sub(
                r'\[table.*?](.*?)\[/table]',
                f'\n<pre>{formatted}</pre>\n',
                text,
                count=1,
                flags=re.DOTALL | re.IGNORECASE
            )
        return super().handle(text, context)

    @staticmethod
    def _convert_bbcode_table_to_pretty_table(table_bbcode: Text) -> Text:
        """Парсит структуру строк и ячеек BBCode для генерации ASCII-таблицы."""
        rows = re.findall(r'\[tr](.*?)\[/tr]', table_bbcode, flags=re.DOTALL | re.IGNORECASE)
        if not rows:
            return ""

        table_data = []
        for row in rows:
            cells = re.findall(r'\[t[dh].*?](.*?)\[/t[dh]]', row, flags=re.DOTALL | re.IGNORECASE)
            row_data = [
                re.sub(r'\s+', ' ', re.sub(r'\[/?[a-z].*?]', '', c, flags=re.IGNORECASE)).strip()
                for c in cells
            ]
            if row_data:
                table_data.append(row_data)

        if not table_data:
            return ""

        pt = PrettyTable()
        pt.header = False
        max_columns = max(len(row) for row in table_data)
        for row in table_data:
            pt.add_row(row + [""] * (max_columns - len(row)))
        return pt.get_string()


class LinkHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Обрабатывает ссылки, email и упоминания пользователей."""
        domain = context.get('domain')

        def _process_url_tag_callback(match: re.Match) -> Text:
            groups = match.groups()
            if len(groups) == 1:
                url = groups[0]
                content = url
            else:
                attr_str = str(groups[0]).strip()
                url = re.split(r'\s+', attr_str)[0].strip('"\'')
                content = groups[1]
            final_url = self._normalize_link_url(url, domain)
            if final_url:
                return f'<a href="{final_url}">{content}</a>'
            return content

        text = re.sub(r'\[url](.*?)\[/url]', _process_url_tag_callback, text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\[url=(.*?)](.*?)\[/url]', _process_url_tag_callback, text, flags=re.DOTALL | re.IGNORECASE)

        text = re.sub(
            r'\[email](.*?)\[/email]',
            lambda m: f'<a href="mailto:{m.group(1).strip() or m.group(1)}">{m.group(1)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r'\[email=(.*?)](.*?)\[/email]',
            lambda m: f'<a href="mailto:{m.group(1).strip().strip(chr(34)+chr(39))}">{m.group(2)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )

        def _process_user_tag_callback(match: re.Match) -> Text:
            uid = match.group(1).strip('"\'')
            name = match.group(2)
            if domain:
                return f'<a href="https://{domain}/company/personal/user/{uid}/">{name}</a>'
            return name

        text = re.sub(r'\[user=(.*?)](.*?)\[/user]', _process_user_tag_callback, text, flags=re.DOTALL | re.IGNORECASE)
        return super().handle(text, context)

    @staticmethod
    def _normalize_link_url(url: Text, domain: Optional[Text]) -> Optional[Text]:
        """Приводит относительные ссылки к абсолютным с учетом домена."""
        url = url.strip()
        if not url or url.startswith(('#', 'javascript:', 'data:')):
            return None
        if url.startswith(('http://', 'https://', 'mailto:', 'tel:')):
            return url
        if url.startswith('//'):
            return f'https:{url}'
        if domain:
            separator = '/' if not url.startswith('/') else ''
            return f'https://{domain}{separator}{url}'
        return url


class MediaHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Обрабатывает теги изображений и видео."""
        domain = context.get('domain')

        def _normalize_media_url(url: Text) -> Text:
            url = url.strip()
            if not url or url.startswith(('http', 'data:')):
                return url
            if domain:
                separator = '/' if not url.startswith('/') else ''
                return f'https://{domain}{separator}{url}'
            return url

        tags = ['img', 'imgleft', 'imgright', 'imgcenter', 'image', 'imgmini']
        for tag in tags:
            pattern = rf'\[{tag}.*?](.*?)\[/{tag}]'
            text = re.sub(
                pattern,
                lambda m: f'<a href="{_normalize_media_url(m.group(1).strip(chr(34)+chr(39)))}">🖼 Изображение</a>',
                text, flags=re.DOTALL | re.IGNORECASE
            )

        text = re.sub(
            r'\[img=(.*?)](.*?)\[/img]',
            lambda m: f'<a href="{_normalize_media_url(m.group(1).strip(chr(34)+chr(39)))}">🖼 {m.group(2)}</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r'\[video.*?](.*?)\[/video]',
            lambda m: f'🎥 <a href="{m.group(1).strip()}">Видео</a>',
            text, flags=re.DOTALL | re.IGNORECASE
        )
        return super().handle(text, context)


class FormattingHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Обрабатывает блоки кода, текстовые эффекты, заголовки и списки."""
        text = self._process_code_blocks(text)
        text = self._process_sub_sup_scripts(text)

        tags_mapping = {
            r'\[b](.*?)\[/b]': r'<b>\1</b>', r'\[bold](.*?)\[/bold]': r'<b>\1</b>',
            r'\[i](.*?)\[/i]': r'<i>\1</i>', r'\[italic](.*?)\[/italic]': r'<i>\1</i>',
            r'\[u](.*?)\[/u]': r'<u>\1</u>', r'\[ins](.*?)\[/ins]': r'<u>\1</u>',
            r'\[s](.*?)\[/s]': r'<s>\1</s>', r'\[del](.*?)\[/del]': r'<s>\1</s>',
            r'\[strike](.*?)\[/strike]': r'<s>\1</s>', r'\[tt](.*?)\[/tt]': r'<code>\1</code>'
        }
        for pattern, replacement in tags_mapping.items():
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)

        quotes = ['quote', 'q', 'cite', 'acronym', 'abbr', 'dfn']
        for tag in quotes:
            text = re.sub(rf'\[{tag}.*?](.*?)\[/{tag}]', r'<code>\1</code>', text, flags=re.DOTALL | re.IGNORECASE)

        for i in range(1, 7):
            text = re.sub(rf'\[h{i}](.*?)\[/h{i}]', r'<b>\1</b>\n', text, flags=re.DOTALL | re.IGNORECASE)

        text = re.sub(r'\[/?(?:list|ul|ol).*?]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\*]', '\n• ', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?(?:p|div)]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[br\s*/?]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[hr\s*/?]', '\n-------------------\n', text, flags=re.IGNORECASE)

        return super().handle(text, context)

    @staticmethod
    def _process_sub_sup_scripts(text: Text) -> Text:
        """Заменяет теги индекса на соответствующие Unicode-символы."""
        trans = {
            "sub": str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"),
            "sup": str.maketrans("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾")
        }
        text = re.sub(r'\[sub](.*?)\[/sub]', lambda m: m.group(1).translate(trans["sub"]), text, flags=re.IGNORECASE)
        text = re.sub(r'\[sup](.*?)\[/sup]', lambda m: m.group(1).translate(trans["sup"]), text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _process_code_blocks(text: Text) -> Text:
        """Оборачивает программный код в теги pre и code."""
        def _wrap_code_in_html(content: Text, lang: Optional[Text] = None) -> Text:
            content = content.strip('\n')
            if lang:
                return f'<pre><code class="language-{lang}">{content}</code></pre>'
            return f'<code>{content}</code>'

        text = re.sub(
            r'\[code\s*=\s*["\']?(.*?)["\']?](.*?)\[/code]',
            lambda m: _wrap_code_in_html(m.group(2), m.group(1).lower().strip()),
            text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r'\[prog(?:=|\s+lang=)["\']?(.*?)["\']?](.*?)\[/prog]',
            lambda m: _wrap_code_in_html(m.group(2), m.group(1).lower().strip()),
            text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r'\[code](.*?)\[/code]', lambda m: _wrap_code_in_html(m.group(1)), text, flags=re.DOTALL | re.IGNORECASE)

        languages = ['php', 'html', 'sql', 'python', 'javascript', 'css']
        for lang in languages:
            text = re.sub(
                rf'\[{lang}](.*?)\[/{lang}]',
                lambda m, l=lang: _wrap_code_in_html(m.group(1), l),
                text, flags=re.DOTALL | re.IGNORECASE
            )
        return text


class SpoilerHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Оборачивает спойлер в текстовые маркеры."""
        text = re.sub(
            r'\[spoiler.*?](.*?)\[/spoiler]',
            r'**спойлер**( \1 )**спойлер**',
            text, flags=re.DOTALL | re.IGNORECASE
        )
        return super().handle(text, context)


class CleanupHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        """Выполняет финальную чистку текста от нераспознанных тегов и лишних пробелов."""
        text = re.sub(r'\[/?[a-z0-9=_-]+.*?]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text).strip()
        return super().handle(text, context)


class BBCodeConverter:
    def __init__(self, domain: Optional[Text] = None):
        """Инициализирует конвертер и собирает цепочку обработчиков."""
        self.domain = domain

    def convert(self, text: Text, ignore_tags: Optional[Iterable[Text]] = None) -> Text:
        """Запускает процесс конвертации через цепочку."""
        if not text:
            return ""

        handler_classes = [
            ProtectedTagHandler,
            HTMLEncodeHandler,
            TableHandler,
            LinkHandler,
            MediaHandler,
            FormattingHandler,
            SpoilerHandler,
            CleanupHandler
        ]

        handler_chain = None
        for handler_class in reversed(handler_classes):
            handler_chain = handler_class(handler_chain)

        context = {
            'domain': self.domain,
            'ignore_tags': list(ignore_tags) if ignore_tags else None
        }

        return handler_chain.handle(text, context)


def bbcode_to_telegram(
    text: Text,
    domain: Optional[Text] = None,
    ignore_tags: Optional[Iterable[Text]] = None,
) -> Text:
    """Функция для перевода из bbcode в html для telegram"""
    converter = BBCodeConverter(domain)
    return converter.convert(text, ignore_tags)
