#!/usr/bin/env python3
"""Genera las claves de licencias y de releases y las deja configuradas en el repo.

    python -m stockly_updater.bootstrap_keys          (desde la raíz del repo)

- Claves de licencias  -> ~/.stockly-license/keys   (las que usa `stockly-license issue`)
- Claves de releases   -> ~/.stockly-release-keys   (la privada va al secreto RELEASE_SIGNING_KEY)
- Pega las dos claves PÚBLICAS en core/licensing/public_keys.py y stockly_updater/release_keys.py.

Es seguro correrlo de nuevo: si ya existen claves se reutilizan (nunca se pisan) y no
se duplican en los archivos. No imprime ninguna clave privada.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from nacl.signing import SigningKey

from .manifest import b64d, b64e

TARGETS = {
    "licencias": ("core/licensing/public_keys.py", "PUBLIC_KEYS"),
    "releases": ("stockly_updater/release_keys.py", "RELEASE_PUBLIC_KEYS"),
}


def ensure_keypair(directory: Path) -> tuple[str, bool]:
    """Devuelve (clave pública base64url, creada_ahora). Reutiliza private.key si existe."""
    directory.mkdir(parents=True, exist_ok=True)
    private_path, public_path = directory / "private.key", directory / "public.key"
    created = False
    if private_path.exists():
        key = SigningKey(b64d(private_path.read_text(encoding="utf-8")))
    else:
        key = SigningKey.generate()
        fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(b64e(bytes(key)) + "\n")
        created = True
    public = b64e(bytes(key.verify_key))
    if not public_path.exists():
        public_path.write_text(public + "\n", encoding="utf-8")
    return public, created


def insert_public_key(file: Path, list_name: str, key: str) -> bool:
    """Agrega la clave a la lista del archivo. False si ya estaba."""
    text = file.read_text(encoding="utf-8")
    if f'"{key}"' in text:
        return False
    start = text.index(f"{list_name}: list[str] = [")
    end = text.index("\n]", start)
    file.write_text(text[:end] + f'\n    "{key}",' + text[end:], encoding="utf-8")
    return True


def key_id(public: str) -> str:
    return hashlib.sha256(b64d(public)).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="Raíz del repo de Stockly")
    parser.add_argument("--license-keys-dir", default=str(Path.home() / ".stockly-license" / "keys"))
    parser.add_argument("--release-keys-dir", default=str(Path.home() / ".stockly-release-keys"))
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    missing = [rel for rel, _ in TARGETS.values() if not (repo / rel).is_file()]
    if missing:
        print(f"No se encontraron {', '.join(missing)} en {repo.resolve()}. ¿Corriste esto desde la raíz del repo?",
              file=sys.stderr)
        return 1

    dirs = {"licencias": Path(args.license_keys_dir), "releases": Path(args.release_keys_dir)}
    for name, (rel, list_name) in TARGETS.items():
        public, created = ensure_keypair(dirs[name])
        added = insert_public_key(repo / rel, list_name, public)
        print(f"Claves de {name}: {'creadas' if created else 'ya existían, se reutilizan'} en {dirs[name]} "
              f"(kid {key_id(public)}); clave pública {'agregada a' if added else 'ya estaba en'} {rel}")
    print()
    print("Siguiente paso (secreto de GitHub para firmar releases), sin mostrar la clave en pantalla:")
    print(f'  gh secret set RELEASE_SIGNING_KEY < "{dirs["releases"] / "private.key"}"')
    print("  (o copiá el contenido de ese archivo en GitHub > Settings > Secrets and variables > Actions)")
    print(f"Guardá una copia de ambos private.key en tu gestor de contraseñas. NUNCA los subas a Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
