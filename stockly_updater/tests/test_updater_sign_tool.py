import pytest
from nacl.signing import SigningKey

from stockly_updater.manifest import b64e, verify_asset, verify_manifest

from stockly_updater import sign_release


@pytest.fixture
def key():
    return SigningKey.generate()


@pytest.fixture
def pkg(tmp_path):
    p = tmp_path / "Stockly-windows-x64.zip"
    p.write_bytes(b"paquete")
    return p


def test_signs_and_output_verifies(tmp_path, key, pkg, capsys):
    out = tmp_path / "meta"
    rc = sign_release.main(["--tag", "v1.2.3", "--out-dir", str(out), str(pkg)], env={"RELEASE_SIGNING_KEY": b64e(bytes(key))})
    assert rc == 0
    data, sig = (out / "manifest.json").read_bytes(), (out / "manifest.json.sig").read_text()
    manifest = verify_manifest(data, sig, [bytes(key.verify_key)])
    verify_asset(pkg, manifest, pkg.name)
    assert manifest["tag"] == "v1.2.3" and b64e(bytes(key)) not in capsys.readouterr().out   # no filtra el secreto


@pytest.mark.parametrize("env", [{}, {"RELEASE_SIGNING_KEY": "  "}, {"RELEASE_SIGNING_KEY": "no-es-una-clave"}])
def test_missing_or_invalid_key(tmp_path, pkg, env, capsys):
    assert sign_release.main(["--tag", "v1.0.0", "--out-dir", str(tmp_path / "m"), str(pkg)], env=env) == 1
    assert not (tmp_path / "m" / "manifest.json").exists()


def test_missing_file(tmp_path, key):
    assert sign_release.main(["--tag", "v1.0.0", "--out-dir", str(tmp_path / "m"), str(tmp_path / "no.zip")],
                             env={"RELEASE_SIGNING_KEY": b64e(bytes(key))}) == 1
