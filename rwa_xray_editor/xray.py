"""Проверка конфига настоящим ядром xray (`xray run -test`).

Ядро в контейнере админки не поставляется, поэтому бинарь качается в том плагина
рядом с geo-базами. Это единственный способ узнать вердикт САМОГО ядра: наш
линтер знает семантику (битые ссылки, пустой балансер), но не знает всех
ограничений реализации, а ядро — наоборот. Проверки дополняют друг друга:
проверено, что висячий `outboundTag` ядро пропускает, а `leastPing` без
observatory — валит.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from typing import Any

from .errors import public_error

BIN_DIR = os.environ.get("XED_BIN_DIR", "/app/geoip")     # тот же том, что у geo
BIN_PATH = os.path.join(BIN_DIR, "xray")
ASSET_DIR = os.environ.get("XED_GEO_DIR", "/app/geoip")
TIMEOUT = 20

# Ядро ПРИКОЛОЧЕНО к версии и к sha256 архива: бинарь исполняется внутри
# контейнера админки, «latest» без проверки — это доверие любому, кто сумеет
# подменить релиз или ответ по пути. Обновление версии — осознанная правка
# этих двух констант (sha — из Xray-linux-64.zip.dgst релиза).
XRAY_VERSION = os.environ.get("XED_XRAY_VERSION", "v26.3.27")
XRAY_SHA256 = {
    "v26.3.27": "23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae",
}
RELEASE_URL = f"https://github.com/XTLS/Xray-core/releases/download/{XRAY_VERSION}/Xray-linux-64.zip"
MAX_ZIP_BYTES = 64 * 1024 * 1024

# Подпроцессы ядра и скачивание — узкое место: пара одновременных проверок
# достаточно, остальные ждут, а не плодят процессы по 20 с каждый.
_check_sem = asyncio.Semaphore(2)
_download_lock = asyncio.Lock()

# Перевод сообщений ядра на человеческий: сырой текст сам по себе мало что говорит.
HINTS: list[tuple[str, str]] = [
    (r"not all dependencies are resolved",
     "Похоже, балансер со стратегией leastPing/leastLoad, а секции observatory "
     "(или burstObservatory) нет — ядро не может собрать зависимости."),
    (r"geoip\.dat|geosite\.dat",
     "Ядро не нашло geo-базы. Скачай их кнопкой ниже — проверка запускается с ними."),
    (r"Listening on non-443 ports",
     "Предупреждение ядра: Reality не на 443 порту заметнее для DPI. Это не ошибка."),
    (r"failed to parse certificate|no such file or directory",
     "Ядро не нашло файл, который есть только на ноде. Пути к сертификатам подменяются "
     "временным самоподписанным; остальные файлы (например, логи) ядро на проверке не открывает."),
    (r"empty clients|no user",
     "У inbound нет ни одного клиента. Панель подставляет их сама при выдаче "
     "конфига на ноду, так что для боевого профиля это норма."),
    (r"vless.*(tls|security)|without TLS is prohibited",
     "VLESS без TLS/Reality ядро запрещает на публичном адресе — задай security."),
    (r"reality.*(key|shortid|servername|dest|target|invalid|failed)",
     "Проблема в секции Reality: проверь privateKey/publicKey, shortIds и serverNames."),
    (r"invalid|unmarshal|unknown field|cannot unmarshal",
     "Ядро не поняло структуру конфига — скорее всего лишнее или неверно названное поле."),
    (r"port|address already in use",
     "Конфликт портов: два inbound слушают один и тот же порт."),
    (r"unknown outbound tag|no such outbound",
     "Правило ссылается на outbound, которого нет в конфиге."),
]


def status() -> dict:
    if not os.path.exists(BIN_PATH):
        return {"available": False}
    ver = ""
    try:
        res = subprocess.run([BIN_PATH, "version"], capture_output=True, text=True, timeout=10)
        ver = (res.stdout or "").splitlines()[0] if res.stdout else ""
    except Exception:  # noqa: BLE001
        pass
    return {"available": True, "version": ver, "size": os.path.getsize(BIN_PATH)}


async def _expected_sha256(client, version: str) -> str | None:
    """sha256 архива: из таблицы для приколоченной версии, иначе из .dgst релиза.

    .dgst лежит рядом с архивом, поэтому от подмены всего релиза не защищает —
    защищает от битой/подменённой по пути загрузки и от «latest» без контроля.
    Для версии из таблицы источник правды — константа в коде.
    """
    pinned = XRAY_SHA256.get(version)
    if pinned:
        return pinned
    resp = await client.get(RELEASE_URL + ".dgst")
    resp.raise_for_status()
    m = re.search(r"SHA2-256=\s*([0-9a-fA-F]{64})", resp.text)
    return m.group(1).lower() if m else None


async def download(ctx) -> dict:
    """Качает приколоченный релиз XTLS/Xray-core, сверяет sha256, распаковывает бинарь."""
    import httpx

    if _download_lock.locked():
        return {"ok": False, "error": "загрузка уже идёт", "status": status()}
    async with _download_lock:
        os.makedirs(BIN_DIR, exist_ok=True)
        tmp_zip = BIN_PATH + ".zip.part"
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                expected = await _expected_sha256(client, XRAY_VERSION)
                if not expected:
                    raise RuntimeError("no sha256 for release " + XRAY_VERSION)
                digest = hashlib.sha256()
                total = 0
                async with client.stream("GET", RELEASE_URL) as resp:
                    resp.raise_for_status()
                    with open(tmp_zip, "wb") as fh:
                        async for chunk in resp.aiter_bytes(65536):
                            total += len(chunk)
                            if total > MAX_ZIP_BYTES:
                                raise RuntimeError("release archive is too large")
                            digest.update(chunk)
                            fh.write(chunk)
            if digest.hexdigest() != expected:
                raise RuntimeError("sha256 mismatch: archive rejected")
            with zipfile.ZipFile(tmp_zip) as zf:
                with zf.open("xray") as src, open(BIN_PATH + ".part", "wb") as dst:
                    dst.write(src.read())
            os.chmod(BIN_PATH + ".part", 0o755)  # nosec B103 — исполняемый файл, иначе не запустить
            os.replace(BIN_PATH + ".part", BIN_PATH)
            return {"ok": True, "status": status()}
        except Exception as exc:  # noqa: BLE001 — без ядра редактор живёт, просто без проверки
            ctx.logger.warning("xray_editor: xray download failed: %s", exc)
            return {"ok": False, "error": public_error(exc), "status": status()}
        finally:
            for leftover in (tmp_zip, BIN_PATH + ".part"):
                if os.path.exists(leftover):
                    os.remove(leftover)


_FILE_KEYS = ("certificateFile", "keyFile")
_placeholder: dict | None = None


def _placeholder_cert() -> dict | None:
    """Временный самоподписанный сертификат от самого ядра (``xray tls cert``).

    Файлы сертификатов живут на ноде, в контейнере админки их нет — без подмены
    ядро валит проверку на «no such file», и всё остальное остаётся непроверенным.
    """
    global _placeholder
    if _placeholder is not None:
        return _placeholder
    try:
        res = subprocess.run([BIN_PATH, "tls", "cert"], capture_output=True, text=True, timeout=10,
                             env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tempfile.gettempdir()})
        data = json.loads(res.stdout)
        if data.get("certificate") and data.get("key"):
            _placeholder = {"certificate": data["certificate"], "key": data["key"]}
    except Exception:  # noqa: BLE001 — без подмены просто покажем ошибку ядра как есть
        _placeholder = None
    return _placeholder


def neutralize_node_files(config: Any) -> tuple[Any, list[str]]:
    """Копия конфига, где ссылки на файлы сертификатов заменены inline-заглушкой.

    Возвращает (конфиг, список подменённых путей). Структура не меняется —
    только элементы ``certificates`` с ``certificateFile``/``keyFile``.
    """
    replaced: list[str] = []
    cert = None

    def walk(node: Any) -> Any:
        nonlocal cert
        if isinstance(node, list):
            return [walk(x) for x in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for key, val in node.items():
            if key == "certificates" and isinstance(val, list):
                items = []
                for item in val:
                    if isinstance(item, dict) and any(k in item for k in _FILE_KEYS):
                        if cert is None:
                            cert = _placeholder_cert()
                        if cert:
                            replaced.extend(str(item[k]) for k in _FILE_KEYS if item.get(k))
                            clean = {k: v for k, v in item.items() if k not in _FILE_KEYS}
                            clean["certificate"] = cert["certificate"]
                            clean["key"] = cert["key"]
                            item = clean
                    items.append(item)
                out[key] = items
            else:
                out[key] = walk(val)
        return out

    return walk(config), replaced


def _hint_for(text: str) -> str | None:
    for pattern, hint in HINTS:
        if re.search(pattern, text, re.I):
            return hint
    return None


async def check(ctx, config: Any) -> dict:
    """Возвращает {available, ok, version, errors[], warnings[], raw}; не более двух ядер разом."""
    if not os.path.exists(BIN_PATH):
        return {"available": False}
    async with _check_sem:
        return await asyncio.to_thread(_check_sync, config)


def _check_sync(config: Any) -> dict:
    if not os.path.exists(BIN_PATH):
        return {"available": False}

    path = None
    config, replaced = neutralize_node_files(config)
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False)
            path = fh.name
        # Окружение — минимальное: бинарю не нужны пароли БД и токен панели.
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": tempfile.gettempdir(),
            "XRAY_LOCATION_ASSET": ASSET_DIR,
        }
        proc = subprocess.run(
            [BIN_PATH, "run", "-test", "-c", path],
            capture_output=True, text=True, timeout=TIMEOUT, env=env,
        )
        # ядро пишет и в stdout, и в stderr — вердикт может оказаться в любом
        raw = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return {"available": True, "ok": False, "errors": [
            {"text": f"проверка не уложилась в {TIMEOUT} с", "hint": None}], "warnings": [], "raw": ""}
    except Exception as exc:  # noqa: BLE001
        return {"available": True, "ok": False, "errors": [
            {"text": public_error(exc), "hint": None}], "warnings": [], "raw": ""}
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    version = next((ln for ln in lines if ln.startswith("Xray ")), "")
    ok = proc.returncode == 0 and bool(re.search(r"Configuration OK", raw, re.I))
    warnings = [{"text": ln, "hint": _hint_for(ln)} for ln in lines if "[Warning]" in ln]
    if replaced:
        warnings.append({
            "text": "сертификаты с ноды не проверялись: " + ", ".join(sorted(set(replaced))),
            "hint": "Файлы есть только на ноде — на проверку подставлен временный самоподписанный "
                    "сертификат. Что файлы на месте и валидны, проверит только сама нода.",
        })
    errors = []
    if not ok:
        for line in lines:
            if line.startswith("Xray ") or "A unified platform" in line or "Configuration OK" in line:
                continue
            errors.append({"text": line, "hint": _hint_for(line)})
        if not errors:
            errors = [{"text": "ядро не приняло конфиг, но без пояснения", "hint": None}]
    need_geo = (not ok) and bool(re.search(r"geoip\.dat|geosite\.dat", raw))
    return {"available": True, "ok": ok, "version": version, "needGeo": need_geo,
            "errors": errors, "warnings": warnings, "raw": raw}
