"""Xray Editor — визуальный редактор конфиг-профилей для remnawave-admin.

Порт функциональности VAQYBIN/Remnawave-Xray-UI-Editor в формат плагина
(Plugin API v1): граф топологии, формы по протоколам, линтер целостности,
трассировщик маршрута, рецепты. UI — vanilla JS + SVG, без сборки: CSP
бэкенда ``script-src 'self'`` не пропускает инлайн-скрипты и CDN.

Запись конфигов идёт через РОДНОЕ API админки
(``PATCH /api/v2/config-profiles/{uuid}``), поэтому версионирование
(``config_versions``), RBAC ``resources:edit`` и аудит достаются даром.

Импорты из ``web.backend.*`` отложены внутрь функций, чтобы пакет
импортировался в изоляции (в т.ч. при сборке wheel).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PLUGIN_ID = "xray_editor"
PLUGIN_NAME = "Редактор Xray"
DIST_NAME = "rwa-plugin-xray-editor"


def _own_version() -> str:
    """Версия — из метаданных пакета: вторая константа неизбежно разъедется."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(DIST_NAME)
    except PackageNotFoundError:  # запуск из исходников, не из wheel
        return "0.0.0"


__version__ = _own_version()


def _build(ctx):
    # Права суперадмина на ресурсы плагина админка с 4.5.0 синхронизирует сама
    # ПОСЛЕ register() (main.py), своя фоновая задача rbac-sync больше не нужна.
    from web.backend.core.plugins import PluginParts

    from .routes import build_router

    return PluginParts(router=build_router(ctx))


def _ui_kwargs() -> dict:
    """Объявить страницу для generic-маршрута, если админка его умеет.

    ``PluginUI`` появился в remnawave-admin 4.5.4 вместе с маршрутом
    ``/plugins/:pluginId`` (PR #267). На старых версиях класса нет — тогда
    ничего не объявляем: остаётся пункт меню и standalone-страница ``/ui``.
    """
    try:
        from web.backend.core.plugins import PluginUI
    except ImportError:
        return {}
    return {"ui": PluginUI(kind="module", path="/ui-module")}


def manifest():
    from web.backend.core.plugins import NavEntry, PluginManifest

    # label_i18n — человеческий текст (переводы плагинов лежат во фронтенд-бандле,
    # свой ключ туда не добавить; i18next вернёт сам ключ, то есть подпись).
    # icon — только из ICON_MAP фронтенда, иначе пусто.
    return PluginManifest(
        id=PLUGIN_ID,
        name=PLUGIN_NAME,
        version=__version__,
        api_version=1,
        billing="free",
        build=_build,
        rbac_resources={"xray_editor": ["view"]},
        navigation=[
            NavEntry(
                path="/plugins/xray-editor",
                label_i18n="Редактор Xray",
                icon="Wrench",
                permission=("xray_editor", "view"),
                section_i18n="nav.sections.plugins",
            ),
        ],
        **_ui_kwargs(),
    )
