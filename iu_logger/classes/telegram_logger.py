from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
import inspect
import json
import logging
import math
import sys
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union
import traceback
import warnings

from integration_utils.vendors.telegram import Bot
from integration_utils.vendors.telegram.utils.request import Request


class TelegramLogger:
    def __init__(self, token: str, chat_id: Union[int, str], usernames: Union[List[str], Tuple[str, ...]],
                 topics: Optional[Dict[int, Optional[int]]] = None, level: int = logging.DEBUG, timeout: float = 10, name: Optional[str] = None):
        if not isinstance(token, str) or not token.strip():
            raise ValueError('token is required')
        if not chat_id:
            raise ValueError('chat_id is required')
        if not isinstance(usernames, (list, tuple)):
            raise TypeError('usernames must be a list or tuple')
        if not all(isinstance(user, str) and user.lstrip('@').strip() for user in usernames):
            raise ValueError('usernames must contain non-empty strings')
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be a positive finite number')
        self._token = token
        self.chat_id = chat_id
        self.usernames = tuple(dict.fromkeys('@' + user.strip().lstrip('@') for user in usernames))
        self.topics = dict(topics or {})
        self.level = level
        self.timeout = timeout
        self.name = name
        self._executor: Optional[ThreadPoolExecutor] = None
        self._bot: Optional[Bot] = None
        self._lock = Lock()

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
        if level < self.level:
            return None
        frame = inspect.currentframe()
        try:
            frame = frame.f_back
            while frame and frame.f_code.co_filename == __file__:
                frame = frame.f_back
            caller = (frame.f_globals.get('__name__', ''), frame.f_code.co_filename, frame.f_code.co_name, frame.f_lineno) if frame else ('', '', '', 0)
        finally:
            del frame
        exc_info = sys.exc_info()
        exception = ''.join(traceback.format_exception(*exc_info)) if exc_info[0] else None
        del exc_info
        messages = self._format(level, message, context, caller, exception)
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='telegram-logger')
            self._executor.submit(self._deliver, messages, self.topics.get(level))

    def _format(self, level: int, message: str, context: Optional[Dict[str, Any]], caller: Tuple[str, str, str, int], exception: Optional[str]) -> List[str]:
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
            sections.append(('Exception', exception, '<pre><code class="language-python">', '</code></pre>'))
        if context is not None:
            sections.append(('Extra fields', json.dumps(context, ensure_ascii=False, indent=2, default=str), '<pre><code class="language-json">', '</code></pre>'))
        if level in (logging.ERROR, logging.CRITICAL) and self.usernames:
            sections.append(('', ' '.join(self.usernames), '', ''))
        messages, current = [], ''
        current_size = 0
        for label, text, opening, closing in sections:
            text = str(text)
            for start in range(0, len(text), 1800):
                chunk = text[start:start + 1800]
                block = (f'<b>{label}:</b>\n' if label else '') + opening + escape(chunk) + closing
                block_size = len(chunk.encode('utf-16-le')) // 2 + (len(label) + 2 if label else 0)
                candidate = current + ('\n\n' if current else '') + block
                candidate_size = current_size + (2 if current else 0) + block_size
                if candidate_size > 4096:
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
                self._bot = Bot(self._token, request=Request(connect_timeout=self.timeout, read_timeout=self.timeout))
            for text in messages:
                self._bot.send_message(chat_id=self.chat_id, text=text, parse_mode='HTML', message_thread_id=topic or None, timeout=self.timeout)
        except Exception as exc:
            warnings.warn('TelegramLogger delivery failed: ' + type(exc).__name__, RuntimeWarning, stacklevel=2)
