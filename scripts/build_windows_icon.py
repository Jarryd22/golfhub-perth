#!/usr/bin/env python3
"""Render the Golf Hub SVG identity into a multi-resolution Windows ICO."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "assets" / "golfhub_icon.svg"
target = ROOT / "assets" / "golfhub_icon.ico"

app = QGuiApplication.instance() or QGuiApplication([])
renderer = QSvgRenderer(str(source))
image = QImage(256, 256, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
renderer.render(painter, QRectF(0, 0, 256, 256))
painter.end()
if not image.save(str(target), "ICO"):
    raise SystemExit("Qt could not write the ICO file")
print(target)
