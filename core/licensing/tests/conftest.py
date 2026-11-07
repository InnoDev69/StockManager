import pytest

pytest.importorskip('stockly_license', reason='falta instalar stockly-license')

from datetime import date, datetime, timedelta, timezone

import pytest

from core.licensing.manager import LicenseManager
from core.licensing.state import LicenseState  # noqa
from core.licensing.updates import check_update, parse_release_date  # noqa
from stockly_license import LicenseVerifier, generate_keypair, issue_license

MACHINE = "ABCD-EFGH-IJKL-2345"
T0 = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


class Clock:
    """Reloj controlable para los tests."""

    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def keypair():
    return generate_keypair()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make_manager(tmp_path, keypair, clock):
    def factory(**kwargs):
        kwargs.setdefault("machine_id", MACHINE)
        kwargs.setdefault("clock", clock)
        return LicenseManager(tmp_path, LicenseVerifier.from_public_keys([keypair[1]]), **kwargs)
    return factory


@pytest.fixture
def manager(make_manager):
    return make_manager()


@pytest.fixture
def issue(keypair, clock):
    def factory(**kwargs):
        kwargs.setdefault("customer", "Kiosco Pepe")
        kwargs.setdefault("machine", MACHINE)
        kwargs.setdefault("now", clock.now)
        return issue_license(keypair[0], **kwargs)
    return factory
