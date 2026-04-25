# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

block_cipher = None

# En onedir, el exe no lleva extensión en Linux; en Windows sí.
exe_extension = '.exe' if sys.platform == 'win32' else ''
exe_name = 'stockly' + exe_extension

webview_datas = collect_data_files('webview')

# Recoger typelibs y libs de gi en Linux
gi_datas = []
if sys.platform == 'linux':
    gi_datas = collect_data_files('gi')

    typelib_dirs = [
        '/usr/lib/x86_64-linux-gnu/girepository-1.0',
        '/usr/lib/girepository-1.0',
        '/usr/lib64/girepository-1.0',
    ]
    for td in typelib_dirs:
        if os.path.isdir(td):
            for f in os.listdir(td):
                if f.endswith('.typelib'):
                    gi_datas.append((os.path.join(td, f), 'gi_typelibs'))
            break

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('bd', 'bd'),
        ('api', 'api'),
        ('.env', '.'),
    ] + webview_datas + gi_datas + collect_data_files('barcode'),
    hiddenimports=[
        'pytz',
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
        'webview',
        'webview.platforms',
        'webview.platforms.gtk',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'gi',
        'gi.repository',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GdkPixbuf',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Gio',
        'gi.repository.Pango',
        'gi.repository.WebKit2',
        'cairo',
        'gi._gi',
        'gi._gi_cairo',
        'waitress',
        'barcode',
        'barcode.writer',
        'barcode.codex',
        'PIL',
        'reportlab',
        # Windows pywebview backend
        'clr',
        'clr_loader',
        'pythonnet',
        'webview.platforms.winforms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'numba', 'llvmlite'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Excluir libs de sistema en Linux para evitar conflictos con GTK del host
if sys.platform == 'linux':
    system_libs = ['libglib', 'libgio', 'libgobject', 'libgmodule']
    a.binaries = [
        (name, path, kind)
        for name, path, kind in a.binaries
        if not any(excl in name.lower() for excl in system_libs)
    ]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- MODO ONEDIR ---
# EXE solo lleva pyz + scripts. Los binaries/datas van en COLLECT.
# Esto evita la extracción a /tmp en cada arranque (que es lo que hace onefile).
exe = EXE(
    pyz,
    a.scripts,
    [],          # <-- vacío: NO pasar a.binaries / a.zipfiles / a.datas aquí
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,   # UPX desactivado: en onedir no ayuda y puede corromper .so de GTK
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/app/icon.ico' if sys.platform == 'win32' else 'static/app/icon.png',
    exclude_binaries=True,
)

# COLLECT ensambla la carpeta final dist/stockly/
# En Linux: dist/stockly/stockly  (ejecutable dentro de la carpeta)
# En Windows: dist/stockly/stockly.exe
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=sys.platform == 'linux',  # strip solo en Linux, ahorra ~20-30% de tamaño
    upx=False,
    name='stockly',
)
