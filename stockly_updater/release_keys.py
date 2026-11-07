"""Claves públicas con las que se verifican los releases.

Generá un par DISTINTO al de las licencias:
    stockly-license keygen --out-dir ~/.stockly-release-keys
Pegá acá la clave pública (es seguro versionarla) y guardá la privada como
secreto `RELEASE_SIGNING_KEY` del repositorio de GitHub. Para rotar, dejá la
vieja y la nueva en la lista hasta que todos los clientes actualicen.

Mientras la lista esté vacía, el ayudante se niega a instalar cualquier
actualización (falla cerrado).
"""
from __future__ import annotations

RELEASE_PUBLIC_KEYS: list[str] = [
    # "AbC...base64url de 43 caracteres...",
]
