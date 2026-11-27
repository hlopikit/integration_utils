import inspect
import json
import logging
import math
import sys
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from threading import Condition
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from integration_utils.vendors.telegram import Bot
from integration_utils.vendors.telegram.utils.request import Request


class TelegramLogger:
    """Отправляет лог в Telegram-чат в фоне.

    token — токен бота.
    chat_id — чат или канал.
    usernames — кого упомянуть в error и critical. Список строк, @ можно не писать.
    topics — необязательно, словарь {уровень logging: id топика}.
    level — минимальный уровень, по умолчанию DEBUG.
    timeout — (таймаут соединения, таймаут чтения), секунды: (3.5, 10). Одно число задаёт одинаковый таймаут для соединения и чтения.
    name — подпись в тексте. Если пусто, подставится модуль вызывающего кода.
    telegram_api_base_url — адрес Bot API. По умолчанию https://api.telegram.org/bot.
    max_queue_size — сколько неотправленных сообщений держать. Дальше новые пропускаются.
    """

    def __init__(
        self,
        token: str,
        chat_id: Union[int, str],
        usernames: Iterable[str],
        topics: Optional[Dict[int, Optional[int]]] = None,
        level: int = logging.DEBUG,
        timeout: Union[float, Tuple[float, float]] = (3.5, 10),
        name: Optional[str] = None,
        telegram_api_base_url: str = 'https://api.telegram.org/bot',
        max_queue_size: int = 100,
    ):
        if not (isinstance(token, str) and token.strip()):
            raise ValueError('token is required')

        if not chat_id:
            raise ValueError('chat_id is required')

        if not isinstance(usernames, Iterable):
            raise TypeError('usernames must be a iterable')

        if not all(isinstance(user, str) and user.lstrip('@').strip() for user in usernames):
            raise ValueError('usernames must contain non-empty strings')

        if isinstance(timeout, (int, float)):
            timeout = (timeout, timeout)
        if not isinstance(timeout, tuple) or len(timeout) != 2:
            raise ValueError('timeout must be a number or a (connect, read) tuple')
        if any(
            not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or value <= 0
            for value in timeout
        ):
            raise ValueError('timeout values must be positive finite numbers')

        if not telegram_api_base_url:
            raise ValueError('telegram_api_base_url is required')

        if not isinstance(max_queue_size, int) or isinstance(max_queue_size, bool) or max_queue_size < 1:
            raise ValueError('max_queue_size must be a positive integer')

        self._token = token
        self.chat_id = chat_id
        self.usernames = tuple(dict.fromkeys('@' + user.strip().lstrip('@') for user in usernames))
        self.topics = dict(topics or {})
        self.level = level
        self.timeout = timeout
        self.name = name
        self.telegram_api_base_url = telegram_api_base_url
        self.max_queue_size = max_queue_size
        self._executor: Optional[ThreadPoolExecutor] = None
        self._bot: Optional[Bot] = None
        self._pending = 0
        self._closed = False
        self._lock = Condition()

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        return self.log(logging.DEBUG, message, context)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None):
        return self.log(logging.INFO, message, context)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        return self.log(logging.WARNING, message, context)

    def error(self, message: str, context: Optional[Dict[str, Any]] = None):
        return self.log(logging.ERROR, message, context)

    def critical(self, message: str, context: Optional[Dict[str, Any]] = None):
        return self.log(logging.CRITICAL, message, context)

    def log(self, level: int, message: str, context: Optional[Dict[str, Any]] = None):
        try:
            self._log(level, message, context)
        except Exception as exc:
            self._warn('TelegramLogger failed: ' + type(exc).__name__)

    def _log(self, level: int, message: str, context: Optional[Dict[str, Any]]):
        if level < self.level:
            return None

        frame = inspect.currentframe()

        try:
            frame = frame.f_back

            while frame and frame.f_code.co_filename == __file__:
                frame = frame.f_back

            if frame is None:
                caller = ('', '', '', 0)
            else:
                caller = (
                    frame.f_globals.get('__name__', ''),
                    frame.f_code.co_filename,
                    frame.f_code.co_name,
                    frame.f_lineno,
                )
        finally:
            del frame

        exc_info = sys.exc_info()
        exception = ''.join(traceback.format_exception(*exc_info)) if exc_info[0] else None
        del exc_info

        messages = self._format(level, message, context, caller, exception)

        with self._lock:
            if self._closed:
                return None

            if self._pending >= self.max_queue_size:
                self._warn('TelegramLogger queue is full, message dropped')
                return None

            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix='telegram-logger',
                )

            self._pending += 1

            try:
                self._executor.submit(self._deliver, messages, self.topics.get(level))
            except Exception as exc:
                self._pending -= 1

                if not self._pending:
                    self._lock.notify_all()

                self._warn('TelegramLogger enqueue failed: ' + type(exc).__name__)

                return None

    def flush(self):
        """Дождаться отправки сообщений, которые уже стоят в очереди."""
        with self._lock:
            while self._pending:
                self._lock.wait()

    def shutdown(self, wait: bool = True):
        """Остановить фоновую отправку.

        wait=True дожидается очереди.
        wait=False отменяет ещё не начатые сообщения и возвращается сразу.
        """

        with self._lock:
            self._closed = True
            executor = self._executor
            self._executor = None

        if executor is None:
            return

        if wait:
            self.flush()
            executor.shutdown()
            return

        executor.shutdown(wait=False, cancel_futures=True)

        with self._lock:
            self._pending = 0
            self._lock.notify_all()

    def _format(
        self,
        level: int,
        message: str,
        context: Optional[Dict[str, Any]],
        caller: Tuple[str, str, str, int],
        exception: Optional[str],
    ) -> List[str]:
        module, path, function, line = caller

        sections = [
            ('Level', '#' + logging.getLevelName(level), '', ''),
            ('Logger', self.name or module, '<code>', '</code>'),
            ('Date', datetime.now().astimezone().isoformat(timespec='seconds'), '', ''),
            ('Message', message, '<i>', '</i>'),
            ('Path', path, '<code>', '</code>'),
            ('Function', function, '<code>', '</code>'),
            ('Line', line, '', ''),
        ]

        if exception:
            sections.append((
                'Exception',
                exception,
                '<pre><code class="language-python">',
                '</code></pre>',
            ))

        if context is not None:
            # json.dumps падает на циклической ссылке. Тогда в лог уходит обычный текст
            try:
                context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
            except (TypeError, ValueError):
                try:
                    context_text = str(context)
                except Exception:
                    context_text = '<unprintable context>'

            sections.append((
                'Extra fields',
                context_text,
                '<pre><code class="language-json">',
                '</code></pre>',
            ))

        if level in (logging.ERROR, logging.CRITICAL) and self.usernames:
            sections.insert(1, ('', ' '.join(self.usernames), '', ''))

        messages = []
        current = ''
        current_size = 0

        for label, text, opening, closing in sections:
            text = str(text)

            for start in range(0, len(text), 1800):
                chunk = text[start:start + 1800]

                if label:
                    block = f'<b>{label}:</b>\n' + opening + escape(chunk) + closing
                else:
                    block = opening + escape(chunk) + closing

                # Длина для Bot API считается в UTF-16, лимит сообщения — 4096
                block_size = len(chunk.encode('utf-16-le')) // 2

                if label:
                    block_size += len(label) + 2

                if current:
                    candidate = current + '\n\n' + block
                    candidate_size = current_size + 2 + block_size
                else:
                    candidate = block
                    candidate_size = block_size

                if current and candidate_size > 4096:
                    messages.append(current)
                    current = block
                    current_size = block_size
                else:
                    current = candidate
                    current_size = candidate_size

        if current:
            messages.append(current)

        return messages

    def _deliver(self, messages: List[str], topic: Optional[int]):
        try:
            if self._bot is None:
                self._bot = Bot(
                    self._token,
                    base_url=self.telegram_api_base_url,
                    request=Request(
                        connect_timeout=self.timeout[0],
                        read_timeout=self.timeout[1],
                    ),
                )

            for text in messages:
                try:
                    self._bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode='HTML',
                        message_thread_id=topic or None,
                        timeout=self.timeout[1],
                    )
                except Exception as exc:
                    self._warn('TelegramLogger delivery failed: ' + type(exc).__name__)

        except Exception as exc:
            self._warn('TelegramLogger delivery failed: ' + type(exc).__name__)

        finally:
            with self._lock:
                if self._pending:
                    self._pending -= 1
                if not self._pending:
                    self._lock.notify_all()

    @staticmethod
    def _warn(message: str):
        try:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        except Exception:
            pass
