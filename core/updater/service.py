"""Servicio de actualizaciones de Stockly: chequeo, licencia y lanzamiento del ayudante."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from stockly_updater import constants as C
from stockly_updater.github import RateLimitExceeded, ReleaseClient, UpdateCheckError, is_newer
from stockly_updater.installer import backup_path

MAX_NOTES_CHARS = 4000
MIN_FORCE_INTERVAL = 60.0   # segundos entre consultas forzadas


class UpdateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    allowed: bool = True            # la licencia permite instalar esta versión
    decision_code: str = "ok"
    message: str = ""
    published_at: str | None = None
    notes: str = ""
    checked_at: float | None = None
    can_apply: bool = False         # instalado (no desarrollo) y con ayudante presente
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _NullLog:
    def info(self, *a, **k): pass
    warning = error = info


class UpdateService:
    def __init__(
        self,
        data_dir: str | Path,
        *,
        license_manager=None,
        current_version: str | None = None,
        client: ReleaseClient | None = None,
        app_dir: str | Path | None = None,
        frozen: bool | None = None,
        launcher: Callable[..., Any] = subprocess.Popen,
        log=None,
        shutdown_delay: float = 1.5,
        force_exit_delay: float = 10.0,
        timer_factory: Callable[..., Any] = threading.Timer,
        exit_fn: Callable[[int], None] = os._exit,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if current_version is None:
            from core.version import __version__ as current_version
        self.current_version = current_version
        self._client = client or ReleaseClient(cache_path=Path(data_dir) / "updates" / "update_cache.json")
        self._license = license_manager
        self._frozen = getattr(sys, "frozen", False) if frozen is None else frozen
        self._app_dir = Path(app_dir) if app_dir else Path(sys.executable).resolve().parent
        self._launcher = launcher
        self._log = log or _NullLog()
        self._shutdown_delay, self._force_exit_delay = shutdown_delay, force_exit_delay
        self._timer_factory, self._exit_fn, self._clock = timer_factory, exit_fn, clock
        self._shutdown_hook: Callable[[], None] | None = None
        self._last_force = 0.0
        self._lock = threading.Lock()

    # ---- ayudante y rutas -------------------------------------------------------
    @property
    def helper_path(self) -> Path:
        return self._app_dir / (C.HELPER_NAME + (".exe" if os.name == "nt" else ""))

    @property
    def can_apply(self) -> bool:
        return self._frozen and self.helper_path.is_file()

    def set_shutdown_hook(self, hook: Callable[[], None]) -> None:
        """Cómo cerrar Stockly de forma ordenada (cerrar la ventana, detener el servidor...)."""
        self._shutdown_hook = hook

    # ---- chequeo ---------------------------------------------------------------------
    def _decision(self, published_at: str | None) -> tuple[bool, str, str]:
        if self._license is None:
            return True, "licensing_disabled", ""
        from core.licensing.updates import check_update
        decision = check_update(self._license, published_at)
        return decision.allowed, decision.code, decision.message

    def check(self, force: bool = False, offline: bool = False) -> UpdateInfo:
        """Consulta GitHub (respetando el cache) y evalúa la licencia. `offline` usa solo el cache."""
        base = {"current_version": self.current_version, "can_apply": self.can_apply}
        try:
            with self._lock:
                if force and not offline:
                    now = self._clock()
                    force = (now - self._last_force) >= MIN_FORCE_INTERVAL
                    if force:
                        self._last_force = now
                release = self._client.cached_latest() if offline else self._client.latest_stable(force=force)
        except RateLimitExceeded as exc:
            return UpdateInfo(**base, error=str(exc))
        except UpdateCheckError as exc:
            self._log.warning(f"No se pudo consultar actualizaciones: {exc}")
            return UpdateInfo(**base, error=f"No se pudo consultar actualizaciones: {exc}")
        if release is None:
            return UpdateInfo(**base, message="Todavía no se consultaron actualizaciones." if offline else
                              "No hay versiones publicadas.")

        tag = release["tag_name"]
        checked_at = self._clock()
        if not is_newer(tag, self.current_version):
            return UpdateInfo(**base, latest_version=tag, message="Stockly está actualizado.", checked_at=checked_at)

        allowed, code, message = self._decision(release.get("published_at"))
        return UpdateInfo(
            **base, latest_version=tag, update_available=True, allowed=allowed, decision_code=code,
            message=message or f"Hay una versión nueva: {tag}.",
            published_at=release.get("published_at"),
            notes=(release.get("body") or "")[:MAX_NOTES_CHARS], checked_at=checked_at,
        )

    def status(self) -> UpdateInfo:
        return self.check(offline=True)

    # ---- aplicar ------------------------------------------------------------------------
    def apply(self) -> str:
        """Lanza el ayudante y programa el cierre de Stockly. Devuelve el tag a instalar."""
        info = self.check()
        if info.error:
            raise UpdateError("check_failed", info.error)
        if not info.update_available:
            raise UpdateError("up_to_date", "Stockly ya está actualizado.")
        if not info.allowed:
            raise UpdateError(info.decision_code, info.message)
        if not self._frozen:
            raise UpdateError("not_installed", "Solo se puede actualizar la versión instalada, no el modo desarrollo.")
        if not self.helper_path.is_file():
            raise UpdateError("helper_missing", "Falta el programa actualizador (update) junto a Stockly.")

        args = [str(self.helper_path), "--apply", "--tag", info.latest_version,
                "--app-dir", str(self._app_dir), "--wait-pid", str(os.getpid()), "--restart"]
        kwargs: dict[str, Any] = {"close_fds": True, "cwd": str(self._app_dir)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            self._launcher(args, **kwargs)
        except OSError as exc:
            raise UpdateError("launch_failed", f"No se pudo iniciar el actualizador: {exc}") from exc
        self._log.info(f"Actualizando de {self.current_version} a {info.latest_version}")
        self._schedule_shutdown()
        return info.latest_version

    def _schedule_shutdown(self) -> None:
        def shutdown() -> None:
            hook = self._shutdown_hook
            if hook is not None:
                try:
                    hook()
                except Exception as exc:  # noqa: BLE001 - igual se fuerza la salida abajo
                    self._log.error(f"Falló el cierre ordenado: {exc}")
            force = self._timer_factory(self._force_exit_delay, lambda: self._exit_fn(0))
            force.daemon = True
            force.start()

        timer = self._timer_factory(self._shutdown_delay, shutdown)
        timer.daemon = True
        timer.start()

    # ---- mantenimiento -----------------------------------------------------------------------
    def cleanup_backup(self) -> bool:
        """Borra el respaldo de la versión anterior (`<app>.old`) y restos de instalaciones fallidas."""
        if not self._frozen:
            return False
        removed = False
        backup = backup_path(self._app_dir)
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
            removed = not backup.exists()
        for leftover in self._app_dir.parent.glob(".stockly-staging-*"):
            shutil.rmtree(leftover, ignore_errors=True)
        return removed

    def maintenance(self) -> None:
        """Tarea periódica: limpieza y chequeo (usa el cache, no gasta cupo de GitHub)."""
        try:
            self.cleanup_backup()
            self.check()
        except Exception as exc:  # noqa: BLE001 - nunca romper el scheduler
            self._log.warning(f"Mantenimiento de actualizaciones falló: {exc}")
