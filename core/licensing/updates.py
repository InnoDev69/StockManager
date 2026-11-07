"""Chequeo de licencia para el updater de Stockly."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from .manager import LicenseManager
from .state import LicenseState, fmt_date


@dataclass(frozen=True)
class UpdateDecision:
    allowed: bool
    code: str                 # ok | unknown_date | trial | support_expired | no_license
    message: str
    updates_until: date | None = None


def parse_release_date(value: str | date | datetime | None) -> date | None:
    """Fecha de publicación de un release (p. ej. `published_at` de GitHub, en UTC)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()
    except ValueError:
        return None


def check_update(manager: LicenseManager, published_at: str | date | datetime | None) -> UpdateDecision:
    """Decide si la licencia permite instalar el release publicado en `published_at`.

    Si la fecha no se puede interpretar se permite (no dejar a nadie sin parches
    por un dato raro de la API).
    """
    st = manager.status()
    release = parse_release_date(published_at)

    if st.state is LicenseState.LICENSED:
        until = st.license.updates_until
        if release is None:
            return UpdateDecision(True, "unknown_date", "No se pudo leer la fecha del release.", until)
        if st.license.updates_allowed(release):
            return UpdateDecision(True, "ok", "La licencia incluye esta actualización.", until)
        return UpdateDecision(
            False, "support_expired",
            f"Tu licencia incluye actualizaciones hasta el {fmt_date(until)} y esta versión se "
            f"publicó el {fmt_date(release)}. Renová el soporte para instalarla.",
            until,
        )
    if st.state is LicenseState.TRIAL:
        return UpdateDecision(True, "trial", "Actualizaciones habilitadas durante la prueba.")
    return UpdateDecision(
        False, "no_license", "Activá una licencia válida para instalar actualizaciones.",
    )
