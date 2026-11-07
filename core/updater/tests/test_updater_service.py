import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core.updater.service import UpdateError, UpdateService
from stockly_updater.github import RateLimitExceeded, UpdateCheckError

HELPER = "update.exe" if os.name == "nt" else "update"


class FakeClient:
    def __init__(self, release=None, error=None):
        self.release, self.error = release, error
        self.calls = []

    def latest_stable(self, force=False):
        self.calls.append(("latest", force))
        if self.error:
            raise self.error
        return self.release

    def cached_latest(self):
        self.calls.append(("cached",))
        return self.release


class FakeTimer:
    created = []

    def __init__(self, delay, fn):
        self.delay, self.fn, self.daemon, self.started = delay, fn, False, False
        FakeTimer.created.append(self)

    def start(self):
        self.started = True


def release(tag="v1.9.0", published="2026-11-01T10:00:00Z", body="notas"):
    return {"tag_name": tag, "published_at": published, "body": body}


class Clock:
    t = 10_000.0

    def __call__(self):
        return self.t


def make(tmp_path, client, **kw):
    kw.setdefault("current_version", "v1.8.5")
    kw.setdefault("frozen", True)
    kw.setdefault("app_dir", tmp_path / "app")
    kw.setdefault("timer_factory", FakeTimer)
    kw.setdefault("clock", Clock())
    (tmp_path / "app").mkdir(exist_ok=True)
    return UpdateService(tmp_path, client=client, **kw)


@pytest.fixture(autouse=True)
def _reset_timers():
    FakeTimer.created.clear()


def test_up_to_date(tmp_path):
    info = make(tmp_path, FakeClient(release("v1.8.5"))).check()
    assert not info.update_available and info.latest_version == "v1.8.5" and info.error is None


def test_update_available_without_licensing(tmp_path):
    info = make(tmp_path, FakeClient(release(body="x" * 9000))).check()
    assert info.update_available and info.allowed and info.decision_code == "licensing_disabled"
    assert len(info.notes) == 4000 and info.to_dict()["latest_version"] == "v1.9.0"


def test_no_releases_and_errors(tmp_path):
    assert "No hay" in make(tmp_path, FakeClient(None)).check().message
    assert "límite" in make(tmp_path, FakeClient(error=RateLimitExceeded())).check().error
    assert "No se pudo consultar" in make(tmp_path, FakeClient(error=UpdateCheckError("x"))).check().error


def test_status_is_offline(tmp_path):
    client = FakeClient(release())
    info = make(tmp_path, client).status()
    assert info.update_available and client.calls == [("cached",)]
    assert "Todavía no" in make(tmp_path, FakeClient(None)).status().message


def test_force_is_throttled(tmp_path):
    client = FakeClient(release())
    svc = make(tmp_path, client)
    svc.check(force=True)
    svc.check(force=True)                                   # dentro de los 60 s: no fuerza
    assert client.calls == [("latest", True), ("latest", False)]
    svc._clock.t += 61
    svc.check(force=True)
    assert client.calls[-1] == ("latest", True)


# ---- licencias ---------------------------------------------------------------------
@pytest.fixture
def licensed(tmp_path):
    pytest.importorskip("stockly_license")
    from core.licensing.manager import LicenseManager
    from stockly_license import LicenseVerifier, generate_keypair, issue_license
    private, public = generate_keypair()
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    manager = LicenseManager(tmp_path / "d", LicenseVerifier.from_public_keys([public]),
                             machine_id="ABCD-EFGH-IJKL-2345", clock=lambda: now)

    def activate(**kw):
        manager.activate(issue_license(private, customer="Pepe", machine="ABCD-EFGH-IJKL-2345", now=now, **kw))
        return manager
    return activate


def test_license_allows_within_support(tmp_path, licensed):
    manager = licensed(updates_until=date(2027, 11, 3))
    info = make(tmp_path, FakeClient(release()), license_manager=manager).check()
    assert info.update_available and info.allowed and info.decision_code == "ok"


def test_license_blocks_after_support(tmp_path, licensed):
    manager = licensed(updates_until=date(2026, 6, 30))
    svc = make(tmp_path, FakeClient(release()), license_manager=manager)
    info = svc.check()
    assert info.update_available and not info.allowed and info.decision_code == "support_expired"
    assert "30/06/2026" in info.message
    with pytest.raises(UpdateError) as exc:
        svc.apply()
    assert exc.value.code == "support_expired"


# ---- aplicar --------------------------------------------------------------------------
def test_apply_preconditions(tmp_path):
    with pytest.raises(UpdateError) as e:
        make(tmp_path, FakeClient(release()), frozen=False).apply()
    assert e.value.code == "not_installed"
    with pytest.raises(UpdateError) as e:
        make(tmp_path, FakeClient(release())).apply()                       # frozen pero sin ayudante
    assert e.value.code == "helper_missing"
    with pytest.raises(UpdateError) as e:
        make(tmp_path, FakeClient(release("v1.8.5"))).apply()
    assert e.value.code == "up_to_date"
    with pytest.raises(UpdateError) as e:
        make(tmp_path, FakeClient(error=UpdateCheckError("x"))).apply()
    assert e.value.code == "check_failed"


def test_apply_launches_helper_and_schedules_shutdown(tmp_path):
    launched, hooked, exited = [], [], []
    svc = make(tmp_path, FakeClient(release()), launcher=lambda args, **kw: launched.append((args, kw)),
               exit_fn=exited.append)
    (tmp_path / "app" / HELPER).write_text("bin")
    svc.set_shutdown_hook(lambda: hooked.append(True))
    assert svc.apply() == "v1.9.0"
    args, kw = launched[0]
    assert args[0] == str(tmp_path / "app" / HELPER) and args[1:] == [
        "--apply", "--tag", "v1.9.0", "--app-dir", str(tmp_path / "app"), "--wait-pid", str(os.getpid()), "--restart"]
    assert kw["cwd"] == str(tmp_path)
    first = FakeTimer.created[0]
    assert first.started and first.daemon and first.delay == 1.5 and hooked == []   # todavía no cerró
    first.fn()                                                                       # vence el primer timer
    assert hooked == [True] and len(FakeTimer.created) == 2
    force = FakeTimer.created[1]
    assert force.delay == 10.0 and exited == []
    force.fn()                                                                       # si no se cerró solo, se fuerza
    assert exited == [0]


def test_shutdown_survives_failing_hook(tmp_path):
    exited = []
    svc = make(tmp_path, FakeClient(release()), launcher=lambda *a, **k: None, exit_fn=exited.append)
    (tmp_path / "app" / HELPER).write_text("bin")
    svc.set_shutdown_hook(lambda: (_ for _ in ()).throw(RuntimeError("ventana ya cerrada")))
    svc.apply()
    FakeTimer.created[0].fn()
    FakeTimer.created[1].fn()
    assert exited == [0]


def test_launch_failure_does_not_schedule_shutdown(tmp_path):
    def boom(*a, **k):
        raise OSError("bloqueado por antivirus")
    svc = make(tmp_path, FakeClient(release()), launcher=boom)
    (tmp_path / "app" / HELPER).write_text("bin")
    with pytest.raises(UpdateError) as e:
        svc.apply()
    assert e.value.code == "launch_failed" and FakeTimer.created == []


# ---- mantenimiento -----------------------------------------------------------------------
def test_cleanup_backup_only_when_installed(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (tmp_path / "app.old").mkdir()
    (tmp_path / ".stockly-staging-abc").mkdir()
    assert make(tmp_path, FakeClient(release()), frozen=False).cleanup_backup() is False
    assert (tmp_path / "app.old").exists()
    assert make(tmp_path, FakeClient(release())).cleanup_backup() is True
    assert not (tmp_path / "app.old").exists() and not (tmp_path / ".stockly-staging-abc").exists()


def test_maintenance_never_raises(tmp_path):
    svc = make(tmp_path, FakeClient(release()))
    svc.check = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    svc.maintenance()
