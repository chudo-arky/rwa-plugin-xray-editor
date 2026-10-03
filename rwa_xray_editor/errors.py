"""Текст ошибки для клиента: без внутренних URL, путей и токенов.

Подробности остаются в логе бэкенда (``ctx.logger``). Пользователю нужен смысл
(что не ответила панель, что GitHub вернул 404), а не адреса внутренней сети и
пути файловой системы контейнера.
"""
from __future__ import annotations

import re

_URL = re.compile(r"https?://\S+")
_PATH = re.compile(r"(?<![\w/])/(?:app|tmp|root|home|etc|var|opt)/[^\s'\"]*")
_TOKEN = re.compile(r"(?i)(token|bearer|authorization|password)[=:]\s*\S+")
_LIMIT = 300


def public_error(exc: BaseException) -> str:
    """Короткое описание исключения, пригодное для показа в UI."""
    text = str(exc) or exc.__class__.__name__
    text = _URL.sub("<url>", text)
    text = _PATH.sub("<path>", text)
    text = _TOKEN.sub(r"\1=<hidden>", text)
    text = " ".join(text.split())
    if len(text) > _LIMIT:
        text = text[: _LIMIT - 1] + "…"
    return text
