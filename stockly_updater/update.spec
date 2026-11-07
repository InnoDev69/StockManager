# -*- mode: python ; coding: utf-8 -*-
# Compilar desde la raíz del repo:  pyinstaller --clean stockly_updater/update.spec
import os
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(SPECPATH, 'helper.py')],
    pathex=[ROOT],
    binaries=[],
    datas=collect_data_files('certifi'),
    hiddenimports=[
        'stockly_updater.constants', 'stockly_updater.github', 'stockly_updater.installer',
        'stockly_updater.manifest', 'stockly_updater.release_keys',
        'nacl', 'nacl.signing', 'nacl.exceptions', 'nacl._sodium', 'cffi',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
    ],
    excludes=['flask', 'werkzeug', 'webview', 'PIL', 'numpy', 'reportlab'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='update',
    debug=False, strip=False, upx=False,
    console=False,            # ventana de progreso; sin consola
)
