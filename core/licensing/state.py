"""Estados de licencia y mensajes para el usuario."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from stockly_license import (
    InvalidSignatureError, InvalidTokenError, License, LicenseExpiredError,
    MachineMismatchError, UnknownKeyError, UnsupportedVersionError,
)
from stockly_license.models import format_dt


class LicenseState(str, Enum):
    LICENSED = "LICENSED"            # licencia válida en este equipo
    TRIAL = "TRIAL"                  # sin licencia, dentro del período de prueba
    TRIAL_EXPIRED = "TRIAL_EXPIRED"  # sin licencia y prueba terminada
    INVALID = "INVALID"              # hay una licencia guardada pero no se puede usar


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


@dataclass(frozen=True)
class LicenseStatus:
    state: LicenseState
    machine_id: str
    message: str
    license: License | None = None
    error_code: str | None = None
    trial_days_left: int | None = None
    trial_days_total: int | None = None

    @property
    def is_active(self) -> bool:
        """True con licencia válida o prueba vigente. Qué se bloquea lo decide Stockly."""
        return self.state in (LicenseState.LICENSED, LicenseState.TRIAL)

    def to_dict(self) -> dict[str, Any]:
        lic = self.license
        licensed = self.state is LicenseState.LICENSED
        return {
            "state": self.state.value,
            "is_active": self.is_active,
            "message": self.message,
            "error_code": self.error_code,
            "machine_id": self.machine_id,
            "customer": lic.customer if lic else None,
            "license_id": lic.license_id if lic else None,
            "plan": lic.plan if lic else None,
            "updates_until": lic.updates_until.isoformat() if lic and lic.updates_until else None,
            "expires_at": format_dt(lic.expires_at) if lic and lic.expires_at else None,
            "features": dict(lic.features) if lic and licensed else {},
            "trial_days_left": self.trial_days_left,
            "trial_days_total": self.trial_days_total,
        }


def error_info(exc: Exception, machine_id: str) -> tuple[str, str]:
    """(código, mensaje en español) para un error de licencia."""
    if isinstance(exc, MachineMismatchError):
        return "wrong_machine", (
            "Esta licencia pertenece a otro equipo. "
            f"El código de este equipo es {machine_id}."
        )
    if isinstance(exc, LicenseExpiredError):
        exp = exc.license.expires_at
        when = f" el {fmt_date(exp.date())}" if exp else ""
        return "expired", f"La licencia venció{when}."
    if isinstance(exc, UnknownKeyError):
        return "unknown_key", (
            "Esta licencia fue firmada con una clave que esta versión de Stockly no conoce. "
            "Probá actualizar Stockly."
        )
    if isinstance(exc, InvalidSignatureError):
        return "bad_signature", "La licencia no es auténtica o fue modificada."
    if isinstance(exc, UnsupportedVersionError):
        return "unsupported_version", (
            "La licencia usa un formato más nuevo. Actualizá Stockly para usarla."
        )
    if isinstance(exc, InvalidTokenError):
        return "invalid_format", "El texto pegado no es una licencia de Stockly."
    return "invalid", "La licencia no es válida."
