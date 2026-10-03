"""geo.py: разбор protobuf-баз вручную собранными файлами, match/categories/entries, allow-list."""
from __future__ import annotations

import ipaddress

import pytest

from rwa_xray_editor import geo


# ---- минимальный protobuf-кодер под схемы geosite.proto / geoip.proto ----
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _ld(field: int, payload: bytes) -> bytes:        # length-delimited
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def _vi(field: int, value: int) -> bytes:            # varint field
    return _varint(field << 3 | 0) + _varint(value)


def geosite(entries: dict[str, list[tuple[int, str]]]) -> bytes:
    out = b""
    for code, domains in entries.items():
        body = _ld(1, code.encode())
        for dtype, value in domains:
            body += _ld(2, _vi(1, dtype) + _ld(2, value.encode()))
        out += _ld(1, body)
    return out


def geoip(entries: dict[str, list[str]], reverse: set[str] = frozenset()) -> bytes:
    out = b""
    for code, cidrs in entries.items():
        body = _ld(1, code.encode())
        for cidr in cidrs:
            net = ipaddress.ip_network(cidr)
            body += _ld(2, _ld(1, net.network_address.packed) + _vi(2, net.prefixlen))
        if code in reverse:
            body += _vi(3, 1)
        out += _ld(1, body)
    return out


@pytest.fixture
def geodir(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "GEO_DIR", str(tmp_path))
    geo._index.clear()
    geo._index_mtime.clear()
    geo._cache.clear()
    (tmp_path / geo.GEOSITE).write_bytes(geosite({
        "openai": [(2, "openai.com"), (3, "chat.openai.com"), (0, "chatgpt")],
        "ru": [(1, r"\.ru$")],
    }))
    (tmp_path / geo.GEOIP).write_bytes(geoip({
        "ru": ["5.8.0.0/16", "2a00:1450::/32"],
        "private": ["10.0.0.0/8"],
    }))
    return tmp_path


def test_status_and_categories(geodir):
    st = geo.status()
    assert st[geo.GEOSITE]["present"] and st[geo.GEOSITE]["categories"] == 2
    assert st[geo.GEOIP]["categories"] == 2
    cats = geo.categories("geosite")
    assert {c["code"] for c in cats["items"]} == {"OPENAI", "RU"}
    assert geo.categories("geosite", query="open")["items"][0]["code"] == "OPENAI"


def test_entries_paginated(geodir):
    page = geo.entries("geosite", "openai", offset=0, limit=2)
    assert page["total"] == 3 and len(page["items"]) == 2
    kinds = {e["kind"] for e in geo.entries("geosite", "openai", limit=100)["items"]}
    assert kinds >= {"domain", "full"}
    ips = geo.entries("geoip", "ru", limit=100)["items"]
    assert {e["value"] for e in ips} == {"5.8.0.0/16", "2a00:1450::/32"}


def test_match_domain_types(geodir):
    r = geo.match("api.openai.com", None, ["geosite:openai", "geosite:ru", "geosite:nope"])
    assert r["loaded"] is True
    assert r["answers"]["geosite:openai"] is True      # суффикс
    assert r["answers"]["geosite:ru"] is False
    assert r["missing"] == ["geosite:nope"]
    assert geo.match("chat.openai.com", None, ["geosite:openai"])["answers"]["geosite:openai"] is True
    assert geo.match("yandex.ru", None, ["geosite:ru"])["answers"]["geosite:ru"] is True   # regex
    assert geo.match("mychatgpt.io", None, ["geosite:openai"])["answers"]["geosite:openai"] is True  # plain


def test_match_ip_and_inverted_key_answers_base_category(geodir):
    r = geo.match(None, "5.8.1.1", ["geoip:ru", "geoip:!ru", "geoip:private"])
    assert r["answers"]["geoip:ru"] is True
    assert r["answers"]["geoip:!ru"] is True            # инверсию применяет клиент
    assert r["answers"]["geoip:private"] is False
    assert geo.match(None, "2a00:1450::8", ["geoip:ru"])["answers"]["geoip:ru"] is True


def test_match_without_databases(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "GEO_DIR", str(tmp_path / "empty"))
    geo._index.clear()
    geo._cache.clear()
    r = geo.match("a.com", "1.1.1.1", ["geosite:x", "geoip:y"])
    assert r == {"loaded": False, "answers": {}, "missing": []}


@pytest.mark.parametrize("url,ok", [
    ("https://github.com/v2fly/geoip/releases/latest/download/geoip.dat", True),
    ("https://raw.githubusercontent.com/x/y/main/geosite.dat", True),
    ("https://evil.example/geoip.dat", False),
    ("http://github.com/x", False),
    ("https://user@github.com/x", False),
    ("https://github.com.evil/x", False),
    ("", False),
    (None, False),
])
def test_allowed_url(url, ok):
    assert geo._allowed_url(url) is ok


@pytest.mark.asyncio
async def test_download_rejects_foreign_source_without_network(ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(geo, "GEO_DIR", str(tmp_path))
    monkeypatch.setattr(geo, "SOURCES", {})           # ничего не качать
    r = await geo.download(ctx, None, {"geosite.dat": "https://evil.example/x"})
    assert r["downloaded"] == [] and "geosite.dat" not in r["errors"]   # ключа нет в SOURCES — игнор
    monkeypatch.setattr(geo, "SOURCES", {"geosite.dat": "https://github.com/a"})
    # единственная цель отклонена → список целей пуст, в сеть не ходим
    r = await geo.download(ctx, None, {"geosite.dat": "https://evil.example/x"})
    assert "отклонён" in r["errors"]["geosite.dat"]
    assert r["downloaded"] == []
