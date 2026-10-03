"""Встроенный JS: синтаксис парсером node и контракты для админки.

Фронтенд лежит строками в Python — битая строка превращается в молчаливый 404
страницы. Без node тест пропускается (локально), в CI node есть всегда.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from rwa_xray_editor.module import MODULE_JS
from rwa_xray_editor.ui import APP_JS, PAGE_HTML

NODE = shutil.which("node")


def _node_check(tmp_path, name: str, source: str):
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    res = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr


@pytest.mark.skipif(not NODE, reason="node не найден")
def test_app_js_parses(tmp_path):
    _node_check(tmp_path, "app.js", APP_JS)


@pytest.mark.skipif(not NODE, reason="node не найден")
def test_module_js_parses(tmp_path):
    _node_check(tmp_path, "module.js", MODULE_JS)


@pytest.mark.skipif(not NODE, reason="node не найден")
def test_module_registers_plugin_ui_contract(tmp_path):
    """mount/unmount должны появиться в window.rwaPluginUI['xray_editor']."""
    harness = (
        "globalThis.window = globalThis; globalThis.document = {currentScript: null};\n"
        + MODULE_JS
        + "\nconst ui = window.rwaPluginUI.xray_editor;"
        "\nif (typeof ui.mount !== 'function' || typeof ui.unmount !== 'function') process.exit(2);\n"
    )
    path = tmp_path / "harness.js"
    path.write_text(harness, encoding="utf-8")
    res = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr


def test_placeholders_substituted_and_single_dialog_anchors():
    assert "/*__CODE__*/" not in APP_JS and "/*__CODECSS__*/" not in APP_JS
    assert "window.__xrayEditor = { mount: mount, unmount: unmount }" in APP_JS
    # дубликат диалога после правки «вставить перед якорем» — кнопки достаются нижней копии
    for anchor in ("id=\"xed-geo-dl\"", "id=\"xed-check-dl\"", "id=\"xed-cs-log\""):
        assert APP_JS.count(anchor) == 1, anchor


def test_page_html_loads_app_relatively():
    assert '<script src="app" defer></script>' in PAGE_HTML
    assert "<title>Редактор Xray</title>" in PAGE_HTML


@pytest.mark.skipif(not NODE, reason="node не найден")
def test_unmount_removes_body_level_popups(tmp_path):
    """После unmount в body не должно остаться подсказок схемы/автодополнения/линтера."""
    harness = r"""
const mk = (cls) => ({ className: cls, parentNode: null, isConnected: true, style: {} });
const body = { children: [], appendChild(el) { el.parentNode = body; body.children.push(el); },
               removeChild(el) { body.children = body.children.filter(x => x !== el); el.parentNode = null; } };
globalThis.window = globalThis;
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.navigator = { language: 'ru', clipboard: {} };
globalThis.location = { pathname: '/plugins/xray-editor', search: '', origin: 'http://localhost' };
globalThis.document = {
  body, currentScript: null, head: { appendChild() {} },
  getElementById: () => null,
  createElement: (t) => ({ tagName: t, style: {}, setAttribute() {}, appendChild() {}, addEventListener() {}, textContent: '' }),
  addEventListener() {}, removeEventListener() {},
  querySelectorAll: (sel) => body.children.filter(el => sel.split(',').some(s => s.trim().slice(1) === el.className)),
};
globalThis.fetch = () => new Promise(() => {});
globalThis.setInterval = () => 1; globalThis.clearInterval = () => {};
""" + APP_JS + r"""
const tip = mk('xed-cmtip'), hints = mk('CodeMirror-hints');
body.appendChild(tip); body.appendChild(hints);
window.__xrayEditor.unmount();
if (body.children.length !== 0) { console.error('left in body:', body.children.map(x => x.className)); process.exit(3); }
"""
    path = tmp_path / "unmount.js"
    path.write_text(harness, encoding="utf-8")
    res = subprocess.run([NODE, str(path)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr or res.stdout


def test_click_handler_ids_are_bound_once():
    """on(id) вешает обработчик по getElementById: один id — одно назначение.

    Регрессия 0.1.2: вкладка JSON инспектора и верхняя вкладка JSON делили id
    `xed-tab-json`, клик по инспектору уходил на верхнюю вкладку.
    """
    import re
    ids = re.findall(r"on\('([a-z0-9-]+)'", APP_JS)
    dups = sorted({i for i in ids if ids.count(i) > 1})
    assert dups == [], dups


def test_trace_reason_codes_have_texts_in_both_languages():
    """Каждый code причины трассировщика должен иметь текст в trR обоих языков."""
    import re
    codes = set(re.findall(r"code: '([a-z0-9_]+)'", APP_JS))
    for m in re.finditer(r"\{ yes: '([a-z0-9_]+)', unknown: '([a-z0-9_]+)', no: '([a-z0-9_]+)' \}", APP_JS):
        codes |= set(m.groups())
    codes |= set(re.findall(r"matchExactField\([^)]*'([a-z]+_need)'\)", APP_JS))
    codes |= {"geo_need", "exact_hit", "exact_miss", "port_hit", "port_miss", "net_hit", "net_miss", "ip_asis", "ip_pass1"}
    codes -= {"geo_off", "geo_missing", "sniff_blind", "need_ip_pass"}   # оговорки рисует trCaveatHtml, не trR
    assert len(codes) > 12, codes
    dicts = re.findall(r"trR: \{(.*?)\n      \},", APP_JS, re.S)
    assert len(dicts) == 2, "ожидались словари trR для ru и en"
    for d in dicts:
        have = set(re.findall(r"([a-z0-9_]+):", d))
        missing = sorted(c for c in codes if c not in have)
        assert missing == [], missing
