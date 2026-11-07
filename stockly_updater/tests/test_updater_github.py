import io
import urllib.error

import pytest

from stockly_updater import github
from stockly_updater.github import (
    RateLimitExceeded, ReleaseClient, UpdateCheckError, download, find_asset, is_newer, parse_version,
)


class FakeResp:
    def __init__(self, body, headers=None):
        self._b = io.BytesIO(body if isinstance(body, bytes) else body.encode())
        self.headers = headers or {}

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://x", code, "err", headers or {}, None)


class FakeOpener:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, req, timeout):
        self.calls.append(req)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def releases_json(*tags, **flags):
    import json
    return json.dumps([{"tag_name": t, "published_at": "2026-11-01T00:00:00Z", **flags.get(t, {})} for t in tags])


@pytest.fixture
def clock():
    return Clock()


def make_client(tmp_path, clock, *responses, **kw):
    opener = FakeOpener(*responses)
    client = ReleaseClient(cache_path=tmp_path / "c.json", opener=opener, clock=clock,
                           sleep=lambda s: None, interval_hours=4, token="", **kw)
    return client, opener


@pytest.mark.parametrize("a, b, expected", [
    ("v1.8.6", "v1.8.5", True), ("v1.8.5", "1.8.5", False), ("v2.0.0", "v1.99.99", True),
    ("v1.10.0", "v1.9.9", True), ("v1.0.0", "0.0.0-dev", True), ("v1.0.0", "garbage", True),
])
def test_is_newer(a, b, expected):
    assert is_newer(a, b) is expected


def test_parse_version_variants():
    assert parse_version("v1.8.6") == (1, 8, 6)
    assert parse_version("1.8.6-dev+abc") == (1, 8, 6)
    assert parse_version("v2") == (2, 0, 0)


def test_picks_highest_stable_and_ignores_the_rest(tmp_path, clock):
    body = releases_json("v1.2.0", "v1.10.0", "v1.11.0", "v1.3.0-beta", "1.99.0", "v1.9.0",
                         **{"v1.11.0": {"draft": True}, "v1.9.0": {"prerelease": True}})
    client, _ = make_client(tmp_path, clock, FakeResp(body, {"ETag": "e1"}))
    assert client.latest_stable()["tag_name"] == "v1.10.0"


def test_cache_etag_and_interval(tmp_path, clock):
    body = releases_json("v1.2.0")
    client, opener = make_client(tmp_path, clock, FakeResp(body, {"ETag": "e1"}), http_error(304))
    client.latest_stable()
    assert len(opener.calls) == 1
    clock.t += 60
    client.latest_stable()                      # dentro del intervalo: no consulta la red
    assert len(opener.calls) == 1
    clock.t += 5 * 3600
    assert client.latest_stable()["tag_name"] == "v1.2.0"   # 304: usa el cache
    assert opener.calls[1].get_header("If-none-match") == "e1"
    assert client._load_cache()["checked_at"] == clock.t


def test_force_bypasses_interval(tmp_path, clock):
    client, opener = make_client(tmp_path, clock, FakeResp(releases_json("v1.0.0")), FakeResp(releases_json("v1.1.0")))
    assert client.latest_stable()["tag_name"] == "v1.0.0"
    assert client.latest_stable(force=True)["tag_name"] == "v1.1.0"


def test_cached_latest_never_touches_network(tmp_path, clock):
    client, opener = make_client(tmp_path, clock)
    assert client.cached_latest() is None and opener.calls == []


def test_rate_limit_without_cache_raises(tmp_path, clock):
    client, _ = make_client(tmp_path, clock, http_error(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1800000000"}))
    with pytest.raises(RateLimitExceeded):
        client.latest_stable()


def test_rate_limit_with_cache_uses_cache(tmp_path, clock):
    client, _ = make_client(tmp_path, clock, FakeResp(releases_json("v1.0.0")),
                            http_error(403, {"X-RateLimit-Remaining": "0"}))
    client.latest_stable()
    clock.t += 5 * 3600
    assert client.latest_stable()["tag_name"] == "v1.0.0"


def test_network_failure_uses_stale_cache_or_raises(tmp_path, clock):
    err = urllib.error.URLError("sin internet")
    client, opener = make_client(tmp_path, clock, err, err, err)
    with pytest.raises(UpdateCheckError):
        client.latest_stable()
    assert len(opener.calls) == github.MAX_RETRIES + 1           # reintentó
    client2, _ = make_client(tmp_path, clock, FakeResp(releases_json("v1.0.0")), err, err, err)
    client2.latest_stable()
    clock.t += 5 * 3600
    assert client2.latest_stable()["tag_name"] == "v1.0.0"       # sin internet: sigue con el cache


def test_server_error_is_retried(tmp_path, clock):
    client, opener = make_client(tmp_path, clock, http_error(502), FakeResp(releases_json("v1.0.0")))
    assert client.latest_stable()["tag_name"] == "v1.0.0" and len(opener.calls) == 2


def test_invalid_payload(tmp_path, clock):
    client, _ = make_client(tmp_path, clock, FakeResp("{no json"))
    with pytest.raises(UpdateCheckError):
        client.latest_stable()
    client, _ = make_client(tmp_path, clock, FakeResp('{"a": 1}'))
    with pytest.raises(UpdateCheckError):
        client.latest_stable()


def test_release_by_tag(tmp_path, clock):
    client, opener = make_client(tmp_path, clock, FakeResp('{"tag_name": "v1.2.3", "assets": []}'))
    assert client.release_by_tag("v1.2.3")["tag_name"] == "v1.2.3"
    assert opener.calls[0].full_url.endswith("/releases/tags/v1.2.3")
    for bad in ("../x", "v1.2", "latest"):
        with pytest.raises(UpdateCheckError):
            client.release_by_tag(bad)
    client, _ = make_client(tmp_path, clock, http_error(404))
    with pytest.raises(UpdateCheckError):
        client.release_by_tag("v9.9.9")


def test_platform_suffix(monkeypatch):
    monkeypatch.setattr(github.sys, "platform", "win32")
    assert github.platform_suffix() == "windows-x64.zip"
    monkeypatch.setattr(github.sys, "platform", "linux")
    monkeypatch.setattr(github.os.path, "exists", lambda p: p == "/etc/arch-release")
    assert github.platform_suffix() == "arch-x64.tar.gz"
    monkeypatch.setattr(github.os.path, "exists", lambda p: False)
    assert github.platform_suffix() == "ubuntu-x64.tar.gz"
    monkeypatch.setattr(github.sys, "platform", "darwin")
    with pytest.raises(RuntimeError):
        github.platform_suffix()


def test_find_asset_case_insensitive():
    assets = [{"name": "Stockly-Windows-x64.ZIP"}, {"name": "manifest.json"}]
    assert find_asset(assets, "windows-x64.zip")["name"] == "Stockly-Windows-x64.ZIP"
    assert find_asset(assets, "arch-x64.tar.gz") is None and find_asset(None, "x") is None


def test_download_progress_limit_and_errors(tmp_path):
    data = b"x" * 200_000
    seen = []
    download("https://x/a", tmp_path / "a.bin", lambda d, t: seen.append((d, t)),
             opener=lambda req, t: FakeResp(data, {"Content-Length": str(len(data))}))
    assert (tmp_path / "a.bin").read_bytes() == data and seen[-1] == (len(data), len(data))

    with pytest.raises(UpdateCheckError):
        download("https://x/b", tmp_path / "b.bin", opener=lambda req, t: FakeResp(data), max_bytes=1000)
    assert not (tmp_path / "b.bin").exists() and not (tmp_path / "b.bin.part").exists()

    def boom(req, t):
        raise urllib.error.URLError("caído")
    with pytest.raises(UpdateCheckError):
        download("https://x/c", tmp_path / "c.bin", opener=boom)
