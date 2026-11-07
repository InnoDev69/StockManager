import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from stockly_updater import installer
from stockly_updater.installer import (
    InstallError, backup_path, find_app_root, finalize, read_installed_version, rollback,
    safe_extract, swap_install, wait_for_pid,
)


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def make_tar(path, members):
    with tarfile.open(path, "w:gz") as tf:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type, info.linkname = tarfile.SYMTYPE, data
                tf.addfile(info)
    return path


def test_zip_extract_ok_and_traversal(tmp_path):
    good = make_zip(tmp_path / "a.zip", {"stockly/stockly.exe": "x", "stockly/_internal/lib.dll": "y"})
    out = tmp_path / "out"
    safe_extract(good, out)
    assert (out / "stockly" / "_internal" / "lib.dll").read_text() == "y"
    evil = make_zip(tmp_path / "evil.zip", {"../fuera.txt": "x"})
    with pytest.raises(InstallError, match="insegura"):
        safe_extract(evil, tmp_path / "out2")
    assert not (tmp_path / "fuera.txt").exists()


def test_tar_extract_ok_internal_symlink_and_attacks(tmp_path):
    ok = make_tar(tmp_path / "a.tar.gz", [("stockly/stockly", "file", b"bin"), ("stockly/lib.so", "symlink", "lib.so.1"),
                                          ("stockly/lib.so.1", "file", b"lib")])
    out = tmp_path / "out"
    safe_extract(ok, out)
    assert (out / "stockly" / "stockly").read_bytes() == b"bin" and (out / "stockly" / "lib.so").is_symlink()
    for name, members in {
        "trav": [("../fuera", "file", b"x")],
        "abs": [("/tmp/stockly-evil", "file", b"x")],
        "link": [("stockly/l", "symlink", "../../../etc/passwd")],
    }.items():
        with pytest.raises(InstallError):
            safe_extract(make_tar(tmp_path / f"{name}.tar.gz", members), tmp_path / f"o-{name}")


def test_find_app_root_and_version(tmp_path):
    (tmp_path / "x" / "stockly").mkdir(parents=True)
    (tmp_path / "x" / "stockly" / ("stockly.exe" if os.name == "nt" else "stockly")).write_text("bin")
    (tmp_path / "x" / "stockly" / "stockly.exe").write_text("bin")        # cubre ambos nombres
    assert find_app_root(tmp_path / "x", "stockly") == tmp_path / "x" / "stockly"
    with pytest.raises(InstallError):
        find_app_root(tmp_path, "otra-app")
    app = tmp_path / "app"
    app.mkdir()
    assert read_installed_version(app) is None
    (app / "version.json").write_text('{"version": "v1.8.5"}')
    assert read_installed_version(app) == "v1.8.5"
    (app / "version.json").write_text("{no json")
    assert read_installed_version(app) is None


def test_wait_for_pid():
    assert wait_for_pid(2_000_000_000, timeout=1) is True          # no existe
    assert wait_for_pid(os.getpid(), timeout=0.05, poll=0.01) is False   # sigue vivo


def make_app(tmp_path, name="stockly", marker="viejo"):
    app = tmp_path / name
    (app / "_internal").mkdir(parents=True)
    (app / "stockly.exe").write_text(marker)
    return app


def make_new(tmp_path, marker="nuevo"):
    new = tmp_path / "staging" / "stockly"
    new.mkdir(parents=True)
    (new / "stockly.exe").write_text(marker)
    return new


def test_swap_success_keeps_backup(tmp_path):
    app, new = make_app(tmp_path), make_new(tmp_path)
    backup = swap_install(app, new)
    assert (app / "stockly.exe").read_text() == "nuevo"
    assert (backup / "stockly.exe").read_text() == "viejo" and backup == backup_path(app)
    finalize(backup)
    assert not backup.exists()


def test_swap_replaces_stale_backup(tmp_path):
    app, new = make_app(tmp_path), make_new(tmp_path)
    stale = backup_path(app)
    stale.mkdir()
    (stale / "basura").write_text("x")
    swap_install(app, new)
    assert not (stale / "basura").exists() and (stale / "stockly.exe").read_text() == "viejo"


def test_swap_missing_new_root_leaves_everything(tmp_path):
    app = make_app(tmp_path)
    with pytest.raises(InstallError):
        swap_install(app, tmp_path / "no-existe")
    assert (app / "stockly.exe").read_text() == "viejo"


def test_swap_move_failure_restores_previous(tmp_path, monkeypatch):
    app, new = make_app(tmp_path), make_new(tmp_path)
    monkeypatch.setattr(installer.shutil, "move", lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")))
    with pytest.raises(InstallError, match="restauró"):
        swap_install(app, new)
    assert (app / "stockly.exe").read_text() == "viejo" and not backup_path(app).exists()


def test_swap_locked_dir_retries_then_fails(tmp_path, monkeypatch):
    app, new = make_app(tmp_path), make_new(tmp_path)
    sleeps = []
    monkeypatch.setattr(installer.os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError("en uso")))
    with pytest.raises(InstallError, match="abierto"):
        swap_install(app, new, retries=3, sleep=sleeps.append)
    assert len(sleeps) == 2 and (app / "stockly.exe").read_text() == "viejo"


def test_rollback(tmp_path):
    app, new = make_app(tmp_path), make_new(tmp_path)
    backup = swap_install(app, new)
    rollback(app, backup)
    assert (app / "stockly.exe").read_text() == "viejo" and not backup.exists()


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX")
def test_mark_executables(tmp_path):
    app = tmp_path / "a"
    app.mkdir()
    for n in ("stockly", "update"):
        (app / n).write_text("x")
        (app / n).chmod(0o644)
    installer.mark_executables(app, "stockly", "update")
    assert (app / "stockly").stat().st_mode & 0o111 and (app / "update").stat().st_mode & 0o111
