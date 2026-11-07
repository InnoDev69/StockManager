"""Manifiesto de release firmado (Ed25519): hash y tamaño de cada asset.

El CI firma `manifest.json` con la clave privada de releases (`sign_release.py`)
y el ayudante lo verifica con las claves públicas embebidas antes de instalar.
El prefijo de dominio impide reutilizar firmas de licencias como firmas de releases.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

FORMAT_VERSION = 1
_DOMAIN = b"stockly-release-v1\n"
_B64URL = re.compile(r"[A-Za-z0-9_-]*")


class ManifestError(Exception):
    """El manifiesto o el archivo descargado no son confiables."""


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64d(text: str) -> bytes:
    text = text.strip()
    if not _B64URL.fullmatch(text):
        raise ValueError("base64url inválido")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_manifest(tag: str, files: Iterable[str | Path]) -> dict:
    assets = {}
    for f in files:
        p = Path(f)
        assets[p.name] = {"sha256": file_sha256(p), "size": p.stat().st_size}
    return {"v": FORMAT_VERSION, "tag": tag, "assets": assets}


def sign_manifest(private_key: bytes, manifest: dict) -> tuple[bytes, str]:
    """Devuelve (bytes_del_manifiesto, firma_base64url)."""
    data = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return data, b64e(SigningKey(private_key).sign(_DOMAIN + data).signature)


def _verify_keys(public_keys: Iterable[bytes | str]) -> list[VerifyKey]:
    keys = []
    for k in public_keys:
        raw = b64d(k) if isinstance(k, str) else bytes(k)
        keys.append(VerifyKey(raw))
    return keys


def verify_manifest(data: bytes, signature: str, public_keys: Iterable[bytes | str]) -> dict:
    keys = _verify_keys(public_keys)
    if not keys:
        raise ManifestError(
            "Esta instalación no tiene claves de verificación de releases: no se puede actualizar de forma segura."
        )
    try:
        sig = b64d(signature)
    except ValueError as exc:
        raise ManifestError("La firma del release está corrupta.") from exc
    for key in keys:
        try:
            key.verify(_DOMAIN + data, sig)
            break
        except BadSignatureError:
            continue
    else:
        raise ManifestError("La firma del release no es válida.")
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ManifestError("El manifiesto del release está corrupto.") from exc
    if (not isinstance(manifest, dict) or manifest.get("v") != FORMAT_VERSION
            or not isinstance(manifest.get("tag"), str) or not isinstance(manifest.get("assets"), dict)):
        raise ManifestError("El manifiesto del release tiene un formato desconocido.")
    return manifest


def verify_asset(path: str | Path, manifest: dict, name: str) -> None:
    entry = manifest["assets"].get(name)
    if not isinstance(entry, dict):
        raise ManifestError(f"El archivo {name} no figura en el manifiesto firmado.")
    if Path(path).stat().st_size != entry.get("size"):
        raise ManifestError(f"El tamaño de {name} no coincide con el manifiesto.")
    if file_sha256(path) != entry.get("sha256"):
        raise ManifestError(f"El contenido de {name} no coincide con el manifiesto (archivo alterado o dañado).")
