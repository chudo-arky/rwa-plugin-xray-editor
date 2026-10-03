"""Галерея шаблонов xray-core из github.com/remnawave/templates (ходит бэкенд)."""
from __future__ import annotations

from .errors import public_error


# ---------------------------------------------------------------------------
# Галерея шаблонов из github.com/remnawave/templates
#
# Ходит бэкенд, а не браузер: CSP админки (connect-src 'self') не пустит
# страницу на внешний хост. Берём только каталоги */xray-core/ — это конфиги
# профилей, которые правит редактор; */subscription-templates/ — другая
# сущность панели (шаблоны подписок), к профилям отношения не имеет.
_TPL_REPO = "remnawave/templates"
_TPL_TTL = 3600.0          # лимит анонимного GitHub API — 60 запросов в час на IP
_tpl_cache: dict = {"at": 0.0, "items": None}
_body_cache: dict = {}


def _pretty_title(path: str) -> str:
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name = name.replace("example-", "").replace("-", " ").replace("_", " ")
    return name[:1].upper() + name[1:]


async def remote_templates(ctx) -> dict:
    import time

    import httpx

    now = time.monotonic()
    if _tpl_cache["items"] is not None and now - _tpl_cache["at"] < _TPL_TTL:
        return {"items": _tpl_cache["items"], "cached": True}

    url = f"https://api.github.com/repos/{_TPL_REPO}/git/trees/main?recursive=1"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            tree = resp.json().get("tree") or []
    except Exception as exc:  # noqa: BLE001 — галерея необязательна, редактор живёт без неё
        ctx.logger.warning("xray_editor: template gallery unavailable: %s", exc)
        return {"items": _tpl_cache["items"] or [], "error": public_error(exc)}

    items = []
    for node in tree:
        path = node.get("path", "")
        if node.get("type") != "blob" or "/xray-core/" not in path or not path.endswith(".json"):
            continue
        author = path.split("/", 1)[0]
        items.append({
            "path": path,
            "title": _pretty_title(path),
            "author": author[3:] if author.startswith("by-") else author,
        })
    items.sort(key=lambda i: (i["author"], i["title"]))
    _tpl_cache["items"] = items
    _tpl_cache["at"] = now
    return {"items": items, "cached": False}


async def remote_template_body(ctx, path: str) -> dict:
    import time

    import httpx

    # путь приходит от клиента — пускаем только то, что реально есть в галерее
    known = {i["path"] for i in (_tpl_cache.get("items") or [])}
    if path not in known:
        fresh = await remote_templates(ctx)
        known = {i["path"] for i in fresh.get("items", [])}
    if path not in known:
        return {"error": "unknown template path"}

    hit = _body_cache.get(path)
    if hit and time.monotonic() - hit[0] < _TPL_TTL:
        return {"config": hit[1]}

    raw = f"https://raw.githubusercontent.com/{_TPL_REPO}/main/{path}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(raw)
            resp.raise_for_status()
            cfg = resp.json()
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning("xray_editor: template %s unavailable: %s", path, exc)
        return {"error": public_error(exc)}

    _body_cache[path] = (time.monotonic(), cfg)
    return {"config": cfg}
