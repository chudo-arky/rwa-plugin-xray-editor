"""Шаблоны подписок панели (Xray JSON / Mihomo / Stash / Clash / Singbox).

Это ДРУГАЯ сущность, не конфиг-профили: профиль описывает работу ядра на ноде,
а шаблон подписки — то, что отдаётся клиентскому приложению. Админка эти ручки
наружу не проксирует, поэтому ходим в панель напрямую через panel_api().

Формат хранения разный: JSON-шаблоны лежат объектом в templateJson, а YAML
(MIHOMO/CLASH/STASH) — base64-строкой в encodedTemplateYaml. Наружу отдаём
единообразно текстом, а при сохранении кладём в нужное поле.
"""
from __future__ import annotations

from .errors import public_error

import base64
import json
from typing import Any

YAML_TYPES = {"MIHOMO", "CLASH", "STASH"}


def _items(resp: Any) -> list:
    body = (resp or {}).get("response", resp)
    if isinstance(body, dict):
        body = body.get("templates") or body.get("items") or []
    return body or []


async def list_templates(ctx) -> dict:
    from web.backend.core.plugin_api import panel_api

    try:
        resp = await panel_api().get_templates()
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning("xray_editor: subscription templates unavailable: %s", exc)
        return {"items": [], "error": public_error(exc)}
    out = []
    for t in _items(resp):
        out.append({
            "uuid": t.get("uuid"),
            "name": t.get("name"),
            "type": t.get("templateType"),
            "position": t.get("viewPosition"),
        })
    out.sort(key=lambda i: (i.get("position") or 0))
    return {"items": out}


async def get_template(ctx, uuid: str) -> dict:
    from web.backend.core.plugin_api import panel_api

    try:
        resp = await panel_api().get_template(uuid)
    except Exception as exc:  # noqa: BLE001
        return {"error": public_error(exc)}
    body = (resp or {}).get("response", resp) or {}
    ttype = body.get("templateType") or ""
    if ttype in YAML_TYPES:
        raw = body.get("encodedTemplateYaml") or ""
        try:
            text = base64.b64decode(raw).decode("utf-8") if raw else ""
        except Exception:  # noqa: BLE001 — битую base64 показываем как есть
            text = raw
        fmt = "yaml"
    else:
        text = json.dumps(body.get("templateJson") or {}, ensure_ascii=False, indent=2)
        fmt = "json"
    return {"uuid": body.get("uuid"), "name": body.get("name"), "type": ttype, "format": fmt, "text": text}


async def save_template(ctx, uuid: str, ttype: str, text: str) -> dict:
    from web.backend.core.plugin_api import panel_api

    kwargs: dict[str, Any] = {}
    if (ttype or "").upper() in YAML_TYPES:
        kwargs["encoded_template_yaml"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
    else:
        try:
            kwargs["template_json"] = json.loads(text)
        except json.JSONDecodeError as exc:
            return {"error": f"невалидный JSON: {exc}"}
    try:
        await panel_api().update_template(uuid, **kwargs)
    except Exception as exc:  # noqa: BLE001 — текст ошибки панели важен пользователю
        ctx.logger.warning("xray_editor: subscription template save failed: %s", exc)
        return {"error": public_error(exc)}
    return {"ok": True}


async def create_template(ctx, name: str, ttype: str) -> dict:
    """Панель разрешает НЕСКОЛЬКО шаблонов одного типа — проверено на живой."""
    from web.backend.core.plugin_api import panel_api

    try:
        resp = await panel_api().create_template(name, ttype)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning("xray_editor: create subscription template failed: %s", exc)
        return {"error": public_error(exc)}
    body = (resp or {}).get("response", resp) or {}
    return {"uuid": body.get("uuid"), "name": body.get("name"), "type": body.get("templateType")}
