import pytest

from rwa_xray_editor import tools


@pytest.mark.parametrize("host,names,ok", [
    ("www.example.com", ["www.example.com"], True),
    ("www.example.com", ["*.example.com"], True),
    ("a.b.example.com", ["*.example.com"], False),        # wildcard — ровно один уровень
    ("example.com", ["*.example.com"], False),
    ("WWW.Example.COM.", ["www.example.com"], True),
    ("www.example.com", ["other.com"], False),
])
def test_covers(host, names, ok):
    assert tools._covers(host, names) is ok


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.2", "192.168.1.1", "169.254.1.1", "::1", "0.0.0.0",
                                  "224.0.0.1", "definitely-not-a-host.invalid"])
def test_resolve_public_rejects_internal_and_unresolvable(host):
    assert tools._resolve_public(host) is None


def test_resolve_public_accepts_public_ip_literal():
    assert tools._resolve_public("1.1.1.1") == "1.1.1.1"


@pytest.mark.asyncio
async def test_probe_validates_before_network(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_probe_sync", lambda *a: pytest.fail("network must not be touched"))
    assert (await tools.reality_probe(ctx, "", 443))["ok"] is False
    assert "port" in (await tools.reality_probe(ctx, "1.1.1.1", 70000))["error"]
    r = await tools.reality_probe(ctx, "10.0.0.1", 443)
    assert r["ok"] is False and "внутренн" in r["error"]


@pytest.mark.asyncio
async def test_probe_connects_to_resolved_ip_once(ctx, monkeypatch):
    seen = {}

    def fake_probe(address, ip, port):
        seen.update(address=address, ip=ip, port=port)
        return {"ok": True}

    monkeypatch.setattr(tools, "_resolve_public", lambda host: "93.184.216.34")
    monkeypatch.setattr(tools, "_probe_sync", fake_probe)
    assert (await tools.reality_probe(ctx, "www.example.com", 443))["ok"] is True
    assert seen == {"address": "www.example.com", "ip": "93.184.216.34", "port": 443}


@pytest.mark.asyncio
async def test_probe_error_is_sanitized(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_resolve_public", lambda host: "93.184.216.34")

    def boom(*a):
        raise OSError("connect https://93.184.216.34:443 refused /app/secret")

    monkeypatch.setattr(tools, "_probe_sync", boom)
    r = await tools.reality_probe(ctx, "www.example.com", 443)
    assert r["ok"] is False and "93.184" not in r["error"] and "/app/" not in r["error"]


@pytest.mark.asyncio
async def test_keypair_via_panel(ctx, panel):
    r = await tools.reality_keypair(ctx)
    assert r == {"ok": True, "privateKey": "priv", "publicKey": "pub"}
    panel.fail = RuntimeError("panel down https://10.0.0.2")
    r = await tools.reality_keypair(ctx)
    assert r["ok"] is False and "10.0.0.2" not in r["error"]


@pytest.mark.asyncio
async def test_resolve_ip_literal_and_bad_names(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_resolve_all", lambda host: pytest.fail("no DNS for literals"))
    assert await tools.resolve_host(ctx, " 1.1.1.1 ") == {"ok": True, "ips": ["1.1.1.1"]}
    assert (await tools.resolve_host(ctx, ""))["ok"] is False
    assert (await tools.resolve_host(ctx, "bad host!"))["ok"] is False
    assert (await tools.resolve_host(ctx, "-leading.example.com"))["ok"] is False


@pytest.mark.asyncio
async def test_resolve_returns_v4_first_and_sanitized_errors(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_resolve_all", lambda host: ["2a00:1450::8", "142.250.74.206"])
    r = await tools.resolve_host(ctx, "youtube.com.")
    assert r == {"ok": True, "ips": ["2a00:1450::8", "142.250.74.206"]}   # порядок задаёт _resolve_all

    def boom(host):
        raise OSError("getaddrinfo failed for /etc/hosts http://10.0.0.1")

    monkeypatch.setattr(tools, "_resolve_all", boom)
    r = await tools.resolve_host(ctx, "nope.invalid")
    assert r["ok"] is False and r["ips"] == [] and "10.0.0.1" not in r["error"]


def test_resolve_all_puts_ipv4_first(monkeypatch):
    fake = [(None, None, None, None, ("2a00:1450::8", 0, 0, 0)), (None, None, None, None, ("142.250.74.206", 0)),
            (None, None, None, None, ("142.250.74.206", 0))]
    monkeypatch.setattr(tools.socket, "getaddrinfo", lambda *a, **k: fake)
    assert tools._resolve_all("youtube.com") == ["142.250.74.206", "2a00:1450::8"]
