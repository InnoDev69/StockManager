"""Persistencia: escritura atómica y registro del período de prueba."""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from stockly_license.models import format_dt, parse_dt


def write_atomic(path: Path, text: str) -> None:
    """Escribe en un temporal y reemplaza: nunca deja un archivo a medias."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


class TrialCorruptError(Exception):
    """El archivo de la prueba existe pero no se puede interpretar."""


@dataclass
class TrialRecord:
    started: datetime
    machine: str
    last_seen: datetime  # última hora vista: evita extender la prueba atrasando el reloj


def load_trial(path: Path) -> TrialRecord | None:
    """None si todavía no hay registro; TrialCorruptError si está dañado."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
        return TrialRecord(
            started=parse_dt(data["started"]),
            machine=str(data["machine"]),
            last_seen=parse_dt(data["last_seen"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TrialCorruptError(str(exc)) from exc


def save_trial(path: Path, record: TrialRecord) -> None:
    write_atomic(path, json.dumps({
        "started": format_dt(record.started),
        "machine": record.machine,
        "last_seen": format_dt(record.last_seen),
    }, indent=2) + "\n")
