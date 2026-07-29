# Optimized PyInstaller build for GolfHub Perth v5.
# QtWebEngine is retained; unrelated Qt QML, 3D and media bindings are excluded.
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
    hiddenimports=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "customtkinter",
        "winotify",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSpatialAudio",
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
    version=str(project / "build_tools" / "version_info_v5.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GolfHub Perth",
)

