"""Instalación segura: extracción validada, reemplazo con respaldo y rollback."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Callable


class InstallError(Exception):
    """No se pudo instalar la actualización (la instalación anterior se conserva)."""


# ---- extracción -------------------------------------------------------------
def _inside(base: Path, target: Path) -> bool:
    return target == base or base in target.parents


def safe_extract(archive: str | Path, dest: str | Path) -> None:
    """Extrae .zip o .tar.gz rechazando rutas fuera de `dest` y archivos especiales."""
    dest = Path(dest).resolve()
    archive = str(archive)
    if archive.lower().endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if not _inside(dest, (dest / info.filename).resolve()):
                    raise InstallError(f"El paquete contiene una ruta insegura: {info.filename}")
            zf.extractall(dest)
        return
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        for m in members:
            target = (dest / m.name).resolve()
            if not _inside(dest, target):
                raise InstallError(f"El paquete contiene una ruta insegura: {m.name}")
            if m.isdev() or m.isfifo():
                raise InstallError(f"El paquete contiene un archivo especial: {m.name}")
            if m.issym() and not _inside(dest, (target.parent / m.linkname).resolve()):
                raise InstallError(f"El paquete contiene un enlace inseguro: {m.name}")
            if m.islnk() and not _inside(dest, (dest / m.linkname).resolve()):
                raise InstallError(f"El paquete contiene un enlace inseguro: {m.name}")
        kwargs = {"filter": "fully_trusted"} if hasattr(tarfile, "fully_trusted_filter") else {}
        tf.extractall(dest, members=members, **kwargs)  # ya validado arriba


def _exe_names(exe_name: str) -> tuple[str, str]:
    return exe_name, exe_name + ".exe"


def find_app_root(extract_dir: str | Path, exe_name: str) -> Path:
    """Carpeta (dentro de lo extraído) que contiene el ejecutable de la app."""
    names = _exe_names(exe_name)
    base = Path(extract_dir)
    for dirpath, _dirs, files in os.walk(base):
        if any(n in files for n in names):
            return Path(dirpath)
    raise InstallError("El paquete descargado no contiene la aplicación.")


def read_installed_version(app_dir: str | Path) -> str | None:
    try:
        data = json.loads((Path(app_dir) / "version.json").read_text(encoding="utf-8"))
        version = data.get("version")
        return version if isinstance(version, str) else None
    except (OSError, ValueError, AttributeError):
        return None


# ---- procesos ---------------------------------------------------------------
def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: sigue vivo
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_pid(pid: int, timeout: float = 60.0, poll: float = 0.25,
                 sleep: Callable[[float], None] = time.sleep) -> bool:
    """Espera a que termine el proceso. True si terminó, False si venció el tiempo."""
    deadline = time.monotonic() + timeout
    while pid_alive(pid):
        if time.monotonic() >= deadline:
            return False
        sleep(poll)
    return True


# ---- reemplazo con respaldo ---------------------------------------------------
def backup_path(app_dir: str | Path) -> Path:
    app_dir = Path(app_dir)
    return app_dir.with_name(app_dir.name + ".old")


def swap_install(app_dir: str | Path, new_root: str | Path, *, retries: int = 8, delay: float = 0.5,
                 sleep: Callable[[float], None] = time.sleep) -> Path:
    """Reemplaza `app_dir` por `new_root` conservando la versión anterior en `<app_dir>.old`.

    Si algo falla, restaura la versión anterior y lanza InstallError. Los datos del
    usuario NO viven en `app_dir` (están en la carpeta de datos), así que no se tocan.
    """
    app_dir, new_root = Path(app_dir), Path(new_root)
    if not new_root.is_dir():
        raise InstallError("No se encontró la nueva versión extraída.")
    backup = backup_path(app_dir)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
        if backup.exists():
            raise InstallError(f"No se pudo limpiar el respaldo anterior ({backup}).")

    last: Exception | None = None
    for attempt in range(retries):
        try:
            os.replace(app_dir, backup)
            break
        except OSError as exc:  # archivos en uso (Stockly abierto, antivirus...)
            last = exc
            if attempt < retries - 1:
                sleep(delay)
    else:
        raise InstallError("No se pudo reemplazar la instalación. ¿Stockly sigue abierto?") from last

    try:
        shutil.move(str(new_root), str(app_dir))
    except Exception as exc:
        shutil.rmtree(app_dir, ignore_errors=True)
        os.replace(backup, app_dir)
        raise InstallError("Falló la instalación; se restauró la versión anterior.") from exc
    return backup


def rollback(app_dir: str | Path, backup: str | Path) -> None:
    shutil.rmtree(app_dir, ignore_errors=True)
    os.replace(backup, app_dir)


def finalize(backup: str | Path) -> None:
    shutil.rmtree(backup, ignore_errors=True)


def mark_executables(app_dir: str | Path, exe_name: str, helper_name: str) -> None:
    """En Linux, asegura permisos de ejecución de la app y del ayudante."""
    if os.name == "nt":
        return
    for name in (exe_name, helper_name):
        path = Path(app_dir) / name
        if path.is_file():
            path.chmod(0o755)
