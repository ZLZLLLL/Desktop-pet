# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path.cwd()
icon_path = project_dir / "app.ico"
version_file = project_dir / "version_info.txt"

datas = [
    (str(project_dir / "assets"), "assets"),
    (str(project_dir / "config.json"), "."),
    (str(project_dir / "dialogs.json"), "."),
    (str(project_dir / "save_data.json"), "."),
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DesktopPet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    icon=str(icon_path) if icon_path.exists() else None,
    version=str(version_file) if version_file.exists() else None,
    console=False,
    disable_windowed_traceback=False,
)
