"""Роуты плагина.

Авторизацию плагин объявляет сам: загрузчик вешает только гейт лицензии, и то
лишь платным. Без явного Depends ручки были бы открыты всем, кто дотянулся до
бэкенда.

Роут скрипта называется БЕЗ расширения `.js`: статик-локация nginx фронтенд-
контейнера (regex по расширениям) сильнее префикса `/api/` и ответила бы 404
сама, не доводя запрос до бэкенда.
"""
from __future__ import annotations


_VENDOR_CACHE: dict[str, str] = {}


def _vendor(name: str) -> str:
    """Файл из ``rwa_xray_editor/vendor`` — читается один раз и держится в памяти."""
    if name not in _VENDOR_CACHE:
        import pathlib

        path = pathlib.Path(__file__).parent / "vendor" / name
        _VENDOR_CACHE[name] = path.read_text(encoding="utf-8")
    return _VENDOR_CACHE[name]


def build_router(ctx):
    from fastapi import APIRouter, Depends
    from fastapi.responses import HTMLResponse, Response

    from web.backend.core.plugin_api import auth_deps

    from . import geo as geo_svc
    from . import subs as subs_svc
    from . import xray as xray_svc
    from .data import remote_template_body, remote_templates
    from .tools import reality_keypair, reality_probe, resolve_host
    from .ui import APP_JS, PAGE_HTML

    AdminUser, require_permission = auth_deps()
    router = APIRouter()

    @router.get("/ui", response_class=HTMLResponse, summary="Standalone-страница редактора")
    async def ui(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ):
        return HTMLResponse(PAGE_HTML)

    @router.get("/app", summary="JS редактора (один модуль на standalone и generic-маршрут)")
    async def app_js(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ):
        # Конфиги читаются/пишутся через родное /api/v2/config-profiles
        # (гейт resources:view / resources:edit роли админа), поэтому здесь
        # достаточно собственного xray_editor:view.
        return Response(APP_JS, media_type="application/javascript; charset=utf-8")

    @router.get("/ui-module", summary="UI-модуль для generic-маршрута /plugins/:pluginId (window.rwaPluginUI)")
    async def ui_module(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ):
        # Без расширения .js — иначе перехватит статик-локация nginx фронта.
        # Авторизация — кукой rw_access: <script src> того же origin её шлёт.
        from .module import MODULE_JS

        return Response(MODULE_JS, media_type="application/javascript; charset=utf-8")

    @router.get("/vendor/cm-js", summary="CodeMirror 5 (вендорная копия внутри пакета)")
    async def vendor_cm_js(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ):
        # CSP админки — script-src 'self': библиотеку можно отдать только своим роутом.
        return Response(_vendor("cm.js"), media_type="application/javascript; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=86400"})

    @router.get("/vendor/cm-css", summary="Стили CodeMirror 5")
    async def vendor_cm_css(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ):
        return Response(_vendor("cm.css"), media_type="text/css; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=86400"})

    @router.get("/tools/x25519", summary="Пара ключей Reality (x25519)")
    async def x25519(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await reality_keypair(ctx)

    @router.post("/tools/reality-target", summary="Проба Reality-цели: TLS1.3, H2, покрытие SNI")
    async def reality_target(
        payload: dict,
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        try:
            port = int(payload.get("port") or 443)
        except (TypeError, ValueError):
            return {"ok": False, "error": "port must be a number"}
        if not 1 <= port <= 65535:
            return {"ok": False, "error": "port must be within 1..65535"}
        return await reality_probe(ctx, str(payload.get("address") or ""), port)

    @router.get("/tools/resolve", summary="DNS-резолв домена для трассировщика (только резолв, без соединения)")
    async def resolve(
        host: str = "",
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await resolve_host(ctx, host)

    @router.get("/templates/remote", summary="Галерея шаблонов xray-core из github.com/remnawave/templates")
    async def templates_remote(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        # Ходит на GitHub САМ БЭКЕНД: CSP админки (connect-src 'self') не пустит
        # браузер на внешний хост. Ответ кэшируется на час — галерея меняется редко,
        # а лимит анонимного GitHub API всего 60 запросов в час на IP.
        return await remote_templates(ctx)

    @router.get("/templates/remote/raw", summary="Содержимое шаблона по пути в репозитории")
    async def templates_remote_raw(
        path: str,
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await remote_template_body(ctx, path)

    @router.get("/geo/status", summary="Состояние geo-баз")
    async def geo_status(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return geo_svc.status()

    @router.post("/geo/download", summary="Скачать/обновить geo-базы (~25 МБ)")
    async def geo_download(
        body: dict | None = None,
        _admin: AdminUser = Depends(require_permission("xray_editor", "edit")),
    ) -> dict:
        return await geo_svc.download(ctx, None, (body or {}).get("urls"))

    @router.post("/geo/match", summary="Вердикты по geosite:/geoip: для трассировщика")
    async def geo_match(
        body: dict,
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return geo_svc.match(body.get("domain"), body.get("ip"), body.get("keys") or [])

    @router.get("/subs", summary="Шаблоны подписок панели")
    async def subs_list(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await subs_svc.list_templates(ctx)

    @router.post("/subs", summary="Создать шаблон подписки")
    async def subs_create(
        body: dict,
        _admin: AdminUser = Depends(require_permission("xray_editor", "edit")),
    ) -> dict:
        return await subs_svc.create_template(ctx, body.get("name") or "", body.get("type") or "XRAY_JSON")

    @router.get("/subs/{uuid}", summary="Содержимое шаблона подписки (YAML разворачивается из base64)")
    async def subs_get(
        uuid: str,
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await subs_svc.get_template(ctx, uuid)

    @router.post("/subs/{uuid}", summary="Сохранить шаблон подписки в панель")
    async def subs_save(
        uuid: str,
        body: dict,
        _admin: AdminUser = Depends(require_permission("xray_editor", "edit")),
    ) -> dict:
        return await subs_svc.save_template(ctx, uuid, body.get("type") or "", body.get("text") or "")

    @router.get("/xray/status", summary="Есть ли ядро для проверки конфига")
    async def xray_status(
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return xray_svc.status()

    @router.post("/xray/download", summary="Скачать ядро xray (~20 МБ) в том плагина")
    async def xray_download(
        _admin: AdminUser = Depends(require_permission("xray_editor", "edit")),
    ) -> dict:
        return await xray_svc.download(ctx)

    @router.post("/xray/check", summary="Проверить конфиг настоящим ядром (xray run -test)")
    async def xray_check(
        body: dict,
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return await xray_svc.check(ctx, body.get("config") or {})

    @router.get("/geo/categories", summary="Список geo-категорий с числом элементов")
    async def geo_categories(
        kind: str = "geosite", query: str = "",
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return geo_svc.categories(kind, query)

    @router.get("/geo/entries", summary="Содержимое geo-категории постранично")
    async def geo_entries(
        kind: str, code: str, offset: int = 0, limit: int = 100, query: str = "",
        _admin: AdminUser = Depends(require_permission("xray_editor", "view")),
    ) -> dict:
        return geo_svc.entries(kind, code, offset, limit, query)

    return router
