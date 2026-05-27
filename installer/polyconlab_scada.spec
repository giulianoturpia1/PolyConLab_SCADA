# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for PolyConLab_SCADA.
# Run from the repository root:
#
#   pyinstaller installer/polyconlab_scada.spec
#
# Output: dist/PolyConLab_SCADA/PolyConLab_SCADA.exe
#
# See README.md §6 for full distribution instructions.

from PyInstaller.utils.hooks import collect_all

datas_pyside6, binaries_pyside6, hiddenimports_pyside6 = collect_all("PySide6")

a = Analysis(
    ["../src/main.py"],
    pathex=["../src"],
    binaries=binaries_pyside6,
    datas=[
        *datas_pyside6,
        # Bundle the images folder so the logo is available at runtime.
        ("../assets/images", "assets/images"),
    ],
    hiddenimports=hiddenimports_pyside6,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PolyConLab_SCADA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed app — no terminal window
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
    name="PolyConLab_SCADA",
)
