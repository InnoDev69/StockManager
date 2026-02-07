# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

block_cipher = None

exe_extension = '.exe' if sys.platform == 'win32' else ''
exe_name = 'stock-manager-server' + exe_extension

webview_datas = collect_data_files('webview')

# Recoger typelibs y libs de gi en Linux
gi_datas = []
gi_binaries = []
if sys.platform == 'linux':
    gi_datas = collect_data_files('gi')
    gi_binaries = collect_dynamic_libs('gi')
    
    # Incluir GObject introspection typelibs
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
    binaries=[] + gi_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('bd', 'bd'),
        ('api', 'api'),
    ] + webview_datas + gi_datas,
    hiddenimports=[
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
        # GObject/GTK
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)