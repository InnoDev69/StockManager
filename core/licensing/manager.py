"""LicenseManager: estado de licencia de Stockly (offline)."""
from __future__ import annotations

import logging
import math
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from stockly_license import (
    LicenseError, LicenseVerifier, format_machine_id, get_machine_id, normalize_machine_id,
)
from stockly_license.models import utcnow

from .state import LicenseState, LicenseStatus, error_info
from .storage import TrialCorruptError, TrialRecord, load_trial, save_trial, write_atomic

log = logging.getLogger(__name__)

_LAST_SEEN_STEP = timedelta(hours=1)


def _truthy(value: Any) -> bool:
    return value not in (None, False, 0, "")


class LicenseManager:
    """Lee, valida y guarda la licencia; calcula el estado y las funciones habilitadas.

    Archivos (dentro de `<data_dir>/license/`):
      license.stk  licencia activada (texto)
      trial.json   inicio de la prueba

    Qué se bloquea según el estado lo decide Stockly: este objeto solo informa.
    """

    def __init__(
        self,
        data_dir: str | Path,
        verifier: LicenseVerifier,
        *,
        machine_id: str | None = None,
        trial_days: int = 30,
        trial_features: Mapping[str, Any] | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        base = Path(data_dir) / "license"
        self._token_path = base / "license.stk"
        self._trial_path = base / "trial.json"
        self._verifier = verifier
        self._machine_id = format_machine_id(machine_id) if machine_id else get_machine_id()
        self._trial_days = max(0, int(trial_days))
        self._trial_features = dict(trial_features or {})
        self._clock = clock
        self._lock = threading.RLock()

    @property
    def machine_id(self) -> str:
        return self._machine_id

    # ---- estado ----------------------------------------------------------
    def status(self) -> LicenseStatus:
        with self._lock:
            now = self._clock()
            try:
                token = self._read_token()
            except OSError:
                log.warning("No se pudo leer %s", self._token_path, exc_info=True)
                return LicenseStatus(
                    LicenseState.INVALID, self._machine_id,
                    "No se pudo leer el archivo de licencia.", error_code="unreadable",
                )
            if token is None:
                return self._trial_status(now)
            return self._token_status(token, now)

    def _read_token(self) -> str | None:
        try:
            text = self._token_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        text = "".join(text.split())
        return text or None

    def _token_status(self, token: str, now: datetime) -> LicenseStatus:
        try:
            lic = self._verifier.verify(token, machine_id=self._machine_id, now=now)
        except LicenseError as exc:
            code, message = error_info(exc, self._machine_id)
            return LicenseStatus(
                LicenseState.INVALID, self._machine_id, message,
                license=getattr(exc, "license", None), error_code=code,
            )
        return LicenseStatus(LicenseState.LICENSED, self._machine_id, "Licencia activa.", license=lic)

    def _trial_status(self, now: datetime) -> LicenseStatus:
        total = self._trial_days

        def expired(code: str, message: str) -> LicenseStatus:
            return LicenseStatus(
                LicenseState.TRIAL_EXPIRED, self._machine_id, message,
                error_code=code, trial_days_left=0, trial_days_total=total,
            )

        try:
            record = load_trial(self._trial_path)
        except (TrialCorruptError, OSError):
            log.warning("Registro de prueba ilegible: %s", self._trial_path, exc_info=True)
            return expired("trial_unreadable", "No se pudo verificar el período de prueba. Activá una licencia.")

        if record is None:
            record = TrialRecord(started=now, machine=self._machine_id, last_seen=now)
            self._save_trial(record)
        else:
            try:
                same_machine = normalize_machine_id(record.machine) == normalize_machine_id(self._machine_id)
            except ValueError:
                same_machine = False
            if not same_machine:
                return expired("trial_other_machine", "El período de prueba de este equipo ya terminó. Activá una licencia.")
            if now >= record.last_seen + _LAST_SEEN_STEP:
                record.last_seen = now
                self._save_trial(record)

        effective_now = max(now, record.last_seen)  # atrasar el reloj no extiende la prueba
        remaining = timedelta(days=total) - (effective_now - record.started)
        if remaining.total_seconds() <= 0:
            return expired("trial_expired", "El período de prueba terminó. Activá una licencia para seguir usando Stockly.")
        days_left = math.ceil(remaining.total_seconds() / 86400)
        return LicenseStatus(
            LicenseState.TRIAL, self._machine_id,
            f"Período de prueba: te quedan {days_left} día{'s' if days_left != 1 else ''}.",
            trial_days_left=days_left, trial_days_total=total,
        )

    def _save_trial(self, record: TrialRecord) -> None:
        try:
            save_trial(self._trial_path, record)
        except OSError:
            log.warning("No se pudo guardar %s", self._trial_path, exc_info=True)

    # ---- activación -------------------------------------------------------
    def activate(self, token_text: str) -> LicenseStatus:
        """Valida y guarda una licencia. Si no es válida lanza LicenseError y no guarda nada."""
        token = "".join(str(token_text).split())
        with self._lock:
            self._verifier.verify(token, machine_id=self._machine_id, now=self._clock())
            write_atomic(self._token_path, token + "\n")
            return self.status()

    def deactivate(self) -> LicenseStatus:
        """Quita la licencia de este equipo (por ejemplo, antes de pasarla a otra PC)."""
        with self._lock:
            self._token_path.unlink(missing_ok=True)
            return self.status()

    # ---- consultas para el resto de Stockly --------------------------------
    def has_feature(self, name: str) -> bool:
        st = self.status()
        if st.state is LicenseState.LICENSED:
            return st.license.has_feature(name)
        if st.state is LicenseState.TRIAL:
            return _truthy(self._trial_features.get(name))
        return False

    def feature(self, name: str, default: Any = None) -> Any:
        st = self.status()
        if st.state is LicenseState.LICENSED:
            return st.license.feature(name, default)
        if st.state is LicenseState.TRIAL:
            return self._trial_features.get(name, default)
        return default

    def updates_allowed(self, release_date: date | datetime) -> bool:
        """¿Puede instalar un release publicado en esa fecha?

        Con licencia: según `updates_until`. En prueba: sí. Prueba vencida o
        licencia inválida: no.
        """
        st = self.status()
        if st.state is LicenseState.LICENSED:
            return st.license.updates_allowed(release_date)
        return st.state is LicenseState.TRIAL
