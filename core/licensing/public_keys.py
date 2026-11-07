"""Claves públicas embebidas en Stockly.

Pegá acá la clave pública que imprime `stockly-license keygen`. Es seguro
versionarla (solo sirve para verificar). Durante una rotación de claves,
dejá la vieja y la nueva en la lista hasta reemitir todas las licencias.
"""
from __future__ import annotations

from stockly_license import LicenseVerifier

PUBLIC_KEYS: list[str] = [
    # "AbC...base64url de 43 caracteres...",
]


def build_verifier(keys: list[str] | None = None) -> LicenseVerifier:
    keys = PUBLIC_KEYS if keys is None else keys
    if not keys:
        raise RuntimeError(
            "Falta embeber la clave pública de licencias: pegala en licensing/public_keys.py "
            "(la imprime `stockly-license keygen`)."
        )
    return LicenseVerifier.from_public_keys(keys)
