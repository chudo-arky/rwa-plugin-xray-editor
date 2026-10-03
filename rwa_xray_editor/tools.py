"""Серверные инструменты редактора: ключи Reality и проба Reality-цели.

Порт соответствующих ручек VAQYBIN (`backend/src/tools/*`) на Python. Проба
делает настоящее TLS-рукопожатие: цель для Reality обязана уметь TLS 1.3 и
(желательно) H2, а её сертификат — покрывать выбранный SNI.

SSRF-защита: адреса приватных/loopback-диапазонов отклоняются — параметр
приходит из браузера, ходить по внутренней сети по такой команде нельзя.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import ssl
from typing import Any

from .errors import public_error

# Проба — настоящее TLS-рукопожатие с чужим хостом до 12 с; больше пары разом не нужно.
_probe_sem = asyncio.Semaphore(2)


async def reality_keypair(ctx) -> dict:
    """x25519-пара. Панель умеет это сама — не тащим свою криптографию."""
    from web.backend.core.plugin_api import panel_api

    try:
        resp = await panel_api().generate_x25519()
    except Exception:  # noqa: BLE001
        ctx.logger.exception("xray_editor: x25519 generation failed")
        return {"ok": False, "error": "panel x25519 unavailable"}
    data = ((resp or {}).get("response") or {})
    pairs = data.get("keypairs") or [data]
    first = pairs[0] if pairs else {}
    return {
        "ok": True,
        "privateKey": first.get("privateKey"),
        "publicKey": first.get("publicKey"),
    }


def _resolve_public(host: str) -> str | None:
    """Один публичный IP цели или None, если имя не резолвится либо ведёт внутрь.

    Резолвим РОВНО ОДИН РАЗ и соединяемся по этому адресу: иначе между проверкой
    и соединением DNS может подсунуть другой ответ (rebinding), и проверка
    приватных диапазонов ничего не стоит.
    """
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except Exception:  # noqa: BLE001 — не резолвится: наружу всё равно не пойдём
        return None
    chosen = None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return None
        if chosen is None:
            chosen = str(ip)
    return chosen


def _probe_sync(address: str, ip: str, port: int) -> dict[str, Any]:
    ctxs = ssl.create_default_context()
    ctxs.check_hostname = False
    ctxs.verify_mode = ssl.CERT_NONE
    ctxs.set_alpn_protocols(["h2", "http/1.1"])
    ctxs.minimum_version = ssl.TLSVersion.TLSv1_2

    with socket.create_connection((ip, port), timeout=8) as raw:
        with ctxs.wrap_socket(raw, server_hostname=address) as tls:
            cert = tls.getpeercert()
            names = []
            for typ, val in (cert or {}).get("subjectAltName", ()):
                if typ == "DNS":
                    names.append(val)
            return {
                "ok": True,
                "tlsVersion": tls.version(),
                "tls13": tls.version() == "TLSv1.3",
                "alpn": tls.selected_alpn_protocol(),
                "h2": tls.selected_alpn_protocol() == "h2",
                "sanCount": len(names),
                "sanSample": names[:8],
                "covers": _covers(address, names),
                "notAfter": (cert or {}).get("notAfter"),
            }


def _covers(host: str, names: list[str]) -> bool:
    """Покрывает ли сертификат имя, с корректным разбором wildcard (*.a.b)."""
    host = host.lower().rstrip(".")
    for n in names:
        n = n.lower().rstrip(".")
        if n == host:
            return True
        if n.startswith("*."):
            # wildcard кроет ровно один уровень: *.a.b подходит x.a.b, но не y.x.a.b
            suffix = n[1:]
            if host.endswith(suffix) and host.count(".") == n.count("."):
                return True
    return False


async def reality_probe(ctx, address: str, port: int = 443) -> dict:
    address = (address or "").strip()
    if not address:
        return {"ok": False, "error": "empty address"}
    if not 1 <= int(port) <= 65535:
        return {"ok": False, "error": "port must be within 1..65535"}
    ip = await asyncio.to_thread(_resolve_public, address)
    if ip is None:
        return {"ok": False, "error": "адрес не резолвится или ведёт во внутреннюю сеть — проба отклонена"}
    try:
        async with _probe_sem:
            return await asyncio.wait_for(asyncio.to_thread(_probe_sync, address, ip, port), timeout=12)
    except Exception as exc:  # noqa: BLE001 — диагностический инструмент, показываем причину
        ctx.logger.info("xray_editor: reality probe failed for %s:%s (%s)", address, port, exc)
        return {"ok": False, "error": public_error(exc)}


_HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$", re.I)


def _resolve_all(host: str) -> list[str]:
    seen: list[str] = []
    for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        addr = info[4][0]
        if addr not in seen:
            seen.append(addr)
    # IPv4 вперёд: правила в конфигах почти всегда про v4, и в поле попадёт первый
    seen.sort(key=lambda a: ipaddress.ip_address(a).version)
    return seen[:8]


async def resolve_host(ctx, host: str) -> dict:
    """DNS-резолв для трассировщика: «узнать IP домена» без nslookup на стороне админа.

    Только резолв, без соединения — поэтому приватные адреса не фильтруем:
    показать, что домен ведёт в 10.x, безопасно и даже полезно для трассы.
    """
    host = (host or "").strip().rstrip(".")
    if not host:
        return {"ok": False, "error": "empty host"}
    try:
        return {"ok": True, "ips": [str(ipaddress.ip_address(host))]}
    except ValueError:
        pass
    if not _HOST_RE.match(host):
        return {"ok": False, "error": "bad hostname"}
    try:
        ips = await asyncio.wait_for(asyncio.to_thread(_resolve_all, host), timeout=5)
    except Exception as exc:  # noqa: BLE001 — NXDOMAIN/таймаут показываем как причину
        return {"ok": False, "error": public_error(exc), "ips": []}
    return {"ok": True, "ips": ips}
