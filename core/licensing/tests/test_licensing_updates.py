from datetime import date, datetime, timezone

import pytest

from core.licensing.manager import LicenseManager
from core.licensing.state import LicenseState  # noqa
from core.licensing.updates import check_update, parse_release_date  # noqa


@pytest.mark.parametrize("value, expected", [
    ("2026-11-03T12:00:00Z", date(2026, 11, 3)),
    ("2026-11-03T23:30:00-03:00", date(2026, 11, 4)),     # se normaliza a UTC
    ("2026-11-03", date(2026, 11, 3)),
    (datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc), date(2026, 11, 3)),
    (date(2026, 11, 3), date(2026, 11, 3)),
    ("no-es-fecha", None),
    ("", None),
    (None, None),
])
def test_parse_release_date(value, expected):
    assert parse_release_date(value) == expected


def test_trial_allows(manager):
    d = check_update(manager, "2030-01-01T00:00:00Z")
    assert d.allowed and d.code == "trial"


def test_licensed_within_and_after_support(manager, issue):
    manager.activate(issue(updates_until=date(2027, 11, 3)))
    ok = check_update(manager, "2027-11-03T10:00:00Z")
    assert ok.allowed and ok.code == "ok" and ok.updates_until == date(2027, 11, 3)
    late = check_update(manager, "2027-11-10T10:00:00Z")
    assert not late.allowed and late.code == "support_expired"
    assert "03/11/2027" in late.message and "10/11/2027" in late.message


def test_unknown_release_date_is_allowed(manager, issue):
    manager.activate(issue(updates_until=date(2020, 1, 1)))
    d = check_update(manager, "fecha rara")
    assert d.allowed and d.code == "unknown_date"


def test_no_license_after_trial_blocks(make_manager, clock):
    m = make_manager(trial_days=1)
    m.status()
    clock.advance(days=2)
    d = check_update(m, "2026-11-04")
    assert not d.allowed and d.code == "no_license"
