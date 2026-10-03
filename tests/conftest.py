"""Заглушка ``web.backend`` — хост-пакета админки в тестах нет.

Плагин импортирует его лениво внутри функций, поэтому достаточно подложить
модули с минимальным контрактом: ``panel_api()`` подменяется в тестах.
"""
from __future__ import annotations

import logging
import sys
import types

import pytest


class _Panel:
    """Фальшивый клиент панели: ответы задаёт тест через атрибуты."""

    def __init__(self):
        self.templates: list[dict] = []
        self.template: dict = {}
        self.updated: list[tuple] = []
        self.created: list[tuple] = []
        self.fail: Exception | None = None

    async def get_templates(self):
        if self.fail:
            raise self.fail
        return {"response": {"templates": self.templates}}

    async def get_template(self, uuid):
        if self.fail:
            raise self.fail
        return {"response": self.template}

    async def update_template(self, uuid, **kw):
        if self.fail:
            raise self.fail
        self.updated.append((uuid, kw))

    async def create_template(self, name, ttype):
        if self.fail:
            raise self.fail
        self.created.append((name, ttype))
        return {"response": {"uuid": "new-uuid", "name": name, "templateType": ttype}}

    async def generate_x25519(self):
        if self.fail:
            raise self.fail
        return {"response": {"keypairs": [{"privateKey": "priv", "publicKey": "pub"}]}}


PANEL = _Panel()


def _install_stub():
    web = types.ModuleType("web")
    backend = types.ModuleType("web.backend")
    core = types.ModuleType("web.backend.core")
    plugin_api = types.ModuleType("web.backend.core.plugin_api")
    plugin_api.panel_api = lambda: PANEL
    plugin_api.API_VERSION = 1
    for name, mod in (("web", web), ("web.backend", backend), ("web.backend.core", core),
                      ("web.backend.core.plugin_api", plugin_api)):
        sys.modules.setdefault(name, mod)


_install_stub()


class Ctx:
    logger = logging.getLogger("xray_editor.test")


@pytest.fixture
def ctx():
    return Ctx()


@pytest.fixture
def panel():
    PANEL.__init__()
    return PANEL
