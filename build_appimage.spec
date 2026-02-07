# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para construir StockManager AppImage con pywebview
Este spec incluye todas las dependencias necesarias para pywebview, PyQt5 y GTK
"""
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# Nombre del ejecutable
exe_name = 'StockManager'

# Datos a incluir
datas_list = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('bd', 'bd'),
    ('api', 'api'),
    ('data', 'data'),
    ('debug', 'debug'),
]

# Agrega .env si existe
if os.path.exists('.env'):
    datas_list.append(('.env', '.'))

# Hidden imports para pywebview y sus backends
hiddenimports = [
    # Flask y dependencias
    'flask',
    'werkzeug.security',
    'werkzeug.serving',
    'werkzeug.routing',
    'jinja2',
    'sqlite3',
    'csv',
    'io',
    'uuid',
    'datetime',
    'decimal',
    'requests',
    'dotenv',
    # pywebview y backends
    'webview',
    'pywebview',
    # PyQt5 backend
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtWebChannel',
    'PyQtWebEngine',
    'qtpy',
    # GTK backend (opcional)
    'gi',
    'gi.repository',
    'gi.repository.Gtk',
    'gi.repository.WebKit2',
    'gi.repository.GLib',
    # Otros
    'threading',
    'signal',
]

# Binarios adicionales (PyQt5 plugins y librerías)
binaries = []

# Collect PyQt5 data files and plugins
try:
    datas_list.extend(collect_data_files('PyQt5'))
except:
    pass

a = Analysis(
    ['launcher_pywebview.py'],
    pathex=[],
    binaries=binaries,
    datas=datas_list,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Sin consola para GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=exe_name,
)
