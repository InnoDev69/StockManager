# stockly/changelog_notice.py
import json
import os
import ssl
import sys
import urllib.request

import certifi

from config import ConfigManager  # ajustar el import a tu path real

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

REPO_OWNER = "InnoDev69"
REPO_REPO = "StockManager"
VERSION_FILE = "version.json"

# Se registra al importar el módulo, siguiendo el mismo patrón que backup/telemetría.
ConfigManager.register_defaults("update", {"last_seen_version": None})


def _base_dir() -> str:
    # stockly.exe vive en base_dir/stockly/stockly.exe -> dos niveles arriba
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ajustar en dev


def _read_current_version() -> str | None:
    path = os.path.join(_base_dir(), VERSION_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version")
        return version if isinstance(version, str) and version.strip() else None
    except (json.JSONDecodeError, OSError):
        return None


def check_and_fetch_changelog(config: ConfigManager) -> str | None:
    """
    Lee la versión actual desde version.json (la mantiene el updater) y la
    compara contra la última vista (config: update.last_seen_version). Si
    cambió, trae el changelog de esa versión desde GitHub. Devuelve None
    si no hay nada nuevo o si version.json todavía no existe.
    """
    current_version = _read_current_version()
    if current_version is None:
        return None

    last_seen = config.get("update.last_seen_version")
    if last_seen == current_version:
        return None

    changelog = None
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_REPO}/releases/tags/{current_version}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Stockly-App"},
        )
        with urllib.request.urlopen(req, timeout=8, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode())
        changelog = data.get("body") or "(Sin notas de la versión)"
    except Exception:
        # Sin internet, rate-limit, o el tag no existe en GitHub (ej: dev
        # local sin releases). No rompemos el arranque por esto.
        changelog = None

    # config.set() ya escribe en disco al toque (atómico), no hace falta
    # un save() aparte. Se marca como visto haya o no internet, para no
    # reintentar el fetch en cada arranque hasta el próximo cambio real.
    config.set("update.last_seen_version", current_version)

    return changelog