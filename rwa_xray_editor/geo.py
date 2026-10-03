"""Geo-базы xray (geosite.dat / geoip.dat) для трассировщика.

Зачем свой сервис: ядро xray умеет ПРИМЕНЯТЬ geo-правила, но не отвечает на
вопрос «входит ли домен в geosite:openai» — API у него нет. Сами базы лежат в
образе ноды, а трассировщик считает вердикты там, где работает плагин, поэтому
файлы нужны рядом с админкой.

Память дороже диска: машина маленькая, а файлы на 28 МБ в питоновских структурах
разрослись бы до сотен мегабайт. Поэтому один потоковый проход строит индекс
«категория → (смещение, длина)», а тело категории декодируется по требованию и
кладётся в маленький LRU. Формат — protobuf, но схема крошечная, поэтому
разбираем вручную (см. geoip.proto / geosite.proto в v2fly):

    GeoSite  { country_code = 1 (string); domain = 2 (repeated Domain) }
    Domain   { type = 1 (enum: 0 plain, 1 regex, 2 domain, 3 full); value = 2 }
    GeoIP    { country_code = 1; cidr = 2 (repeated CIDR); reverse_match = 3 }
    CIDR     { ip = 1 (bytes); prefix = 2 (uint32) }
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit

from .errors import public_error

GEO_DIR = os.environ.get("XED_GEO_DIR", "/app/geoip")
GEOSITE = "geosite.dat"
GEOIP = "geoip.dat"

# Официальные сборки v2fly — те же, что кладут в образы нод.
SOURCES = {
    GEOSITE: "https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat",
    GEOIP: "https://github.com/v2fly/geoip/releases/latest/download/geoip.dat",
}

# Откуда разрешено качать: адрес приходит из браузера, а бэкенд ходит по нему
# сам — без списка это SSRF «скачай что угодно и положи на диск».
ALLOWED_HOSTS = {"github.com", "raw.githubusercontent.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com"}
MAX_GEO_BYTES = 128 * 1024 * 1024
_download_lock = asyncio.Lock()

_index: dict[str, dict[str, tuple[int, int]]] = {}   # файл → {КАТЕГОРИЯ: (offset, size)}
_index_mtime: dict[str, float] = {}
_cache: OrderedDict[str, Any] = OrderedDict()        # 'geosite:CODE' → разобранное тело
_CACHE_MAX = 12


def _path(name: str) -> str:
    return os.path.join(GEO_DIR, name)


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def _build_index(name: str) -> dict[str, tuple[int, int]]:
    """Потоковый проход по верхнему уровню: только имена категорий и границы."""
    path = _path(name)
    idx: dict[str, tuple[int, int]] = {}
    with open(path, "rb") as fh:
        data = fh.read()
    pos, size = 0, len(data)
    while pos < size:
        tag, pos = _read_varint(data, pos)
        if tag & 0x07 != 2:            # верхний уровень — только length-delimited entry
            break
        length, pos = _read_varint(data, pos)
        entry_start, entry_end = pos, pos + length
        # внутри entry первым полем идёт country_code — читаем только его
        p = entry_start
        code = ""
        while p < entry_end:
            t, p = _read_varint(data, p)
            field, wire = t >> 3, t & 0x07
            if wire == 2:
                ln, p = _read_varint(data, p)
                if field == 1:
                    code = data[p:p + ln].decode("utf-8", "replace")
                    break                # дальше в теле только домены/сети — пропускаем
                p += ln
            elif wire == 0:
                _, p = _read_varint(data, p)
            else:
                break
        if code:
            # считаем элементы, не декодируя их: только теги поля 2 внутри entry
            cnt, q = 0, entry_start
            while q < entry_end:
                t3, q = _read_varint(data, q)
                f3, w3 = t3 >> 3, t3 & 0x07
                if w3 == 2:
                    l3, q = _read_varint(data, q)
                    if f3 == 2:
                        cnt += 1
                    q += l3
                elif w3 == 0:
                    _, q = _read_varint(data, q)
                else:
                    break
            idx[code.upper()] = (entry_start, length, cnt)
        pos = entry_end
    return idx


def _ensure_index(name: str) -> dict[str, tuple[int, int]] | None:
    path = _path(name)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    if _index.get(name) is None or _index_mtime.get(name) != mtime:
        _index[name] = _build_index(name)
        _index_mtime[name] = mtime
    return _index[name]


def _entry_bytes(name: str, code: str) -> bytes | None:
    idx = _ensure_index(name)
    if not idx:
        return None
    hit = idx.get(code.upper())
    if not hit:
        return None
    offset, length = hit[0], hit[1]
    with open(_path(name), "rb") as fh:
        fh.seek(offset)
        return fh.read(length)


def _cache_put(key: str, value: Any) -> Any:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return value


def _parse_domains(blob: bytes) -> list[tuple[int, str]]:
    """[(type, value)] — type: 0 plain, 1 regex, 2 domain(суффикс), 3 full."""
    out: list[tuple[int, str]] = []
    pos, size = 0, len(blob)
    while pos < size:
        tag, pos = _read_varint(blob, pos)
        field, wire = tag >> 3, tag & 0x07
        if wire == 2:
            ln, pos = _read_varint(blob, pos)
            chunk = blob[pos:pos + ln]
            pos += ln
            if field == 2:                       # Domain
                dtype, value, p2 = 0, "", 0
                while p2 < len(chunk):
                    t2, p2 = _read_varint(chunk, p2)
                    f2, w2 = t2 >> 3, t2 & 0x07
                    if w2 == 0:
                        v2, p2 = _read_varint(chunk, p2)
                        if f2 == 1:
                            dtype = v2
                    elif w2 == 2:
                        l2, p2 = _read_varint(chunk, p2)
                        if f2 == 2:
                            value = chunk[p2:p2 + l2].decode("utf-8", "replace")
                        p2 += l2
                    else:
                        break
                if value:
                    out.append((dtype, value))
        elif wire == 0:
            _, pos = _read_varint(blob, pos)
        else:
            break
    return out


def _parse_cidrs(blob: bytes) -> tuple[list[tuple[int, int, int]], bool]:
    """([(int_адрес, длина_префикса, версия)], reverse_match)."""
    nets: list[tuple[int, int, int]] = []
    reverse = False
    pos, size = 0, len(blob)
    while pos < size:
        tag, pos = _read_varint(blob, pos)
        field, wire = tag >> 3, tag & 0x07
        if wire == 2:
            ln, pos = _read_varint(blob, pos)
            chunk = blob[pos:pos + ln]
            pos += ln
            if field == 2:                       # CIDR
                ip_raw, prefix, p2 = b"", 0, 0
                while p2 < len(chunk):
                    t2, p2 = _read_varint(chunk, p2)
                    f2, w2 = t2 >> 3, t2 & 0x07
                    if w2 == 2:
                        l2, p2 = _read_varint(chunk, p2)
                        if f2 == 1:
                            ip_raw = chunk[p2:p2 + l2]
                        p2 += l2
                    elif w2 == 0:
                        v2, p2 = _read_varint(chunk, p2)
                        if f2 == 2:
                            prefix = v2
                    else:
                        break
                if ip_raw:
                    nets.append((int.from_bytes(ip_raw, "big"), prefix, len(ip_raw) * 8))
        elif wire == 0:
            v, pos = _read_varint(blob, pos)
            if field == 3:
                reverse = bool(v)
        else:
            break
    return nets, reverse


def _domains_of(code: str) -> list[tuple[int, str]] | None:
    key = "geosite:" + code.upper()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    blob = _entry_bytes(GEOSITE, code)
    if blob is None:
        return None
    return _cache_put(key, _parse_domains(blob))


def _cidrs_of(code: str):
    key = "geoip:" + code.upper()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    blob = _entry_bytes(GEOIP, code)
    if blob is None:
        return None
    return _cache_put(key, _parse_cidrs(blob))


def _domain_hit(domains: list[tuple[int, str]], host: str) -> bool:
    host = host.lower().rstrip(".")
    for dtype, value in domains:
        v = value.lower()
        if dtype == 3:                                  # full
            if host == v:
                return True
        elif dtype == 2:                                # domain (суффикс)
            if host == v or host.endswith("." + v):
                return True
        elif dtype == 1:                                # regexp
            try:
                if re.search(value, host):
                    return True
            except re.error:
                continue
        else:                                           # plain (подстрока)
            if v in host:
                return True
    return False


def _ip_hit(nets, ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    bits = int(addr)
    size = 32 if addr.version == 4 else 128
    for net_int, prefix, net_size in nets:
        if net_size != size:
            continue
        mask = ((1 << prefix) - 1) << (size - prefix) if prefix else 0
        if (bits & mask) == (net_int & mask):
            return True
    return False


PRESETS = {
    "v2fly": {
        GEOSITE: "https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat",
        GEOIP: "https://github.com/v2fly/geoip/releases/latest/download/geoip.dat",
    },
    "loyalsoldier": {
        GEOSITE: "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat",
        GEOIP: "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat",
    },
}


def categories(kind: str, query: str = "", limit: int = 400) -> dict:
    """Список категорий с числом элементов — для вкладки просмотра."""
    name = GEOSITE if kind == "geosite" else GEOIP
    idx = _ensure_index(name)
    if idx is None:
        return {"items": [], "present": False}
    q = (query or "").strip().upper()
    items = [
        {"code": code, "count": (hit[2] if len(hit) > 2 else 0)}
        for code, hit in idx.items()
        if not q or q in code
    ]
    items.sort(key=lambda i: i["code"])
    return {"items": items[:limit], "total": len(items), "present": True}


def entries(kind: str, code: str, offset: int = 0, limit: int = 100, query: str = "") -> dict:
    """Содержимое категории постранично."""
    if kind == "geosite":
        rows = _domains_of(code)
        if rows is None:
            return {"items": [], "total": 0}
        types = {0: "plain", 1: "regexp", 2: "domain", 3: "full"}
        data = [{"kind": types.get(t, str(t)), "value": v} for t, v in rows]
    else:
        parsed = _cidrs_of(code)
        if parsed is None:
            return {"items": [], "total": 0}
        nets, reverse = parsed
        data = []
        for net_int, prefix, size in nets:
            try:
                addr = ipaddress.ip_address(net_int if size == 32 else net_int)
                if size == 128:
                    addr = ipaddress.IPv6Address(net_int)
                else:
                    addr = ipaddress.IPv4Address(net_int)
                data.append({"kind": "cidr", "value": f"{addr}/{prefix}"})
            except Exception:  # noqa: BLE001
                continue
    q = (query or "").strip().lower()
    if q:
        data = [d for d in data if q in d["value"].lower()]
    total = len(data)
    return {"items": data[offset:offset + limit], "total": total, "offset": offset}


def status() -> dict:
    out = {}
    for name in (GEOSITE, GEOIP):
        path = _path(name)
        if os.path.exists(path):
            idx = _ensure_index(name) or {}
            out[name] = {
                "present": True,
                "size": os.path.getsize(path),
                "mtime": os.path.getmtime(path),
                "categories": len(idx),
            }
        else:
            out[name] = {"present": False}
    return out


def _allowed_url(url: Any) -> bool:
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    parts = urlsplit(url)
    return parts.hostname in ALLOWED_HOSTS and not parts.username and not parts.password


async def download(ctx, which: str | None = None, urls: dict | None = None) -> dict:
    """Качает базы в том плагина. Файлы ~28 МБ, поэтому пишем потоком.

    urls позволяет взять другой источник (пресеты v2fly/Loyalsoldier или свой
    релиз на GitHub) — важно держать базы теми же, что стоят на нодах, иначе
    вердикты трассировщика разойдутся с реальностью. Хосты — только из
    ``ALLOWED_HOSTS``, размер — до ``MAX_GEO_BYTES``.
    """
    import httpx

    if _download_lock.locked():
        return {"downloaded": [], "errors": {"*": "загрузка уже идёт"}, "status": status()}
    src = dict(SOURCES)
    errors: dict[str, str] = {}
    for k, v in (urls or {}).items():
        if k not in src or not v:
            continue
        if _allowed_url(v):
            src[k] = v
        else:
            errors[k] = "источник отклонён: разрешены только https-ссылки на " + ", ".join(sorted(ALLOWED_HOSTS))
    targets = [which] if which in src else [n for n in src if n not in errors]
    done = []
    async with _download_lock:
        os.makedirs(GEO_DIR, exist_ok=True)
        for name in targets:
            url = src[name]
            tmp = _path(name) + ".part"
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        total = 0
                        with open(tmp, "wb") as fh:
                            async for chunk in resp.aiter_bytes(65536):
                                total += len(chunk)
                                if total > MAX_GEO_BYTES:
                                    raise RuntimeError("file is too large")
                                fh.write(chunk)
                os.replace(tmp, _path(name))
                _index.pop(name, None)          # индекс перестроится при следующем запросе
                _cache.clear()
                done.append(name)
            except Exception as exc:  # noqa: BLE001 — трассировщик работает и без баз
                ctx.logger.warning("xray_editor: geo download %s failed: %s", name, exc)
                errors[name] = public_error(exc)
                if os.path.exists(tmp):
                    os.remove(tmp)
    return {"downloaded": done, "errors": errors, "status": status()}


def match(domain: str | None, ip: str | None, keys: list[str]) -> dict:
    """Контракт как у оригинала: {loaded, answers, missing}.

    ⚠ Ключ с инверсией (`geoip:!ru`) нормализуем: отвечаем ПО БАЗОВОЙ категории,
    а инверсию применяет клиент. В оригинале здесь рассинхрон — он шлёт ключ с
    «!», а сверяется по ключу без «!», и вердикт всегда выходил «нет данных».
    """
    answers: dict[str, bool] = {}
    missing: list[str] = []
    loaded = False
    for key in keys:
        raw = str(key)
        if raw.startswith("geosite:"):
            body = raw[8:]
        elif raw.startswith("geoip:"):
            body = raw[6:]
        else:
            continue
        body = body.lstrip("!")
        code, _, attr = body.partition("@")
        if raw.startswith("geosite:"):
            if domain is None:
                continue
            domains = _domains_of(code)
            if domains is None:
                if _ensure_index(GEOSITE) is None:
                    continue                       # базы нет — вопрос остаётся без ответа
                if code.upper() not in (_ensure_index(GEOSITE) or {}):
                    if raw not in missing:
                        missing.append(raw)
                continue
            loaded = True
            answers[raw] = _domain_hit(domains, domain)
        else:
            if ip is None:
                continue
            parsed = _cidrs_of(code)
            if parsed is None:
                if _ensure_index(GEOIP) is None:
                    continue
                if code.upper() not in (_ensure_index(GEOIP) or {}):
                    if raw not in missing:
                        missing.append(raw)
                continue
            loaded = True
            nets, reverse = parsed
            hit = _ip_hit(nets, ip)
            if reverse:
                hit = not hit
            answers[raw] = hit
    return {"loaded": loaded, "answers": answers, "missing": missing}
