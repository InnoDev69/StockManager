#!/usr/bin/env python3
"""Firma los assets de un release (lo usa el CI).

    RELEASE_SIGNING_KEY=<clave privada base64url> python -m stockly_updater.sign_release \
        --tag v1.8.6 --out-dir release-meta Stockly-windows-x64.zip

Genera `manifest.json` (hash y tamaño de cada asset) y `manifest.json.sig`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from nacl.signing import SigningKey

from . import constants as C
from .manifest import b64d, b64e, build_manifest, sign_manifest, verify_manifest


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out-dir", default="release-meta")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    secret = (env.get("RELEASE_SIGNING_KEY") or "").strip()
    if not secret:
        print("Falta la variable RELEASE_SIGNING_KEY (clave privada de releases).", file=sys.stderr)
        return 1
    try:
        private = b64d(secret)
        public = bytes(SigningKey(private).verify_key)
    except Exception:  # noqa: BLE001 - no mostrar el secreto en el error
        print("RELEASE_SIGNING_KEY no es una clave válida.", file=sys.stderr)
        return 1
    missing = [f for f in args.files if not Path(f).is_file()]
    if missing:
        print(f"No existen los archivos: {', '.join(missing)}", file=sys.stderr)
        return 1

    manifest = build_manifest(args.tag, args.files)
    data, signature = sign_manifest(private, manifest)
    verify_manifest(data, signature, [public])          # autoverificación
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / C.MANIFEST_ASSET).write_bytes(data)
    (out / C.MANIFEST_SIG_ASSET).write_text(signature + "\n", encoding="utf-8")
    print(f"Manifiesto firmado para {args.tag}: {len(manifest['assets'])} asset(s). Clave pública: {b64e(public)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
