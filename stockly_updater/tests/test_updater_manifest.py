import json

import pytest
from nacl.signing import SigningKey

from stockly_updater.manifest import (
    ManifestError, b64e, build_manifest, file_sha256, sign_manifest, verify_asset, verify_manifest,
)


@pytest.fixture
def key():
    return SigningKey.generate()


@pytest.fixture
def pub(key):
    return b64e(bytes(key.verify_key))


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "Stockly-windows-x64.zip"
    p.write_bytes(b"contenido del paquete")
    return p


def signed(key, asset, tag="v1.2.3"):
    return sign_manifest(bytes(key), build_manifest(tag, [asset]))


def test_roundtrip(key, pub, asset):
    data, sig = signed(key, asset)
    manifest = verify_manifest(data, sig, [pub])
    assert manifest["tag"] == "v1.2.3" and "Stockly-windows-x64.zip" in manifest["assets"]
    verify_asset(asset, manifest, asset.name)


def test_accepts_raw_bytes_keys_and_rotation(key, asset):
    data, sig = signed(key, asset)
    other = SigningKey.generate()
    assert verify_manifest(data, sig, [bytes(other.verify_key), bytes(key.verify_key)])


def test_fails_closed_without_keys(key, asset):
    data, sig = signed(key, asset)
    with pytest.raises(ManifestError, match="claves"):
        verify_manifest(data, sig, [])


def test_wrong_key_and_tampering(key, pub, asset):
    data, sig = signed(key, asset)
    with pytest.raises(ManifestError):
        verify_manifest(data, sig, [b64e(bytes(SigningKey.generate().verify_key))])
    forged = json.loads(data)
    forged["assets"][asset.name]["sha256"] = "0" * 64
    with pytest.raises(ManifestError):
        verify_manifest(json.dumps(forged, sort_keys=True, separators=(",", ":")).encode(), sig, [pub])
    with pytest.raises(ManifestError):
        verify_manifest(data, "!!!no-es-base64", [pub])


def test_license_style_signature_is_not_accepted(key, pub, asset):
    """Una firma sin el prefijo de dominio de releases no sirve (aunque la clave sea la misma)."""
    data, _ = signed(key, asset)
    raw_sig = b64e(key.sign(data).signature)
    with pytest.raises(ManifestError):
        verify_manifest(data, raw_sig, [pub])


def test_unknown_format(key, pub):
    data = json.dumps({"v": 99, "tag": "v1.0.0", "assets": {}}).encode()
    sig = b64e(key.sign(b"stockly-release-v1\n" + data).signature)
    with pytest.raises(ManifestError, match="formato"):
        verify_manifest(data, sig, [pub])


def test_asset_checks(key, pub, asset, tmp_path):
    data, sig = signed(key, asset)
    manifest = verify_manifest(data, sig, [pub])
    asset.write_bytes(b"contenido alterado!!")                 # distinto tamaño
    with pytest.raises(ManifestError, match="tamaño"):
        verify_asset(asset, manifest, asset.name)
    asset.write_bytes(b"x" * len(b"contenido del paquete"))    # mismo tamaño, otro contenido
    with pytest.raises(ManifestError, match="no coincide"):
        verify_asset(asset, manifest, asset.name)
    with pytest.raises(ManifestError, match="no figura"):
        verify_asset(asset, manifest, "otro.zip")


def test_file_sha256(asset):
    import hashlib
    assert file_sha256(asset) == hashlib.sha256(b"contenido del paquete").hexdigest()
