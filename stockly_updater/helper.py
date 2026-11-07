"""Ayudante de actualización (`update.exe`): aplica una actualización y reinicia Stockly.

Lo lanza Stockly:
    update --apply --tag v1.8.6 --app-dir <carpeta de la app> --wait-pid <pid> --restart

Se actualiza a sí mismo: antes de hacer nada se copia a una carpeta temporal y se
relanza desde ahí, así el `update.exe` instalado deja de estar en uso y se
reemplaza junto con el resto de la aplicación.
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from stockly_updater import constants as C
from stockly_updater.github import (
    ReleaseClient, UpdateCheckError, download, find_asset, find_asset_by_name,
    is_newer, platform_suffix,
)
from stockly_updater.installer import (
    InstallError, find_app_root, finalize, mark_executables, read_installed_version,
    safe_extract, swap_install, wait_for_pid,
)
from stockly_updater.manifest import ManifestError, verify_asset, verify_manifest
from stockly_updater.release_keys import RELEASE_PUBLIC_KEYS

log = logging.getLogger("stockly.update")
RELOCATED_FLAG = "--relocated"
ProgressFn = Callable[[int, str], None]


def helper_executable(app_dir: str | Path) -> Path:
    return Path(app_dir) / (C.HELPER_NAME + (".exe" if os.name == "nt" else ""))


def app_executable(app_dir: str | Path, exe_name: str = C.EXE_NAME) -> Path:
    return Path(app_dir) / (exe_name + (".exe" if os.name == "nt" else ""))


def launch_detached(args: list[str], cwd: str | Path | None = None) -> None:
    kwargs: dict = {"cwd": str(cwd) if cwd else None, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)


# ---- lógica de la actualización (sin interfaz, testeable) ------------------------
def apply_update(
    app_dir: str | Path,
    tag: str,
    *,
    wait_pid: int | None = None,
    restart: bool = False,
    progress: ProgressFn = lambda pct, msg: None,
    client: ReleaseClient | None = None,
    downloader: Callable = download,
    public_keys=None,
    exe_name: str = C.EXE_NAME,
    sleep: Callable[[float], None] = time.sleep,
    launcher: Callable[[list[str], str | Path | None], None] = launch_detached,
    wait_timeout: float = 90.0,
) -> str:
    """Descarga, verifica e instala `tag` en `app_dir`. Devuelve el tag instalado."""
    app_dir = Path(app_dir).resolve()
    keys = RELEASE_PUBLIC_KEYS if public_keys is None else public_keys
    work: Path | None = None
    staging: Path | None = None
    installed = False
    try:
        current = read_installed_version(app_dir)
        if current and not is_newer(tag, current):
            raise InstallError(f"La versión instalada ({current}) ya es igual o más nueva que {tag}.")

        progress(0, "Esperando que Stockly se cierre…")
        if wait_pid and not wait_for_pid(wait_pid, timeout=wait_timeout, sleep=sleep):
            raise InstallError("Stockly no se cerró a tiempo. Cerralo e intentá de nuevo.")

        progress(3, "Consultando la versión…")
        release = (client or ReleaseClient()).release_by_tag(tag)
        assets = release.get("assets") or []
        suffix = platform_suffix()
        package = find_asset(assets, suffix)
        manifest_asset = find_asset_by_name(assets, C.MANIFEST_ASSET)
        sig_asset = find_asset_by_name(assets, C.MANIFEST_SIG_ASSET)
        if package is None:
            raise InstallError(f"El release {tag} no incluye el paquete para este sistema ({suffix}).")
        if manifest_asset is None or sig_asset is None:
            raise InstallError(f"El release {tag} no está firmado: no se instala.")

        work = Path(tempfile.mkdtemp(prefix="stockly-update-"))
        progress(6, "Verificando la firma del release…")
        downloader(manifest_asset["browser_download_url"], work / C.MANIFEST_ASSET)
        downloader(sig_asset["browser_download_url"], work / C.MANIFEST_SIG_ASSET)
        manifest = verify_manifest(
            (work / C.MANIFEST_ASSET).read_bytes(),
            (work / C.MANIFEST_SIG_ASSET).read_text(encoding="utf-8"),
            keys,
        )
        if manifest["tag"] != tag:
            raise ManifestError("El manifiesto firmado corresponde a otra versión.")

        archive = work / package["name"]

        def on_progress(done: int, total: int) -> None:
            pct = 10 + int(70 * done / total) if total else 10
            progress(min(pct, 80), f"Descargando… {done // (1024 * 1024)} MB")

        downloader(package["browser_download_url"], archive, on_progress)
        progress(82, "Verificando integridad…")
        verify_asset(archive, manifest, package["name"])

        progress(86, "Extrayendo…")
        try:
            staging = Path(tempfile.mkdtemp(dir=app_dir.parent, prefix=".stockly-staging-"))
        except OSError:
            staging = Path(tempfile.mkdtemp(prefix="stockly-staging-"))
        safe_extract(archive, staging)
        new_root = find_app_root(staging, exe_name)

        progress(92, "Instalando…")
        swap_install(app_dir, new_root, sleep=sleep)
        installed = True
        mark_executables(app_dir, exe_name, C.HELPER_NAME)
        progress(98, "Finalizando…")
    except Exception:
        if restart and not installed:                       # que el usuario no se quede sin Stockly
            _try_launch(launcher, app_dir, exe_name)
        raise
    finally:
        for folder in (work, staging):
            if folder is not None:
                shutil.rmtree(folder, ignore_errors=True)

    if restart:
        _try_launch(launcher, app_dir, exe_name)
    progress(100, "Listo")
    return tag


def _try_launch(launcher, app_dir: Path, exe_name: str) -> None:
    exe = app_executable(app_dir, exe_name)
    try:
        if exe.is_file():
            launcher([str(exe)], app_dir)
    except OSError:
        log.exception("No se pudo reiniciar Stockly")


# ---- autoactualización: relanzarse desde una copia temporal -------------------------
def relocate_self(argv: list[str]) -> bool:
    """True si se relanzó desde una copia temporal (el proceso actual debe terminar)."""
    if not getattr(sys, "frozen", False) or RELOCATED_FLAG in argv:
        return False
    tmp = tempfile.mkdtemp(prefix="stockly-updater-")
    copy = os.path.join(tmp, os.path.basename(sys.executable))
    shutil.copy2(sys.executable, copy)
    args = [copy, *argv, RELOCATED_FLAG]
    if "--app-dir" not in argv:
        args += ["--app-dir", os.path.dirname(sys.executable)]
    launch_detached(args, cwd=tmp)
    return True


def cleanup_old_copies() -> None:
    for folder in glob.glob(os.path.join(tempfile.gettempdir(), "stockly-updater-*")):
        shutil.rmtree(folder, ignore_errors=True)  # la que está en uso falla en silencio


# ---- interfaz ----------------------------------------------------------------------
def _run_with_window(work: Callable[[ProgressFn], str]) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        return _run_console(work)

    events: queue.Queue = queue.Queue()
    root = tk.Tk()
    root.title("Actualizando Stockly")
    root.geometry("420x130")
    root.resizable(False, False)
    label = tk.Label(root, text="Preparando…", anchor="w")
    label.pack(fill="x", padx=16, pady=(18, 6))
    bar = ttk.Progressbar(root, maximum=100, length=388)
    bar.pack(padx=16)
    result = {"code": 1}

    def worker() -> None:
        try:
            work(lambda pct, msg: events.put(("progress", pct, msg)))
            events.put(("done", 100, "Stockly se actualizó correctamente."))
        except Exception as exc:  # noqa: BLE001 - se informa al usuario
            log.exception("Falló la actualización")
            events.put(("error", 0, str(exc) or exc.__class__.__name__))

    def poll() -> None:
        try:
            while True:
                kind, pct, msg = events.get_nowait()
                if kind == "progress":
                    bar["value"] = pct
                    label["text"] = msg
                elif kind == "done":
                    bar["value"] = 100
                    label["text"] = msg
                    result["code"] = 0
                    root.after(1200, root.destroy)
                    return
                else:
                    messagebox.showerror(
                        "No se pudo actualizar",
                        f"{msg}\n\nTu instalación anterior se conservó.",
                    )
                    root.destroy()
                    return
        except queue.Empty:
            pass
        root.after(100, poll)

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, poll)
    root.mainloop()
    return result["code"]


def _run_console(work: Callable[[ProgressFn], str]) -> int:
    try:
        work(lambda pct, msg: print(f"[{pct:3d}%] {msg}", flush=True))
    except Exception as exc:  # noqa: BLE001
        log.exception("Falló la actualización")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def _selftest() -> int:
    """Verifica que el ejecutable empaquetado puede firmar y verificar (PyNaCl)."""
    from nacl.signing import SigningKey

    from stockly_updater.manifest import b64e, build_manifest, sign_manifest

    key = SigningKey.generate()
    manifest = {"v": 1, "tag": "v0.0.0", "assets": {}}
    data, sig = sign_manifest(bytes(key), manifest)
    assert verify_manifest(data, sig, [b64e(bytes(key.verify_key))]) == manifest
    assert build_manifest("v0.0.0", []) == manifest
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="update", description="Ayudante de actualización de Stockly")
    p.add_argument("--apply", action="store_true", help="Aplica una actualización (lo usa Stockly)")
    p.add_argument("--tag", help="Versión a instalar, p. ej. v1.8.6")
    p.add_argument("--app-dir", help="Carpeta de la aplicación a actualizar")
    p.add_argument("--wait-pid", type=int, help="PID de Stockly: se espera a que termine")
    p.add_argument("--restart", action="store_true", help="Reabre Stockly al terminar")
    p.add_argument("--selftest", action="store_true", help="Autochequeo del ejecutable (CI)")
    p.add_argument(RELOCATED_FLAG, action="store_true", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    logging.basicConfig(
        filename=os.path.join(tempfile.gettempdir(), "stockly-update.log"),
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.selftest:
        return _selftest()
    if not args.apply:
        message = ("Esta herramienta la usa Stockly para actualizarse.\n\n"
                   "Abrí Stockly → Ajustes → Licencia y actualizaciones.")
        try:
            import tkinter as tk
            from tkinter import messagebox
            tk.Tk().withdraw()
            messagebox.showinfo("Actualizador de Stockly", message)
        except Exception:  # noqa: BLE001 - sin interfaz gráfica
            print(message)
        return 0
    if not args.tag or not args.app_dir:
        print("Faltan --tag y --app-dir.", file=sys.stderr)
        return 2
    if relocate_self(argv):
        return 0
    cleanup_old_copies()
    log.info("Actualizando %s a %s", args.app_dir, args.tag)
    return _run_with_window(lambda progress: apply_update(
        args.app_dir, args.tag, wait_pid=args.wait_pid, restart=args.restart, progress=progress,
    ))


if __name__ == "__main__":
    sys.exit(main())
