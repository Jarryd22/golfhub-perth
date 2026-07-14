# PyInstaller build for the production PySide6 desktop application.
from pathlib import Path

project = Path(SPECPATH)

a = Analysis(
    [str(project / "main_qt.py")],
    pathex=[str(project)],
    binaries=[],
    datas=[
        (str(project / "assets"), "assets"),
        (str(project / "data"), "data"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "customtkinter",
        "winotify",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GolfHub Perth",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project / "assets" / "golfhub_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GolfHub Perth",
)
