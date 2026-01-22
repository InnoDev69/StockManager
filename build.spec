# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Determinar extensión según OS
exe_extension = '.exe' if sys.platform == 'win32' else ''
exe_name = 'stock-manager-server' + exe_extension

# Incluye el .env si existe
datas_list = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('bd', 'bd'),
    ('api', 'api'),
]

# Agrega .env si existe
if os.path.exists('.env'):
    datas_list.append(('.env', '.'))

a = Analysis(
    ['main.py'],  # Cambiado: ahora está en la raíz
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('bd', 'bd'),
        ('api', 'api'),
    ],
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
        'python-dotenv',
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)