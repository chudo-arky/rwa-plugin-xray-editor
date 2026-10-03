"""xray.py: разбор вердикта ядра (фальшивый бинарь), подсказки, пин релиза, минимальное окружение."""
from __future__ import annotations

import hashlib
import io
import os
import stat
import sys
import zipfile

import pytest

from rwa_xray_editor import xray

POSIX = os.name == "posix"


def test_hints_match_core_messages():
    assert "observatory" in xray._hint_for("not all dependencies are resolved")
    assert "geo-базы" in xray._hint_for("failed to open file geosite.dat")
    assert xray._hint_for("something completely different") is None


def test_pinned_release_url_and_sha_table():
    assert xray.XRAY_VERSION in xray.RELEASE_URL
    assert "latest" not in xray.RELEASE_URL
    assert len(xray.XRAY_SHA256[xray.XRAY_VERSION]) == 64


def _fake_core(tmp_path, body: str) -> str:
    """Скрипт вместо бинаря: печатает заданный текст и выходит с кодом по маркеру."""
    path = tmp_path / "xray"
    code = 0 if "Configuration OK" in body else 1
    path.write_text("#!/bin/sh\nprintenv > \"$(dirname \"$0\")/env.txt\"\n"
                    f"cat <<'EOF'\n{body}\nEOF\nexit {code}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


@pytest.mark.skipif(not POSIX, reason="sh-скрипт вместо бинаря — только POSIX")
def test_check_ok_and_minimal_env(tmp_path, monkeypatch):
    monkeypatch.setattr(xray, "BIN_PATH", _fake_core(tmp_path, "Xray 26.3.27 (Xray, Penetrates Everything.)\n"
                                                              "A unified platform for anti-censorship.\n"
                                                              "[Warning] core: Xray 26.3.27 started\n"
                                                              "Configuration OK."))
    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    r = xray._check_sync({"inbounds": []})
    assert r["ok"] is True and r["version"].startswith("Xray 26.3.27")
    assert len(r["warnings"]) == 1 and r["errors"] == []
    env = (tmp_path / "env.txt").read_text()
    assert "DATABASE_URL" not in env and "XRAY_LOCATION_ASSET=" in env


@pytest.mark.skipif(not POSIX, reason="sh-скрипт вместо бинаря — только POSIX")
def test_check_failure_lines_get_hints(tmp_path, monkeypatch):
    monkeypatch.setattr(xray, "BIN_PATH", _fake_core(tmp_path, "Xray 26.3.27\n"
                                                              "Failed to start: not all dependencies are resolved"))
    r = xray._check_sync({})
    assert r["ok"] is False
    assert r["errors"][0]["text"].startswith("Failed to start")
    assert "observatory" in r["errors"][0]["hint"]


@pytest.mark.asyncio
async def test_check_without_core(ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(xray, "BIN_PATH", str(tmp_path / "missing"))
    assert await xray.check(ctx, {}) == {"available": False}
    assert xray.status() == {"available": False}


class _Resp:
    def __init__(self, data: bytes):
        self._data = data
        self.text = data.decode("utf-8", "replace")

    def raise_for_status(self):
        pass

    async def aiter_bytes(self, n):
        for i in range(0, len(self._data), n):
            yield self._data[i:i + n]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Client:
    """httpx.AsyncClient на замену: отдаёт заранее заданный архив."""
    archive = b""

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url):
        return _Resp(self.archive)

    async def get(self, url):
        return _Resp(b"SHA2-256= " + hashlib.sha256(self.archive).hexdigest().encode())


def _zip_with_binary() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xray", "#!/bin/sh\necho fake\n")
    return buf.getvalue()


@pytest.fixture
def fake_httpx(monkeypatch):
    import types
    mod = types.ModuleType("httpx")
    mod.AsyncClient = _Client
    monkeypatch.setitem(sys.modules, "httpx", mod)
    return _Client


@pytest.mark.asyncio
async def test_download_rejects_sha_mismatch_and_keeps_old_binary(ctx, tmp_path, monkeypatch, fake_httpx):
    monkeypatch.setattr(xray, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(xray, "BIN_PATH", str(tmp_path / "xray"))
    (tmp_path / "xray").write_bytes(b"old")
    fake_httpx.archive = _zip_with_binary()
    monkeypatch.setitem(xray.XRAY_SHA256, xray.XRAY_VERSION, "00" * 32)
    r = await xray.download(ctx)
    assert r["ok"] is False and "sha256" in r["error"]
    assert (tmp_path / "xray").read_bytes() == b"old"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.asyncio
async def test_download_accepts_pinned_sha(ctx, tmp_path, monkeypatch, fake_httpx):
    monkeypatch.setattr(xray, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(xray, "BIN_PATH", str(tmp_path / "xray"))
    fake_httpx.archive = _zip_with_binary()
    monkeypatch.setitem(xray.XRAY_SHA256, xray.XRAY_VERSION, hashlib.sha256(fake_httpx.archive).hexdigest())
    monkeypatch.setattr(xray, "status", lambda: {"available": True})
    r = await xray.download(ctx)
    assert r["ok"] is True
    assert (tmp_path / "xray").read_bytes().startswith(b"#!/bin/sh")


@pytest.mark.asyncio
async def test_download_unpinned_version_uses_dgst(ctx, tmp_path, monkeypatch, fake_httpx):
    monkeypatch.setattr(xray, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(xray, "BIN_PATH", str(tmp_path / "xray"))
    monkeypatch.setattr(xray, "XRAY_VERSION", "v0.0.0-test")
    fake_httpx.archive = _zip_with_binary()
    monkeypatch.setattr(xray, "status", lambda: {"available": True})
    assert (await xray.download(ctx))["ok"] is True


@pytest.mark.asyncio
async def test_download_size_limit(ctx, tmp_path, monkeypatch, fake_httpx):
    monkeypatch.setattr(xray, "BIN_DIR", str(tmp_path))
    monkeypatch.setattr(xray, "BIN_PATH", str(tmp_path / "xray"))
    monkeypatch.setattr(xray, "MAX_ZIP_BYTES", 10)
    fake_httpx.archive = _zip_with_binary()
    monkeypatch.setitem(xray.XRAY_SHA256, xray.XRAY_VERSION, hashlib.sha256(fake_httpx.archive).hexdigest())
    r = await xray.download(ctx)
    assert r["ok"] is False and "large" in r["error"]


def test_neutralize_node_files_replaces_cert_paths(monkeypatch):
    monkeypatch.setattr(xray, "_placeholder_cert", lambda: {"certificate": ["C"], "key": ["K"]})
    cfg = {"inbounds": [{"streamSettings": {"tlsSettings": {"certificates": [
        {"certificateFile": "/var/lib/x/cert.pem", "keyFile": "/var/lib/x/key.pem", "usage": "encipherment"},
        {"certificate": ["inline"], "key": ["inline"]},
    ]}}}], "outbounds": [{"tag": "x"}]}
    out, replaced = xray.neutralize_node_files(cfg)
    certs = out["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"]
    assert certs[0] == {"usage": "encipherment", "certificate": ["C"], "key": ["K"]}
    assert certs[1] == {"certificate": ["inline"], "key": ["inline"]}
    assert sorted(replaced) == ["/var/lib/x/cert.pem", "/var/lib/x/key.pem"]
    assert cfg["inbounds"][0]["streamSettings"]["tlsSettings"]["certificates"][0]["certificateFile"]  # исходник цел
    assert out["outbounds"] == cfg["outbounds"]


def test_neutralize_without_placeholder_keeps_config(monkeypatch):
    monkeypatch.setattr(xray, "_placeholder_cert", lambda: None)
    cfg = {"a": {"certificates": [{"certificateFile": "/x"}]}}
    out, replaced = xray.neutralize_node_files(cfg)
    assert out == cfg and replaced == []


def test_hints_for_node_only_files_and_gfw_warning():
    assert "на ноде" in xray._hint_for("open /var/lib/remnawave/ssl/cert.pem: no such file or directory")
    assert "не ошибка" in xray._hint_for("[Warning] infra/conf: REALITY: Listening on non-443 ports may get your IP blocked by the GFW")
    assert xray._hint_for("failed to build reality config: invalid shortId") is not None


@pytest.mark.skipif(not POSIX, reason="sh-скрипт вместо бинаря — только POSIX")
def test_check_reports_need_geo_and_cert_note(tmp_path, monkeypatch):
    monkeypatch.setattr(xray, "BIN_PATH", _fake_core(tmp_path, "Xray 26.3.27\n"
                        "Failed to start: failed to load GeoIP: private > open /app/geoip/geoip.dat: no such file or directory"))
    monkeypatch.setattr(xray, "_placeholder_cert", lambda: {"certificate": ["C"], "key": ["K"]})
    r = xray._check_sync({"inbounds": [{"streamSettings": {"tlsSettings": {"certificates": [{"certificateFile": "/n/c.pem"}]}}}]})
    assert r["ok"] is False and r["needGeo"] is True
    assert any("сертификаты с ноды" in w["text"] for w in r["warnings"])
