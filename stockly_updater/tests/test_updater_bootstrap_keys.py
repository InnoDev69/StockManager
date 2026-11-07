import os
import shutil
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from stockly_updater import bootstrap_keys
from stockly_updater.manifest import b64d

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path):
    for rel, _ in bootstrap_keys.TARGETS.values():
        dst = tmp_path / "repo" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    return tmp_path / "repo"


def run(repo, tmp_path):
    return bootstrap_keys.main(["--repo", str(repo), "--license-keys-dir", str(tmp_path / "lic"),
                                "--release-keys-dir", str(tmp_path / "rel")])


def test_generates_keys_and_configures_repo(repo, tmp_path, capsys):
    assert run(repo, tmp_path) == 0
    out = capsys.readouterr().out
    for name, (rel, list_name) in bootstrap_keys.TARGETS.items():
        d = tmp_path / ("lic" if name == "licencias" else "rel")
        public = (d / "public.key").read_text().strip()
        private = (d / "private.key").read_text().strip()
        assert SigningKey(b64d(private)).verify_key.encode() == b64d(public)       # el par coincide
        assert (repo / rel).read_text().count(f'"{public}"') == 1                    # quedó en el repo
        assert private not in out                                                     # nunca imprime la privada
    assert "gh secret set RELEASE_SIGNING_KEY" in out


def test_is_idempotent_and_never_overwrites(repo, tmp_path):
    assert run(repo, tmp_path) == 0
    before = {p: p.read_text() for p in (tmp_path / "lic").iterdir()}
    files_before = {rel: (repo / rel).read_text() for rel, _ in bootstrap_keys.TARGETS.values()}
    assert run(repo, tmp_path) == 0
    assert {p: p.read_text() for p in (tmp_path / "lic").iterdir()} == before
    assert {rel: (repo / rel).read_text() for rel, _ in bootstrap_keys.TARGETS.values()} == files_before


def test_result_is_valid_python_with_the_keys_in_the_list(repo, tmp_path):
    run(repo, tmp_path)
    ns = {}
    exec((repo / "stockly_updater/release_keys.py").read_text(), ns)
    assert ns["RELEASE_PUBLIC_KEYS"] == [(tmp_path / "rel" / "public.key").read_text().strip()]


def test_rotation_keeps_old_key_in_the_list(repo, tmp_path):
    run(repo, tmp_path)
    old = (tmp_path / "rel" / "public.key").read_text().strip()
    for f in (tmp_path / "rel").iterdir():
        f.unlink()
    run(repo, tmp_path)                                                      # claves nuevas
    ns = {}
    exec((repo / "stockly_updater/release_keys.py").read_text(), ns)
    assert len(ns["RELEASE_PUBLIC_KEYS"]) == 2 and old in ns["RELEASE_PUBLIC_KEYS"]


def test_wrong_directory_is_a_clean_error(tmp_path, capsys):
    assert bootstrap_keys.main(["--repo", str(tmp_path), "--license-keys-dir", str(tmp_path / "a"),
                                "--release-keys-dir", str(tmp_path / "b")]) == 1
    assert not (tmp_path / "a").exists()


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX")
def test_private_keys_are_0600(repo, tmp_path):
    run(repo, tmp_path)
    for d in ("lic", "rel"):
        assert ((tmp_path / d / "private.key").stat().st_mode & 0o777) == 0o600


def test_compatible_with_the_license_cli(repo, tmp_path):
    pytest.importorskip("stockly_license")
    from stockly_license.keys import read_key_file, public_from_private
    run(repo, tmp_path)
    private = read_key_file(tmp_path / "lic" / "private.key")
    assert b64d((tmp_path / "lic" / "public.key").read_text().strip()) == public_from_private(private)
