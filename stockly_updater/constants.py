"""Constantes del actualizador."""
from __future__ import annotations

import os

OWNER = "InnoDev69"
REPO = "StockManager"
EXE_NAME = "stockly"        # ejecutable de la app (sin .exe)
HELPER_NAME = "update"      # ejecutable del ayudante (sin .exe)

# Solo se consideran estables los tags exactos vX.Y.Z
STABLE_TAG_RE = r"^v\d+\.\d+\.\d+$"

MANIFEST_ASSET = "manifest.json"
MANIFEST_SIG_ASSET = "manifest.json.sig"

MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024  # 1 GB


def check_interval_hours() -> float:
    try:
        return float(os.environ.get("STOCKLY_UPDATE_CHECK_INTERVAL_HOURS", "4"))
    except ValueError:
        return 4.0
