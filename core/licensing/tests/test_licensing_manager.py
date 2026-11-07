import json
from datetime import date, timedelta

import pytest

from core.licensing.manager import LicenseManager
from core.licensing.state import LicenseState  # noqa
from core.licensing.updates import check_update, parse_release_date  # noqa
from stockly_license import (
    InvalidSignatureError, InvalidTokenError, LicenseExpiredError, LicenseVerifier,
    MachineMismatchError, generate_keypair, issue_license,
)

MACHINE = "ABCD-EFGH-IJKL-2345"


# ---- período de prueba --------------------------------------------------------
def test_first_run_starts_trial(manager, tmp_path):
    st = manager.status()
    assert st.state is LicenseState.TRIAL
    assert st.trial_days_left == 30 and st.trial_days_total == 30
    assert st.is_active
    assert (tmp_path / "license" / "trial.json").is_file()


def test_trial_counts_down_and_expires(manager, clock):
    manager.status()
    clock.advance(days=10)
    assert manager.status().trial_days_left == 20
    clock.advance(days=19, hours=12)
    st = manager.status()
    assert st.state is LicenseState.TRIAL and st.trial_days_left == 1
    clock.advance(days=1)
    st = manager.status()
    assert st.state is LicenseState.TRIAL_EXPIRED
    assert st.error_code == "trial_expired" and not st.is_active


def test_clock_rollback_does_not_extend_trial(manager, clock):
    manager.status()
    clock.advance(days=20)
    assert manager.status().trial_days_left == 10      # guarda la última hora vista
    clock.advance(days=-15)                            # el usuario atrasa el reloj
    assert manager.status().trial_days_left == 10


def test_corrupt_trial_file_counts_as_expired(manager, tmp_path):
    manager.status()
    (tmp_path / "license" / "trial.json").write_text("{no es json", encoding="utf-8")
    st = manager.status()
    assert st.state is LicenseState.TRIAL_EXPIRED and st.error_code == "trial_unreadable"


def test_trial_copied_from_other_machine_is_expired(make_manager, tmp_path):
    make_manager().status()
    other = make_manager(machine_id="AAAA-AAAA-AAAA-AAAA")
    st = other.status()
    assert st.state is LicenseState.TRIAL_EXPIRED and st.error_code == "trial_other_machine"


def test_trial_days_configurable(make_manager):
    assert make_manager(trial_days=7).status().trial_days_left == 7
    assert make_manager(trial_days=0).status().state is LicenseState.TRIAL_EXPIRED


# ---- activación ---------------------------------------------------------------
def test_activate_persists_across_instances(manager, make_manager, issue):
    st = manager.activate(issue(updates_until=date(2027, 11, 3), features={"multicaja": 2}))
    assert st.state is LicenseState.LICENSED and st.license.customer == "Kiosco Pepe"
    again = make_manager().status()                    # "reinicio" de la app
    assert again.state is LicenseState.LICENSED and again.license.feature("multicaja") == 2


def test_activate_tolerates_whitespace(manager, issue):
    token = issue()
    wrapped = "\n ".join(token[i:i + 30] for i in range(0, len(token), 30))
    assert manager.activate(wrapped).state is LicenseState.LICENSED


@pytest.mark.parametrize("make_bad, exc", [
    (lambda issue, kp, clock: "basura", InvalidTokenError),
    (lambda issue, kp, clock: "", InvalidTokenError),
    (lambda issue, kp, clock: issue(machine="AAAA-AAAA-AAAA-AAAA"), MachineMismatchError),
    (lambda issue, kp, clock: issue(expires_at=clock.now + timedelta(seconds=1)), LicenseExpiredError),
])
def test_activate_rejects_and_saves_nothing(manager, issue, keypair, clock, tmp_path, make_bad, exc):
    token = make_bad(issue, keypair, clock)
    if exc is LicenseExpiredError:
        clock.advance(seconds=5)
    with pytest.raises(exc):
        manager.activate(token)
    assert not (tmp_path / "license" / "license.stk").exists()
    assert manager.status().state is LicenseState.TRIAL


def test_activate_rejects_foreign_signature(manager, clock):
    other_private, _ = generate_keypair()
    token = issue_license(other_private, customer="X", now=clock.now)
    with pytest.raises(Exception) as info:
        manager.activate(token)
    assert type(info.value).__name__ in ("UnknownKeyError", "InvalidSignatureError")


def test_invalid_stored_license_is_reported(manager, issue, tmp_path):
    manager.activate(issue())
    path = tmp_path / "license" / "license.stk"
    path.write_text(path.read_text().replace("STK1.", "STK1.A"), encoding="utf-8")  # alterada
    st = manager.status()
    assert st.state is LicenseState.INVALID and st.error_code in ("bad_signature", "invalid_format")
    assert not st.is_active


def test_license_expiring_later_becomes_invalid(manager, issue, clock):
    manager.activate(issue(expires_at=clock.now + timedelta(days=30)))
    clock.advance(days=31)
    st = manager.status()
    assert st.state is LicenseState.INVALID and st.error_code == "expired"


def test_deactivate_returns_to_trial(manager, issue):
    manager.activate(issue())
    assert manager.deactivate().state is LicenseState.TRIAL
    manager.deactivate()  # idempotente


# ---- funciones y actualizaciones -------------------------------------------------
def test_has_feature_by_state(manager, make_manager, issue, clock):
    assert not manager.has_feature("marca_blanca")                    # prueba: sin extras
    with_trial = make_manager(trial_features={"marca_blanca": True})
    assert with_trial.has_feature("marca_blanca")
    manager.activate(issue(features={"marca_blanca": True, "multicaja": 2, "bot": False}))
    assert manager.has_feature("marca_blanca") and manager.has_feature("multicaja")
    assert not manager.has_feature("bot") and not manager.has_feature("inexistente")
    assert manager.feature("multicaja") == 2 and manager.feature("x", "d") == "d"


def test_no_features_when_not_usable(make_manager, clock):
    m = make_manager(trial_days=1, trial_features={"marca_blanca": True})
    m.status()
    clock.advance(days=2)
    assert not m.has_feature("marca_blanca") and m.feature("marca_blanca", "def") == "def"


def test_updates_allowed_matrix(manager, make_manager, issue, clock):
    assert manager.updates_allowed(date(2030, 1, 1))                   # prueba: sí
    manager.activate(issue(updates_until=date(2027, 11, 3)))
    assert manager.updates_allowed(date(2027, 11, 3))
    assert not manager.updates_allowed(date(2027, 11, 4))
    manager.activate(issue())                                          # sin límite
    assert manager.updates_allowed(date(2099, 1, 1))
    m2 = make_manager(trial_days=1)
    m2.deactivate(); m2.status()
    clock.advance(days=2)
    assert not m2.updates_allowed(date(2026, 11, 4))                   # prueba vencida: no


# ---- serialización -------------------------------------------------------------
def test_status_to_dict_is_json_serializable(manager, issue):
    d = manager.status().to_dict()
    json.dumps(d)
    assert d["state"] == "TRIAL" and d["features"] == {} and d["customer"] is None
    manager.activate(issue(updates_until=date(2027, 11, 3), features={"multicaja": 2}))
    d = manager.status().to_dict()
    json.dumps(d)
    assert d["state"] == "LICENSED" and d["updates_until"] == "2027-11-03"
    assert d["features"] == {"multicaja": 2} and d["machine_id"] == MACHINE


def test_unbound_license_works_on_any_machine(make_manager, issue):
    token = issue(machine=None)
    other = make_manager(machine_id="AAAA-AAAA-AAAA-AAAA")
    assert other.activate(token).state is LicenseState.LICENSED


def test_state_atomic_write_leaves_no_temp_files(manager, issue, tmp_path):
    manager.activate(issue())
    names = sorted(p.name for p in (tmp_path / "license").iterdir())
    assert names == ["license.stk", "trial.json"] or names == ["license.stk"]


def test_plan_is_exposed_in_status(manager, issue):
    manager.activate(issue(plan="Convenio Sur"))
    assert manager.status().license.plan == "Convenio Sur"
    assert manager.status().to_dict()["plan"] == "Convenio Sur"
    assert manager.deactivate().to_dict()["plan"] is None
