# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Get the PySide6 path
pyside6_path = Path(sys.base_prefix) / "Lib" / "site-packages" / "PySide6"
if not pyside6_path.exists():
    # Try in venv
    pyside6_path = Path(sys.executable).parent.parent / "Lib" / "site-packages" / "PySide6"

a = Analysis(
    ['src/launcher.py'],
    pathex=[],
    binaries=[
        (str(pyside6_path / "plugins"), "PySide6/plugins"),
    ],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'PySide6.QtCharts',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_pyside6_env.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
