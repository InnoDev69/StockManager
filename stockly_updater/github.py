"""Consulta de releases de GitHub (con cache ETag) y descarga de assets.

Solo biblioteca estándar (usa certifi si está instalado).
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import constants as C

_STABLE_RE = re.compile(C.STABLE_TAG_RE)
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5
USER_AGENT = "Stockly-Updater"


class UpdateCheckError(Exception):
    """No se pudo consultar o descargar desde GitHub."""


class RateLimitExceeded(UpdateCheckError):
    def __init__(self, reset_at: datetime | None = None):
        msg = "Se agotó el límite de consultas a GitHub."
        if reset_at is not None:
            msg += f" Se restablece a las {reset_at.astimezone().strftime('%H:%M')}."
        super().__init__(msg)
        self.reset_at = reset_at


# ---- versiones ------------------------------------------------------------
def is_stable_tag(tag: object) -> bool:
    return isinstance(tag, str) and bool(_STABLE_RE.match(tag))


def parse_version(tag: str) -> tuple[int, int, int]:
    """'v1.8.6' / '1.8.6-dev' -> (1, 8, 6). Lo que no se entiende cuenta como 0."""
    text = str(tag).strip().lstrip("vV").split("+")[0].split("-")[0]
    parts = [int(p) for p in text.split(".") if p.isdigit()][:3]
    return tuple(parts + [0] * (3 - len(parts)))  # type: ignore[return-value]


def is_newer(new_tag: str, current_tag: str) -> bool:
    return parse_version(new_tag) > parse_version(current_tag)


# ---- plataforma y assets ----------------------------------------------------
def platform_suffix() -> str:
    if sys.platform == "win32":
        return "windows-x64.zip"
    if sys.platform.startswith("linux"):
        return "arch-x64.tar.gz" if os.path.exists("/etc/arch-release") else "ubuntu-x64.tar.gz"
    raise RuntimeError(f"Plataforma no soportada: {sys.platform}")


def find_asset(assets: list, suffix: str) -> dict | None:
    for asset in assets or []:
        if str(asset.get("name", "")).lower().endswith(suffix.lower()):
            return asset
    return None


def find_asset_by_name(assets: list, name: str) -> dict | None:
    for asset in assets or []:
        if asset.get("name") == name:
            return asset
    return None


# ---- red -----------------------------------------------------------------------
def _default_opener() -> Callable[[urllib.request.Request, float], Any]:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # sin certifi o sin su archivo: usar los certificados del sistema
        ctx = ssl.create_default_context()
    return lambda req, timeout: urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class ReleaseClient:
    """Lista de releases con cache condicional (ETag) para no gastar el rate limit."""

    def __init__(
        self,
        owner: str = C.OWNER,
        repo: str = C.REPO,
        *,
        cache_path: str | Path | None = None,
        token: str | None = None,
        interval_hours: float | None = None,
        opener: Callable[[urllib.request.Request, float], Any] | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.owner, self.repo = owner, repo
        self._cache_path = Path(cache_path) if cache_path else None
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        hours = C.check_interval_hours() if interval_hours is None else interval_hours
        self._interval = hours * 3600
        self._opener = opener or _default_opener()
        self._clock, self._sleep = clock, sleep

    # -- cache --
    def _load_cache(self) -> dict:
        if self._cache_path is None:
            return {}
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_cache(self, cache: dict) -> None:
        if self._cache_path is None:
            return
        try:
            _write_atomic(self._cache_path, json.dumps(cache))
        except OSError:
            pass

    # -- http --
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get(self, url: str, headers: dict[str, str]):
        last: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self._opener(urllib.request.Request(url, headers=headers), 10)
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise
                last = exc
            except (urllib.error.URLError, OSError) as exc:
                last = exc
            if attempt < MAX_RETRIES:
                self._sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise UpdateCheckError(f"No se pudo conectar a GitHub: {last}")

    @staticmethod
    def _pick(releases: list) -> dict | None:
        stable = [
            r for r in releases
            if isinstance(r, dict) and is_stable_tag(r.get("tag_name"))
            and not r.get("draft") and not r.get("prerelease")
        ]
        return max(stable, key=lambda r: parse_version(r["tag_name"]), default=None)

    def _fetch(self, cache: dict) -> list:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases?per_page=30"
        headers = self._headers()
        if cache.get("etag"):
            headers["If-None-Match"] = cache["etag"]
        new_etag = None
        try:
            with self._get(url, headers) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
                new_etag = resp.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            limited = exc.code in (403, 429) and (exc.headers or {}).get("X-RateLimit-Remaining") == "0"
            if (exc.code == 304 or limited) and "releases" in cache:
                releases = cache["releases"]            # sin cambios o sin cupo: usar lo cacheado
            elif limited:
                reset = (exc.headers or {}).get("X-RateLimit-Reset")
                raise RateLimitExceeded(
                    datetime.fromtimestamp(int(reset), tz=timezone.utc) if reset else None
                ) from exc
            else:
                raise UpdateCheckError(f"GitHub respondió con el error {exc.code}.") from exc
        except UpdateCheckError:
            if "releases" not in cache:
                raise
            releases = cache["releases"]                # sin internet: seguir con lo cacheado
        except (ValueError, UnicodeDecodeError) as exc:
            raise UpdateCheckError("Respuesta inválida de GitHub.") from exc

        if not isinstance(releases, list):
            raise UpdateCheckError("Respuesta inválida de GitHub.")
        cache = dict(cache)
        cache["releases"] = releases
        if new_etag:
            cache["etag"] = new_etag
        cache["checked_at"] = self._clock()
        self._save_cache(cache)
        return releases

    # -- api pública --
    def cached_latest(self) -> dict | None:
        """Último release estable según el cache (sin tocar la red)."""
        return self._pick(self._load_cache().get("releases", []))

    def latest_stable(self, force: bool = False) -> dict | None:
        cache = self._load_cache()
        fresh = "releases" in cache and (self._clock() - cache.get("checked_at", 0)) < self._interval
        if fresh and not force:
            return self._pick(cache["releases"])
        return self._pick(self._fetch(cache))

    def release_by_tag(self, tag: str) -> dict:
        if not is_stable_tag(tag):
            raise UpdateCheckError(f"Tag de versión inválido: {tag!r}")
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        try:
            with self._get(url, self._headers()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise UpdateCheckError(f"No se pudo obtener el release {tag} (error {exc.code}).") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise UpdateCheckError("Respuesta inválida de GitHub.") from exc
        if not isinstance(data, dict):
            raise UpdateCheckError("Respuesta inválida de GitHub.")
        return data


def download(
    url: str,
    dest: str | Path,
    progress_cb: Callable[[int, int], None] | None = None,
    *,
    opener: Callable[[urllib.request.Request, float], Any] | None = None,
    timeout: float = 30,
    max_bytes: int = C.MAX_DOWNLOAD_BYTES,
) -> None:
    """Descarga a `dest` (vía archivo .part; no deja archivos a medias)."""
    opener = opener or _default_opener()
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    try:
        with opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout) as resp, \
                open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                done += len(chunk)
                if done > max_bytes:
                    raise UpdateCheckError("El archivo supera el tamaño máximo permitido.")
                out.write(chunk)
                if progress_cb:
                    progress_cb(done, total)
        os.replace(part, dest)
    except (urllib.error.URLError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise UpdateCheckError(f"Falló la descarga: {exc}") from exc
    except BaseException:
        part.unlink(missing_ok=True)
        raise
