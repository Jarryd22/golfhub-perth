#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from app.qt_golfhub_app import GolfHub


class PreviewGolfHub(GolfHub):
    def show_initial_cache(self):
        pass


def weather(label, low, high, rain, wind, icon_file="sheet_partly_cloudy.png"):
    return {"label": label, "tmin": low, "tmax": high, "rain_chance": rain, "wind": wind, "icon_file": icon_file}


def live(name, times, forecast):
    rows = []
    for time_label, minutes, spots in times:
        rows.append({"time": time_label, "minutes": minutes, "spots": spots, "course": "", "source_url": "https://example.com"})
    return {
        "site_name": name,
        "url": "https://example.com",
        "hole_label": "18 holes",
        "decorated_rows": rows,
        "weather": forecast,
        "error": None,
        "direct_booking": False,
    }


def direct(name, forecast):
    return {
        "site_name": name,
        "url": "https://example.com",
        "hole_label": "18 holes",
        "decorated_rows": [],
        "weather": forecast,
        "error": None,
        "direct_booking": True,
    }


parser = argparse.ArgumentParser()
parser.add_argument("--width", type=int, default=1500)
parser.add_argument("--height", type=int, default=940)
parser.add_argument("--output", default="ui_preview_v4.png")
parser.add_argument("--show-courses", action="store_true")
args = parser.parse_args()

app = QApplication(sys.argv[:1])
window = PreviewGolfHub()
window.resize(args.width, args.height)
window.context = {
    "sites": window.sites,
    "date": QDate.currentDate().addDays(1).toString("yyyy-MM-dd"),
    "holes": "18",
    "from": None,
    "to": None,
    "players": 2,
}
results = [
    live("Wembley", [("7:12 am", 432, 4), ("7:28 am", 448, 2), ("8:04 am", 484, 3)], weather("Mostly clear", 9, 18, 10, 13, "sheet_clear.png")),
    live("Collier Park", [("8:16 am", 496, 4), ("8:32 am", 512, 2), ("9:04 am", 544, 4)], weather("Partly cloudy", 10, 19, 20, 16)),
    live("Secret Harbour", [("9:20 am", 560, 3), ("9:36 am", 576, 4)], weather("Light showers", 11, 17, 45, 22, "sheet_partly_rain.png")),
    live("Joondalup Resort", [("7:04 am", 424, 3), ("7:12 am", 432, 4)], weather("Mostly clear", 9, 19, 10, 12)),
    live("Maylands", [("9:04 am", 544, 1), ("9:20 am", 560, 2)], weather("Partly cloudy", 10, 19, 20, 14)),
    direct("Point Walter", weather("Sunny", 11, 20, 5, 18, "sheet_clear.png")),
]
window.render_results(results, "Shared cache - updated 4 minutes ago")
window.show()
app.processEvents()
if args.show_courses:
    window.toggle_courses()
    app.processEvents()
target = ROOT / args.output
window.grab().save(str(target))
print(target)
window.close()
