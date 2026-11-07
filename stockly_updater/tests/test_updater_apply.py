import json
import os
import zipfile
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from stockly_updater import helper
from stockly_updater.github import UpdateCheckError
from stockly_updater.helper import apply_update, parse_args, relocate_self
from stockly_updater.installer import InstallError, backup_path
from stockly_updater.manifest import ManifestError, b64e, build_manifest, sign_manifest

EXE = "stockly.exe" if os.name == "nt" else "stockly"
HELPER = "update.exe" if os.name == "nt" else "update"
PKG = "Stockly-test-x64.zip"


class Env:
    """Un release falso (paquete + manifiesto firmado) y una instalación vieja."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.key = SigningKey.generate()
        self.pub = [b64e(bytes(self.key.verify_key))]
        monkeypatch.setattr(helper, "platform_suffix", lambda: "test-x64.zip")
        self.app = tmp_path / "install" / "stockly"
        (self.app / "_internal").mkdir(parents=True)
        (self.app / EXE).write_text("viejo")
        (self.app / HELPER).write_text("update-viejo")
        (self.app / "version.json").write_text(json.dumps({"version": "v1.0.0"}))
        self.files = {}
        self.launched = []
        self.build_release()

    def build_release(self, *, tag="v1.1.0", signer=None, tamper=False, unsigned=False, no_package=False):
        pkg = self.tmp / "release" / PKG
        pkg.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr(f"stockly/{EXE}", "nuevo")
            zf.writestr(f"stockly/{HELPER}", "update-nuevo")
            zf.writestr("stockly/_internal/lib.txt", "lib nueva")
            zf.writestr("stockly/version.json", json.dumps({"version": tag}))
        data, sig = sign_manifest(bytes(signer or self.key), build_manifest(tag, [pkg]))
        if tamper:
            with zipfile.ZipFile(pkg, "a") as zf:
                zf.writestr("stockly/backdoor.txt", "x")
        (self.tmp / "release" / "manifest.json").write_bytes(data)
        (self.tmp / "release" / "manifest.json.sig").write_text(sig)
        names = [] if no_package else [PKG]
        if not unsigned:
            names += ["manifest.json", "manifest.json.sig"]
        self.files = {f"https://dl/{n}": self.tmp / "release" / n for n in names}
        assets = [{"name": n, "browser_download_url": f"https://dl/{n}"} for n in names]
        self.client = type("C", (), {"release_by_tag": lambda s, t: {"tag_name": t, "assets": assets}})()

    def downloader(self, url, dest, progress=None):
        data = self.files[url].read_bytes()
        Path(dest).write_bytes(data)
        if progress:
            progress(len(data), len(data))

    def run(self, tag="v1.1.0", **kw):
        kw.setdefault("public_keys", self.pub)
        kw.setdefault("launcher", lambda args, cwd: self.launched.append((args, str(cwd))))
        return apply_update(self.app, tag, client=self.client, downloader=self.downloader,
                            sleep=lambda s: None, **kw)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return Env(tmp_path, monkeypatch)


def untouched(env):
    assert (env.app / EXE).read_text() == "viejo" and not backup_path(env.app).exists()
    assert not list(env.app.parent.glob(".stockly-staging-*"))


def test_success_updates_app_and_helper_and_restarts(env):
    steps = []
    assert env.run(restart=True, progress=lambda p, m: steps.append(p)) == "v1.1.0"
    assert (env.app / EXE).read_text() == "nuevo"
    assert (env.app / HELPER).read_text() == "update-nuevo"           # el ayudante también se actualiza
    assert json.loads((env.app / "version.json").read_text())["version"] == "v1.1.0"
    assert (backup_path(env.app) / EXE).read_text() == "viejo"        # respaldo de la anterior
    assert steps[-1] == 100 and steps == sorted(steps)
    assert env.launched == [([str(env.app / EXE)], str(env.app))]
    assert not list(env.app.parent.glob(".stockly-staging-*"))


def test_no_restart_flag(env):
    env.run(restart=False)
    assert env.launched == []


@pytest.mark.parametrize("tag", ["v1.0.0", "v0.9.0"])
def test_refuses_same_or_older_version(env, tag):
    with pytest.raises(InstallError, match="igual o más nueva"):
        env.run(tag=tag)
    untouched(env)


def test_unsigned_release_is_refused(env):
    env.build_release(unsigned=True)
    with pytest.raises(InstallError, match="no está firmado"):
        env.run()
    untouched(env)


def test_missing_platform_package(env):
    env.build_release(no_package=True)
    with pytest.raises(InstallError, match="no incluye el paquete"):
        env.run()


def test_tampered_package_is_refused_and_old_app_restarted(env):
    env.build_release(tamper=True)
    # el manifiesto se firmó ANTES de alterar el paquete: el hash ya no coincide
    with pytest.raises(ManifestError):
        env.run(restart=True)
    untouched(env)
    assert env.launched == [([str(env.app / EXE)], str(env.app))]     # no se deja al usuario sin Stockly


def test_wrong_signing_key_is_refused(env):
    env.build_release(signer=SigningKey.generate())
    with pytest.raises(ManifestError):
        env.run()
    untouched(env)


def test_fails_closed_without_embedded_keys(env):
    with pytest.raises(ManifestError, match="claves"):
        env.run(public_keys=[])
    untouched(env)


def test_manifest_for_another_version_is_refused(env):
    env.build_release(tag="v1.5.0")                 # manifiesto firmado de otra versión...
    with pytest.raises(ManifestError, match="otra versión"):
        env.run(tag="v1.1.0")                        # ...presentado como v1.1.0
    untouched(env)


def test_wait_for_stockly_timeout(env):
    with pytest.raises(InstallError, match="no se cerró"):
        env.run(wait_pid=os.getpid(), wait_timeout=0.05)
    untouched(env)


def test_download_failure_keeps_everything(env):
    def broken(url, dest, progress=None):
        raise UpdateCheckError("sin internet")
    with pytest.raises(UpdateCheckError):
        apply_update(env.app, "v1.1.0", client=env.client, downloader=broken, public_keys=env.pub,
                     sleep=lambda s: None, launcher=lambda a, c: env.launched.append(a), restart=True)
    untouched(env)
    assert len(env.launched) == 1


def test_helper_cli_basics(monkeypatch):
    args = parse_args(["--apply", "--tag", "v1.2.3", "--app-dir", "x", "--wait-pid", "7", "--restart"])
    assert args.apply and args.tag == "v1.2.3" and args.wait_pid == 7 and args.restart
    assert relocate_self(["--apply"]) is False                        # sin congelar no se relanza
    assert helper.main(["--selftest"]) == 0
    assert helper.main(["--apply"]) == 2                              # faltan --tag y --app-dir


def test_relocate_when_frozen(tmp_path, monkeypatch):
    exe = tmp_path / "update-bin"
    exe.write_text("binario")
    launched = []
    monkeypatch.setattr(helper.sys, "frozen", True, raising=False)
    monkeypatch.setattr(helper.sys, "executable", str(exe))
    monkeypatch.setattr(helper, "launch_detached", lambda args, cwd=None: launched.append(args))
    assert relocate_self(["--apply", "--tag", "v1.0.0"]) is True
    copy, *rest = launched[0]
    assert Path(copy) != exe and Path(copy).read_text() == "binario"          # copia temporal
    assert rest[-3:] == ["--relocated", "--app-dir", str(tmp_path)] or "--relocated" in rest
    launched.clear()
    assert relocate_self(["--apply", "--relocated"]) is False                  # ya relanzado: no se repite
    helper.shutil.rmtree(Path(copy).parent, ignore_errors=True)
