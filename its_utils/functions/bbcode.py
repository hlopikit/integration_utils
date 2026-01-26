import html
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Text, Any
from urllib.parse import urlparse
from prettytable import PrettyTable


class BaseHandler(ABC):
    def __init__(self, next_handler: Optional['BaseHandler'] = None):
        self._next_handler = next_handler

    @abstractmethod
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        if self._next_handler:
            return self._next_handler.handle(text, context)
        return text


class HTMLEncodeHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        if not text:
            return ""
        text = html.escape(str(text), quote=False)
        return super().handle(text, context)


class TableHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = self._extract_tables(text)
        return super().handle(text, context)

    def _extract_tables(self, text: Text) -> Text:
        tables = re.findall(r'\[table.*?\](.*?)\[/table\]', text, flags=re.IGNORECASE | re.DOTALL)
        for table_bbcode in tables:
            formatted_table = self._bbcode_table_to_prettytable(table_bbcode)
            text = re.sub(r'\[table.*?\](.*?)\[/table\]', f'\n<pre>{formatted_table}</pre>\n', text, count=1, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _bbcode_table_to_prettytable(self, table_bbcode: Text) -> Text:
        rows = re.findall(r'\[tr\](.*?)\[/tr\]', table_bbcode, flags=re.IGNORECASE | re.DOTALL)
        if not rows:
            return ""

        table_data = []
        for row in rows:
            cells = re.findall(r'\[td.*?\](.*?)\[/td\]|\[th.*?\](.*?)\[/th\]', row, flags=re.IGNORECASE | re.DOTALL)
            row_data = []
            for cell in cells:
                cell_text = cell[0] or cell[1]
                if cell_text is not None:
                    row_data.append(self._clean_cell_text(cell_text))
            if row_data:
                table_data.append(row_data)

        if not table_data:
            return ""

        pt = PrettyTable()
        pt.header = False
        max_columns = max(len(row) for row in table_data)

        for row in table_data:
            while len(row) < max_columns:
                row.append("")
            pt.add_row(row)

        return pt.get_string()

    def _clean_cell_text(self, text: Text) -> Text:
        text = re.sub(r'\[/?[a-z].*?\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class LinkHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = self._process_links(text, context)
        return super().handle(text, context)

    def _process_links(self, text: Text, context: Dict[str, Any]) -> Text:
        domain = context.get('domain')

        def process_url_tag(match: re.Match) -> Text:
            if len(match.groups()) == 1:
                url = match.group(1)
                text_content = url
            else:
                url = match.group(1)
                text_content = match.group(2)

            final_url = self._normalize_url(url, domain)
            if self._is_valid_external_url(final_url):
                return f'<a href="{final_url}">{text_content}</a>'
            return text_content

        def process_email_tag(match: re.Match) -> Text:
            email = match.group(1)
            return f'<a href="mailto:{email}">{email}</a>'

        def process_user_tag(match: re.Match) -> Text:
            uid = match.group(1)
            name = match.group(2) if len(match.groups()) > 1 else f"User {uid}"
            if domain:
                link = f"https://{domain}/company/personal/user/{uid}/"
                return f'<a href="{link}">{name}</a>'
            return name

        text = re.sub(r'\[url\](.*?)\[/url\]', process_url_tag, text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', process_url_tag, text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[email\](.*?)\[/email\]', process_email_tag, text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[user=(.*?)\](.*?)\[/user\]', process_user_tag, text, flags=re.IGNORECASE | re.DOTALL)

        return text

    def _normalize_url(self, url: Text, domain: Optional[Text]) -> Text:
        if not url:
            return url
        if url.startswith(('http://', 'https://', 'mailto:', 'tel:')):
            return url
        if domain and not url.startswith(('http://', 'https://')):
            if url.startswith('/'):
                return f'https://{domain}{url}'
            elif '.' not in url:
                return f'https://{domain}/{url}'
        return url

    def _is_valid_external_url(self, url: Text) -> bool:
        if not url:
            return False
        if url.startswith(('#', 'javascript:')):
            return False
        try:
            parsed = urlparse(url)
            if not parsed.netloc and not url.startswith('mailto:'):
                return False
            return True
        except:
            return False


class MediaHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = self._process_images(text, context)
        text = self._process_videos(text)
        return super().handle(text, context)

    def _process_images(self, text: Text, context: Dict[str, Any]) -> Text:
        domain = context.get('domain')

        def process_image_tag(match: re.Match) -> Text:
            url = match.group(1)
            alt_text = match.group(2) if len(match.groups()) > 1 else 'Изображение'

            final_url = self._normalize_image_url(url, domain)
            if final_url:
                return f'<a href="{final_url}">🖼 {alt_text}</a>'
            return alt_text

        text = re.sub(r'\[img\](.*?)\[/img\]', process_image_tag, text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[img=(.*?)\](.*?)\[/img\]', process_image_tag, text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _process_videos(self, text: Text) -> Text:
        video_tags = ['video', 'youtube', 'rutube', 'googlevideo', 'vimeo']
        for tag in video_tags:
            pattern = rf'\[{tag}.*?\](.*?)\[/{tag}\]'
            text = re.sub(pattern, r'🎥 <a href="\1">Видео</a>', text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _normalize_image_url(self, url: Text, domain: Optional[Text]) -> Text:
        if not url:
            return url
        if url.startswith(('http://', 'https://', 'data:')):
            return url
        if domain:
            if url.startswith('/'):
                return f'https://{domain}{url}'
            else:
                return f'https://{domain}/{url}'
        return url


class FormattingHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = self._process_code_blocks(text)
        text = self._process_simple_tags(text)
        text = self._process_headers(text)
        text = self._process_lists(text)
        text = self._process_paragraphs(text)
        return super().handle(text, context)

    def _process_simple_tags(self, text: Text) -> Text:
        mapping = {
            r'\[b\](.*?)\[/b\]': r'<b>\1</b>',
            r'\[bold\](.*?)\[/bold\]': r'<b>\1</b>',
            r'\[i\](.*?)\[/i\]': r'<i>\1</i>',
            r'\[italic\](.*?)\[/italic\]': r'<i>\1</i>',
            r'\[u\](.*?)\[/u\]': r'<u>\1</u>',
            r'\[ins\](.*?)\[/ins\]': r'<u>\1</u>',
            r'\[s\](.*?)\[/s\]': r'<s>\1</s>',
            r'\[del\](.*?)\[/del\]': r'<s>\1</s>',
            r'\[strike\](.*?)\[/strike\]': r'<s>\1</s>',
            r'\[tt\](.*?)\[/tt\]': r'<code>\1</code>',
            r'\[code\](.*?)\[/code\]': r'<code>\1</code>',
        }

        for pattern, replacement in mapping.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)

        text = re.sub(r'\[quote.*?\](.*?)\[/quote\]', r'<blockquote>\1</blockquote>', text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _process_code_blocks(self, text: Text) -> Text:
        def process_code_with_language(match: re.Match) -> Text:
            language = match.group(1).lower()
            content = match.group(2)
            return f'<pre><code class="language-{language}">{content}</code></pre>'

        text = re.sub(r'\[code\s*=\s*(.*?)\](.*?)\[/code\]', process_code_with_language, text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[php\](.*?)\[/php\]', r'<pre><code class="language-php">\1</code></pre>', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[html\](.*?)\[/html\]', r'<pre><code class="language-html">\1</code></pre>', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[sql\](.*?)\[/sql\]', r'<pre><code class="language-sql">\1</code></pre>', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'\[python\](.*?)\[/python\]', r'<pre><code class="language-python">\1</code></pre>', text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _process_headers(self, text: Text) -> Text:
        for i in range(1, 7):
            text = re.sub(rf'\[h{i}\](.*?)\[/h{i}\]', r'<b>\1</b>\n', text, flags=re.IGNORECASE | re.DOTALL)
        return text

    def _process_lists(self, text: Text) -> Text:
        text = re.sub(r'\[/?list.*?\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?ul\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?ol\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\*\]', '\n• ', text, flags=re.IGNORECASE)
        return text

    def _process_paragraphs(self, text: Text) -> Text:
        text = re.sub(r'\[/?p\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?div\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[br\s*/?\]', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\[hr\s*/?\]', '\n-------------------\n', text, flags=re.IGNORECASE)
        return text


class SpoilerHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = re.sub(r'\[spoiler\](.*?)\[/spoiler\]', r'<span class="tg-spoiler">\1</span>', text, flags=re.IGNORECASE | re.DOTALL)
        return super().handle(text, context)


class CleanupHandler(BaseHandler):
    def handle(self, text: Text, context: Dict[str, Any]) -> Text:
        text = self._remove_unsupported_tags(text)
        text = self._cleanup_whitespace(text)
        return super().handle(text, context)

    def _remove_unsupported_tags(self, text: Text) -> Text:
        text = re.sub(r'\[/?[a-z0-9=_-]+.*?\]', '', text, flags=re.IGNORECASE)
        return text

    def _cleanup_whitespace(self, text: Text) -> Text:
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        return text.strip()


class BBCodeConverter:
    def __init__(self, domain: Optional[Text] = None):
        self.domain = domain

        cleanup_handler = CleanupHandler()
        spoiler_handler = SpoilerHandler(cleanup_handler)
        formatting_handler = FormattingHandler(spoiler_handler)
        media_handler = MediaHandler(formatting_handler)
        link_handler = LinkHandler(media_handler)
        table_handler = TableHandler(link_handler)
        self._handler_chain = HTMLEncodeHandler(table_handler)

    def convert(self, text: Text) -> Text:
        if not text:
            return ""
        return self._handler_chain.handle(text, {'domain': self.domain})


def bbcode_to_telegram(text: Text, domain: Optional[Text] = None) -> Text:
    converter = BBCodeConverter(domain)
    return converter.convert(text)
