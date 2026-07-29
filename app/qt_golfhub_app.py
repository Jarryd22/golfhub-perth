#!/usr/bin/env python3
from __future__ import annotations

import sys
import traceback
import webbrowser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from PySide6.QtCore import QDate, QEvent, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.golfhub_core import (
    ASSET_DIR,
    COLLIER_EMPTY_BOOKING_NOTE,
    COLLIER_PUBLIC_CALENDAR_URL,
    CONFIG_FILE,
    DATA_DIR,
    fetch_site_result,
    load_sites,
    parse_user_time,
)
from app.course_results import direct_result
from app.booking_assist import BookingAssistError, build_booking_assist_plan
from app.booking_dialog import BookingAssistDialog
from app.shared_cache import (
    cache_age_label,
    fetch_shared_snapshot,
    load_local_snapshot,
    make_snapshot,
    save_local_snapshot,
)


APP_VERSION = "5.0"
MAX_SEARCH_DAYS = 28


def should_show_empty_course(result: dict[str, Any]) -> bool:
    '''Keep an actionable Collier card visible even with an older cache.'''
    return bool(
        result.get('show_when_empty')
        or (
            result.get('site_name') == 'Collier Park'
            and not result.get('decorated_rows')
        )
    )


PALETTE = {
    "bg": "#090909",
    "surface": "#111111",
    "surface2": "#171717",
    "surface3": "#202020",
    "line": "#303030",
    "line2": "#454545",
    "text": "#F6F6F6",
    "muted": "#B8B8B8",
    "faint": "#7D7D7D",
    "gold": "#F59E0B",
    "gold2": "#FDBA74",
    "mint": "#FBBF24",
    "danger": "#F28B74",
}



def consecutive_date_strings(start: QDate, day_count: int, maximum: QDate | None = None) -> list[str]:
    """Return a bounded, inclusive sequence used by both the UI and workers."""
    count = max(1, min(MAX_SEARCH_DAYS, int(day_count or 1)))
    if maximum is not None:
        count = min(count, max(1, start.daysTo(maximum) + 1))
    return [start.addDays(offset).toString("yyyy-MM-dd") for offset in range(count)]


def friendly_date(date_str: str) -> str:
    value = QDate.fromString(date_str, "yyyy-MM-dd")
    return value.toString("dddd, d MMMM yyyy") if value.isValid() else date_str


class ScanWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(list, bool)
    failed = Signal(str)

    def __init__(self, sites, date_str, hole_type, pref_from, pref_to, players):
        super().__init__()
        self.sites = sites
        self.date_str = date_str
        self.hole_type = hole_type
        self.pref_from = pref_from
        self.pref_to = pref_to
        self.players = players
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    def _fetch(self, site):
        if (getattr(site, "provider", "") or "").lower() == "direct":
            return direct_result(site, self.hole_type, self.date_str)
        return fetch_site_result(
            site, self.date_str, self.hole_type, self.pref_from, self.pref_to, self.players
        )

    @Slot()
    def run(self):
        try:
            total = len(self.sites)
            results_by_name = {}
            completed = 0
            with ThreadPoolExecutor(max_workers=min(8, max(1, total))) as pool:
                jobs = {pool.submit(self._fetch, site): site for site in self.sites}
                for job in as_completed(jobs):
                    site = jobs[job]
                    if self.cancel_requested:
                        for pending in jobs:
                            pending.cancel()
                        break
                    try:
                        results_by_name[site.name] = job.result()
                    except Exception as exc:
                        results_by_name[site.name] = {
                            "site_name": site.name,
                            "url": f"https://{site.domain}",
                            "hole_label": f"{self.hole_type} holes",
                            "decorated_rows": [],
                            "error": str(exc),
                            "not_configured": False,
                        }
                    completed += 1
                    self.progress.emit(completed, total, site.name)

            ordered = [results_by_name[s.name] for s in self.sites if s.name in results_by_name]
            self.finished.emit(ordered, self.cancel_requested)
        except Exception:
            self.failed.emit(traceback.format_exc())


class CacheWorker(QObject):
    finished = Signal(object)

    def __init__(self, date_strings: str | list[str], hole_type: str):
        super().__init__()
        self.date_strings = [date_strings] if isinstance(date_strings, str) else list(date_strings)
        self.hole_type = hole_type

    @Slot()
    def run(self):
        snapshots: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(self.date_strings)))) as pool:
            jobs = {
                pool.submit(fetch_shared_snapshot, date_str, self.hole_type): date_str
                for date_str in self.date_strings
            }
            for job in as_completed(jobs):
                date_str = jobs[job]
                try:
                    snapshots[date_str] = job.result()
                except Exception:
                    snapshots[date_str] = None
        self.finished.emit(snapshots)


class CourseRow(QFrame):
    toggled = Signal()

    def __init__(self, site):
        super().__init__()
        self.site = site
        self.setObjectName("CourseRow")
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.check = QCheckBox()
        self.check.setChecked(True)
        self.check.stateChanged.connect(self.toggled.emit)
        layout.addWidget(self.check)
        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(site.name)
        name.setObjectName("CourseName")
        holes = " / ".join(h for h in ("18", "9") if h in site.holes)
        detail = QLabel(f"{holes} holes")
        detail.setObjectName("CourseMeta")
        text.addWidget(name)
        text.addWidget(detail)
        layout.addLayout(text, 1)
        provider = (getattr(site, "provider", "") or "MiClub").upper()
        badge = QLabel("LIVE" if provider != "DIRECT" else "DIRECT")
        badge.setObjectName("LiveBadge" if provider != "DIRECT" else "DirectBadge")
        layout.addWidget(badge)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.check.toggle()
        super().mousePressEvent(event)


class TeeTimeCard(QFrame):
    def __init__(
        self,
        row: dict[str, Any],
        fallback_url: str | None,
        result: dict[str, Any] | None = None,
        booking_handler=None,
    ):
        super().__init__()
        self.row = row
        self.result = result or {}
        self.booking_handler = booking_handler
        self.url = row.get("source_url") or fallback_url
        self.setObjectName("TeeTime")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(12)
        time = QLabel(str(row.get("time") or "--"))
        time.setObjectName("TeeTimeValue")
        layout.addWidget(time)
        spots = int(row.get("spots", 0) or 0)
        info = QLabel(f"{spots} spot{'s' if spots != 1 else ''}")
        info.setObjectName("Muted")
        layout.addWidget(info)
        layout.addStretch()
        book = QPushButton("BOOK")
        book.setObjectName("MiniButton")
        book.setStyleSheet("QPushButton { background-color: #F59E0B; color: #090909; border: 0; border-radius: 7px; padding: 8px 13px; font-weight: 800; } QPushButton:hover { background-color: #FFB020; } QPushButton:pressed { background-color: #E48700; }")
        book.clicked.connect(self.open_url)
        layout.addWidget(book)

    def open_url(self):
        if self.booking_handler:
            self.booking_handler(self.result, self.row)
        elif self.url:
            webbrowser.open(self.url)


class WeatherBadge(QFrame):
    def __init__(self, weather: dict[str, Any] | None, compact: bool = False):
        super().__init__()
        self.setObjectName("WeatherBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 11, 7)
        layout.setSpacing(9)

        icon = QLabel()
        icon.setObjectName("WeatherIcon")
        icon_size = 34 if compact else 42
        icon.setFixedSize(icon_size, icon_size)
        icon.setAlignment(Qt.AlignCenter)
        icon_file = str((weather or {}).get("icon_file") or "sheet_partly_cloudy.png")
        icon_path = ASSET_DIR / "icons" / Path(icon_file).name
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull():
            icon.setPixmap(pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon.setText("WX")
        layout.addWidget(icon)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        layout.addLayout(copy)
        if not weather:
            title = QLabel("Forecast unavailable")
            title.setObjectName("WeatherTitle")
            copy.addWidget(title)
            return
        condition = str(weather.get("label") or "Forecast")
        high = weather.get("tmax", "--")
        low = weather.get("tmin", "--")
        title = QLabel(f"{condition}   {low}-{high} C")
        title.setObjectName("WeatherTitle")
        copy.addWidget(title)
        if not compact:
            rain = weather.get("rain_chance", "--")
            wind = weather.get("wind", "--")
            detail = QLabel(f"Rain {rain}%   |   Wind {wind} km/h")
            detail.setObjectName("WeatherDetail")
            copy.addWidget(detail)


class DirectCourseCard(QFrame):
    def __init__(self, result: dict[str, Any]):
        super().__init__()
        self.result = result
        self.setObjectName("DirectCourse")
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(7)
        name = QLabel(str(result.get("site_name") or "Course"))
        name.setObjectName("DirectTitle")
        layout.addWidget(name, 0, 0)
        button = QPushButton("VIEW COURSE")
        button.setObjectName("MiniButton")
        button.setStyleSheet("QPushButton { background-color: #F59E0B; color: #090909; border: 0; border-radius: 7px; padding: 8px 13px; font-weight: 800; } QPushButton:hover { background-color: #FFB020; } QPushButton:pressed { background-color: #E48700; }")
        button.clicked.connect(self.open_url)
        layout.addWidget(button, 0, 1, alignment=Qt.AlignRight)
        note = QLabel(str(result.get("booking_note") or "Official booking or visitor information."))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note, 1, 0, 1, 2)
        layout.addWidget(WeatherBadge(result.get("weather"), compact=True), 2, 0, 1, 2)

    def open_url(self):
        if self.result.get("url"):
            webbrowser.open(self.result["url"])


class ResponsiveCardGrid(QWidget):
    """A small wrapping grid that keeps cards readable on narrower screens."""

    def __init__(self, widgets, min_cell_width=260, max_columns=3):
        super().__init__()
        self.widgets = list(widgets)
        self.min_cell_width = min_cell_width
        self.max_columns = max_columns
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        for widget in self.widgets:
            widget.setMinimumWidth(min_cell_width)
            self.grid.addWidget(widget)
        self._relayout()

    def set_visible_limit(self, limit):
        for index, widget in enumerate(self.widgets):
            widget.setHidden(index >= limit)
        self._relayout()

    def _relayout(self):
        width = max(self.width(), self.min_cell_width)
        columns = max(1, min(self.max_columns, width // (self.min_cell_width + 10)))
        while self.grid.count():
            self.grid.takeAt(0)
        visible = [widget for widget in self.widgets if not widget.isHidden()]
        for index, widget in enumerate(visible):
            self.grid.addWidget(widget, index // columns, index % columns)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()


class MonthOnlyCalendar(QCalendarWidget):
    """Calendar month grid that never exposes adjacent-month date cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self._calendar_view = self.findChild(QTableView, "qt_calendar_calendarview")
        if self._calendar_view is not None:
            self._calendar_view.viewport().installEventFilter(self)

    def is_displayed_month_date(self, value):
        return value.year() == self.yearShown() and value.month() == self.monthShown()

    def _date_at_view_position(self, position):
        if self._calendar_view is None:
            return None
        index = self._calendar_view.indexAt(position)
        if not index.isValid() or index.row() == 0:
            return None
        first = QDate(self.yearShown(), self.monthShown(), 1)
        grid_start = first.addDays(1 - first.dayOfWeek())
        return grid_start.addDays((index.row() - 1) * 7 + index.column())

    def eventFilter(self, watched, event):
        if (
            self._calendar_view is not None
            and watched is self._calendar_view.viewport()
            and event.type()
            in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            )
        ):
            value = self._date_at_view_position(event.position().toPoint())
            if value is not None and not self.is_displayed_month_date(value):
                return True
        return super().eventFilter(watched, event)

    def paintCell(self, painter, rect, value):
        if not self.is_displayed_month_date(value):
            painter.fillRect(rect, QColor(PALETTE["surface2"]))
            return
        super().paintCell(painter, rect, value)


class MultiDatePopup(QFrame):
    """Anchored dropdown calendar for up to 28 individual booking dates."""

    datesAccepted = Signal(list)

    def __init__(self, minimum, maximum, selected, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("MultiDatePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(440)
        self._minimum = minimum
        self._maximum = maximum
        self._selected = {value for value in selected if minimum <= value <= maximum}
        if not self._selected:
            self._selected = {minimum}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)
        title = QLabel("Choose one or more dates")
        title.setObjectName("CalendarTitle")
        root.addWidget(title)
        help_text = QLabel("Select any dates you want to compare. They do not need to be consecutive.")
        help_text.setObjectName("CalendarHelp")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        self.today_label = QLabel(
            f"TODAY  â€¢  {QDate.currentDate().toString('dddd, d MMMM yyyy').upper()}"
        )
        self.today_label.setObjectName("CalendarToday")
        root.addWidget(self.today_label)

        month_navigation = QHBoxLayout()
        month_navigation.setContentsMargins(0, 0, 0, 0)
        self.previous_month_button = QPushButton("<")
        self.previous_month_button.setObjectName("CalendarNav")
        self.previous_month_button.setAccessibleName("Previous month")
        month_navigation.addWidget(self.previous_month_button)
        month_navigation.addStretch()
        self.month_label = QLabel()
        self.month_label.setObjectName("CalendarMonth")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_navigation.addWidget(self.month_label)
        month_navigation.addStretch()
        self.next_month_button = QPushButton(">")
        self.next_month_button.setObjectName("CalendarNav")
        self.next_month_button.setAccessibleName("Next month")
        month_navigation.addWidget(self.next_month_button)
        root.addLayout(month_navigation)

        self.calendar = MonthOnlyCalendar()
        self.calendar.setGridVisible(False)
        self.calendar.setNavigationBarVisible(False)
        self.calendar.setMinimumDate(minimum)
        self.calendar.setMaximumDate(maximum)
        self.calendar.setSelectionMode(QCalendarWidget.SelectionMode.SingleSelection)
        if self._selected:
            self.calendar.setSelectedDate(min(self._selected))
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.clicked.connect(self.toggle_date)
        self.calendar.currentPageChanged.connect(self.update_month_header)
        self.previous_month_button.clicked.connect(self.calendar.showPreviousMonth)
        self.next_month_button.clicked.connect(self.calendar.showNextMonth)
        root.addWidget(self.calendar)
        self.update_month_header(self.calendar.yearShown(), self.calendar.monthShown())

        status_row = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setObjectName("CalendarCount")
        status_row.addWidget(self.count_label)
        status_row.addStretch()
        self.reset_button = QPushButton("KEEP ONE DATE")
        self.reset_button.setObjectName("CalendarQuiet")
        self.reset_button.clicked.connect(self.clear_dates)
        status_row.addWidget(self.reset_button)
        root.addLayout(status_row)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("CalendarSummary")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.setObjectName("CalendarQuiet")
        self.cancel_button.clicked.connect(self.close)
        actions.addWidget(self.cancel_button)
        self.done_button = QPushButton("USE SELECTED DATES")
        self.done_button.setObjectName("CalendarPrimary")
        self.done_button.clicked.connect(self.apply_dates)
        actions.addWidget(self.done_button)
        root.addLayout(actions)
        self.refresh_highlights()

    def show_below(self, anchor):
        """Open immediately below the date control, or above it when space is tight."""
        self.adjustSize()
        self.resize(max(440, min(540, anchor.width())), self.sizeHint().height())
        point = anchor.mapToGlobal(anchor.rect().bottomLeft())
        point.setY(point.y() + 5)
        screen = QApplication.screenAt(point) or anchor.screen()
        available = screen.availableGeometry()
        x = max(available.left() + 8, min(point.x(), available.right() - self.width() - 8))
        y = point.y()
        if y + self.height() > available.bottom() - 8:
            above = anchor.mapToGlobal(anchor.rect().topLeft()).y() - self.height() - 5
            y = max(available.top() + 8, above)
        self.move(x, y)
        self.show()
        self.raise_()
        self.calendar.setFocus(Qt.FocusReason.PopupFocusReason)

    def toggle_date(self, value):
        if not self.calendar.is_displayed_month_date(value):
            return
        if value in self._selected:
            if len(self._selected) > 1:
                self._selected.remove(value)
        elif len(self._selected) < MAX_SEARCH_DAYS:
            self._selected.add(value)
        self.refresh_highlights()

    def update_month_header(self, year, month):
        shown = QDate(year, month, 1)
        self.month_label.setText(shown.toString("MMMM yyyy"))
        first_month = QDate(self._minimum.year(), self._minimum.month(), 1)
        last_month = QDate(self._maximum.year(), self._maximum.month(), 1)
        self.previous_month_button.setEnabled(shown > first_month)
        self.next_month_button.setEnabled(shown < last_month)

    def clear_dates(self):
        self._selected = {min(self._selected) if self._selected else self._minimum}
        self.refresh_highlights()

    def apply_dates(self):
        self.datesAccepted.emit(self.selected_dates())
        self.close()

    def refresh_highlights(self):
        value = self._minimum
        empty = QTextCharFormat()
        while value <= self._maximum:
            self.calendar.setDateTextFormat(value, empty)
            value = value.addDays(1)

        today = QDate.currentDate()
        if self._minimum <= today <= self._maximum:
            current = QTextCharFormat()
            current.setBackground(QColor(PALETTE["surface3"]))
            current.setForeground(QColor(PALETTE["gold2"]))
            current.setFontWeight(QFont.Weight.Bold)
            current.setFontUnderline(True)
            current.setUnderlineColor(QColor(PALETTE["gold"]))
            self.calendar.setDateTextFormat(today, current)

        for value in self._selected:
            marked = QTextCharFormat()
            marked.setBackground(QColor(PALETTE["gold"]))
            marked.setForeground(QColor(PALETTE["bg"]))
            marked.setFontWeight(QFont.Weight.Bold)
            if value == today:
                marked.setFontUnderline(True)
                marked.setUnderlineColor(QColor(PALETTE["bg"]))
            self.calendar.setDateTextFormat(value, marked)
        # Keep the month the golfer is browsing. Re-selecting the earliest
        # chosen date here would jump back to the first month after every
        # cross-month click, making it awkward to choose several August dates.
        count = len(self._selected)
        self.count_label.setText(f"{count} date{'s' if count != 1 else ''} selected")
        labels = [value.toString("ddd, d MMM yyyy") for value in sorted(self._selected)]
        if len(labels) <= 4:
            summary = "  â€¢  ".join(labels)
        else:
            summary = "  â€¢  ".join(labels[:3]) + f"  â€¢  +{len(labels) - 3} more"
        self.summary_label.setText(f"Selected: {summary}")
        self.done_button.setEnabled(True)

    def selected_dates(self):
        return sorted(self._selected)


class MultiDateButton(QPushButton):
    datesChanged = Signal()

    def __init__(self, minimum, maximum, selected, parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._dates = []
        self._popup = None
        self.setObjectName("DatePickerButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(250)
        self.clicked.connect(self.open_picker)
        self.set_dates(selected, emit=False)

    def open_picker(self):
        if self._popup is not None and self._popup.isVisible():
            self._popup.close()
            return
        self._popup = MultiDatePopup(
            self._minimum,
            self._maximum,
            self._dates,
            self.window(),
        )
        self._popup.datesAccepted.connect(self.set_dates)
        self._popup.destroyed.connect(self._popup_closed)
        self._popup.show_below(self)

    @Slot()
    def _popup_closed(self):
        self._popup = None

    def picker_popup(self):
        return self._popup

    def set_dates(self, values, emit=True):
        unique = sorted({
            value
            for value in values
            if value.isValid() and self._minimum <= value <= self._maximum
        })[:MAX_SEARCH_DAYS]
        if not unique:
            return
        changed = unique != self._dates
        self._dates = unique
        self.update_text()
        if changed and emit:
            self.datesChanged.emit()

    def selected_qdates(self):
        return list(self._dates)

    def update_text(self):
        first = self._dates[0]
        if len(self._dates) == 1:
            today = QDate.currentDate()
            if first == today:
                prefix = "Today  â€¢  "
            elif first == today.addDays(1):
                prefix = "Tomorrow  â€¢  "
            else:
                prefix = ""
            label = prefix + first.toString("ddd, d MMM yyyy")
        elif len(self._dates) <= 3:
            label = f"{len(self._dates)} dates  â€¢  " + " + ".join(
                value.toString("ddd d MMM") for value in self._dates
            )
        else:
            last = self._dates[-1]
            label = (
                f"{len(self._dates)} dates  â€¢  "
                f"{first.toString('d MMM')} â€“ {last.toString('d MMM yyyy')}"
            )
        self.setText(label + "   â–¾")
        self.setToolTip(
            "Selected dates:\n"
            + "\n".join(value.toString("ddd, d MMM yyyy") for value in self._dates)
        )

    def minimumDate(self):
        return self._minimum

    def maximumDate(self):
        return self._maximum

    def date(self):
        return self._dates[0]

    def setDate(self, value):
        self.set_dates([value])


class ResultCard(QFrame):
    def __init__(self, result: dict[str, Any], rows: list[dict[str, Any]], booking_handler=None):
        super().__init__()
        self.result = result
        self.rows = rows
        self.booking_handler = booking_handler
        self.collier_empty = (
            result.get('site_name') == 'Collier Park'
            and not result.get('decorated_rows')
        )
        self.open_target = (
            result.get('official_calendar_url')
            or (COLLIER_PUBLIC_CALENDAR_URL if self.collier_empty else None)
        )
        if self.collier_empty:
            self.result = dict(result)
            self.result['url'] = self.open_target
            result = self.result
        self.expanded = False
        self.setObjectName("ResultCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 18)
        outer.setSpacing(13)

        top = QGridLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setHorizontalSpacing(12)
        top.setVerticalSpacing(9)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel(str(result.get("site_name") or "Golf course"))
        title.setObjectName("ResultTitle")
        title_col.addWidget(title)
        calendar_status = result.get("calendar_availability")
        protected_calendar = bool(result.get("calendar_captcha_enabled"))
        if calendar_status == "available" and protected_calendar:
            meta_text = f"Times are available - Wembley asks for a quick check before showing exact times - {result.get('hole_label', '')}"
        elif calendar_status == "available":
            meta_text = f"Official calendar shows bookings available - {result.get('hole_label', '')}"
        elif calendar_status == "full":
            meta_text = f"Official calendar currently shows this round as full - {result.get('hole_label', '')}"
        elif calendar_status == "unreleased":
            meta_text = f"Timesheet not released yet - {result.get('hole_label', '')}"
        elif result.get("direct_booking"):
            meta_text = "Official course link - booking or visitor instructions"
        elif result.get("error"):
            meta_text = "Could not read live availability - direct booking is still available"
        else:
            meta_text = f"{len(rows)} matching tee time{'s' if len(rows) != 1 else ''} - {result.get('hole_label', '')}"
        if self.collier_empty:
            hole_label = result.get('hole_label', '')
            meta_text = f'No public tee times showing for this date - {hole_label}'
        meta = QLabel(meta_text)
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        meta.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_col.addWidget(meta)
        top.addLayout(title_col, 0, 0)
        open_button = QPushButton(
            "VIEW WEMBLEY TIMES"
            if calendar_status
            else ("VIEW COURSE" if result.get("direct_booking") else "OPEN BOOKING PAGE")
        )
        open_button.setObjectName("OutlineButton")
        if self.collier_empty:
            open_button.setText('VIEW OFFICIAL CALENDAR')
        open_button.clicked.connect(self.open_url)
        top.addWidget(open_button, 0, 1, alignment=Qt.AlignTop | Qt.AlignRight)
        top.addWidget(WeatherBadge(result.get("weather")), 1, 0, 1, 2, alignment=Qt.AlignLeft)
        top.setColumnStretch(0, 1)
        outer.addLayout(top)

        if result.get("error"):
            warning = QLabel("Live times were unavailable for this course. You can still open its official booking page.")
            warning.setObjectName("Warning")
            warning.setWordWrap(True)
            outer.addWidget(warning)
        elif calendar_status:
            note = QLabel(result.get("booking_note") or "Open Wembley's official calendar to check exact times.")
            note.setObjectName("AvailabilityAvailable" if calendar_status == "available" else "AvailabilityNotice")
            note.setWordWrap(True)
            outer.addWidget(note)
        elif result.get("direct_booking"):
            note = QLabel(result.get("booking_note") or "Check current times on the official course website.")
            note.setObjectName("DirectNote")
            note.setWordWrap(True)
            outer.addWidget(note)
        elif not rows:
            empty = QLabel("No matching tee times in this search window.")
            empty.setObjectName("EmptyNote")
            if self.collier_empty:
                empty.setText(
                    result.get('booking_note')
                    or COLLIER_EMPTY_BOOKING_NOTE
                )
                empty.setObjectName('AvailabilityNotice')
                empty.setWordWrap(True)
            outer.addWidget(empty)
        else:
            cards = [
                TeeTimeCard(row, result.get("url"), result, self.booking_handler)
                for row in rows
            ]
            self.tee_grid = ResponsiveCardGrid(cards, min_cell_width=250, max_columns=3)
            outer.addWidget(self.tee_grid)
            if len(rows) > 12:
                self.more_button = QPushButton(f"SHOW ALL {len(rows)} TIMES")
                self.more_button.setObjectName("QuietButton")
                self.more_button.clicked.connect(self.toggle_all_times)
                outer.addWidget(self.more_button, alignment=Qt.AlignHCenter)
                self.tee_grid.set_visible_limit(12)

    def toggle_all_times(self):
        self.expanded = not self.expanded
        self.tee_grid.set_visible_limit(len(self.rows) if self.expanded else 12)
        self.more_button.setText("SHOW FIRST 12" if self.expanded else f"SHOW ALL {len(self.rows)} TIMES")

    def open_url(self):
        if self.result.get("url"):
            webbrowser.open(self.result["url"])


class DaySection(QFrame):
    """A lazily populated date group, keeping long searches quick to display."""

    def __init__(self, date_str: str, detail: str, source: str, builder):
        super().__init__()
        self.date_str = date_str
        self.builder = builder
        self._built = False
        self._title = f"{friendly_date(date_str).upper()}  -  {detail}"
        self.setObjectName("DaySection")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("DayHeader")
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setHorizontalSpacing(10)
        header_layout.setVerticalSpacing(4)
        self.toggle = QPushButton(f"+  {self._title}")
        self.toggle.setObjectName("DayToggle")
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.toggled.connect(self._set_open)
        header_layout.addWidget(self.toggle, 0, 0)
        source_label = QLabel(source)
        source_label.setObjectName("DaySource")
        header_layout.addWidget(source_label, 1, 0)
        outer.addWidget(header)

        self.body = QWidget()
        self.body.setObjectName("DayBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 12, 12, 14)
        self.body_layout.setSpacing(10)
        self.body.setVisible(False)
        outer.addWidget(self.body)

    def set_expanded(self, expanded: bool):
        self.toggle.setChecked(expanded)

    def _set_open(self, expanded: bool):
        if expanded and not self._built:
            self.builder(self.body_layout)
            self._built = True
        self.body.setVisible(expanded)
        self.toggle.setText(f"{'-' if expanded else '+'}  {self._title}")


class GolfHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Golf Hub Perth")
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1500, max(1000, available.width() - 70)), min(940, max(660, available.height() - 70)))
        self.setMinimumSize(980, 640)
        self.sites = load_sites(DATA_DIR / CONFIG_FILE)
        self.course_rows: list[CourseRow] = []
        self.scan_thread = None
        self.scan_worker = None
        self.cache_thread = None
        self.cache_worker = None
        self._active_cache_context = None
        self._pending_cache_context = None
        self.context = {}
        self.last_results = []
        self._closing = False
        self._booking_dialogs = []

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(20, 18, 20, 18)
        shell.setSpacing(14)
        shell.addWidget(self.build_header())
        shell.addWidget(self.build_search_bar())

        self.splitter = QSplitter(Qt.Horizontal)
        self.course_panel = self.build_courses()
        self.splitter.addWidget(self.course_panel)
        self.splitter.addWidget(self.build_results())
        self.splitter.setSizes([0, 1450])
        self.splitter.setChildrenCollapsible(True)
        self.course_panel.setVisible(False)
        shell.addWidget(self.splitter, 1)

        self.setStyleSheet(self.styles())
        self.update_course_visibility()
        self.render_empty()

        # Owned single-shot timers are cancelled automatically with the window.
        # This avoids stale Qt callbacks touching deleted widgets during shutdown.
        self._initial_cache_timer = QTimer(self)
        self._initial_cache_timer.setSingleShot(True)
        self._initial_cache_timer.timeout.connect(self.show_initial_cache)
        self._cache_search_timer = QTimer(self)
        self._cache_search_timer.setSingleShot(True)
        self._cache_search_timer.timeout.connect(self.search_cache)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._reset_results_scroll)
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.close)
        self._initial_cache_timer.start(0)

    def build_header(self):
        card = QFrame()
        card.setObjectName("Hero")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        brand = QVBoxLayout()
        brand.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(7)
        name = QLabel("GOLF HUB")
        name.setObjectName("Logo")
        perth = QLabel("PERTH")
        perth.setObjectName("PerthBadge")
        row.addWidget(name)
        row.addWidget(perth)
        row.addStretch()
        brand.addLayout(row)
        tagline = QLabel("One search. Every public course. Plan your round with confidence.")
        tagline.setObjectName("Tagline")
        brand.addWidget(tagline)
        layout.addLayout(brand, 1)
        self.header_status = QLabel(f"{len(self.sites)} COURSES  /  CACHE READY")
        self.header_status.setObjectName("StatusBadge")
        layout.addWidget(self.header_status)
        return card

    def build_search_bar(self):
        card = QFrame()
        card.setObjectName("SearchCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        today = QDate.currentDate()
        self.date = MultiDateButton(
            today,
            today.addDays(27),
            [today.addDays(1)],
        )
        self.date.datesChanged.connect(self.update_day_mode)
        self.date_field = self.field("DATES", self.date)
        layout.addWidget(self.date_field, 0, 0, 1, 4)

        round_wrap = QWidget()
        round_layout = QHBoxLayout(round_wrap)
        round_layout.setContentsMargins(0, 0, 0, 0)
        round_layout.setSpacing(5)
        self.round_group = QButtonGroup(self)
        self.holes18 = QRadioButton("18 holes")
        self.holes9 = QRadioButton("9 holes")
        self.holes18.setChecked(True)
        for button in (self.holes18, self.holes9):
            button.setObjectName("RoundButton")
            self.round_group.addButton(button)
            round_layout.addWidget(button)
        self.holes18.toggled.connect(self.update_course_visibility)
        self.round_field = self.field("ROUND", round_wrap)
        layout.addWidget(self.round_field, 0, 4, 1, 4)

        self.time_from = QComboBox()
        self.time_to = QComboBox()
        for combo in (self.time_from, self.time_to):
            combo.setObjectName("Input")
            combo.addItem("Any")
            for hour in range(5, 20):
                for minute in (0, 30):
                    suffix = "am" if hour < 12 else "pm"
                    combo.addItem(f"{hour % 12 or 12}:{minute:02d} {suffix}")
        times = QWidget()
        times_layout = QHBoxLayout(times)
        times_layout.setContentsMargins(0, 0, 0, 0)
        times_layout.setSpacing(5)
        times_layout.addWidget(self.time_from)
        times_layout.addWidget(QLabel("to"))
        times_layout.addWidget(self.time_to)

        self.time_preset = QComboBox()
        self.time_preset.setObjectName("Input")
        self.time_preset.addItems(["Any time", "Morning", "Midday", "Afternoon", "Custom range"])
        self.time_preset.currentTextChanged.connect(self.apply_time_preset)
        self.time_field = self.field("TIME", self.time_preset)
        layout.addWidget(self.time_field, 0, 8, 1, 4)
        self.custom_time_field = self.field("CUSTOM RANGE", times)
        self.custom_time_field.setVisible(False)
        layout.addWidget(self.custom_time_field, 1, 5, 1, 3)

        self.players = QComboBox()
        self.players.setObjectName("Input")
        self.players.addItems(["Any", "1", "2", "3", "4"])
        self.players_field = self.field("PLAYERS", self.players)
        layout.addWidget(self.players_field, 1, 0, 1, 2)

        self.course_button = QPushButton("CHOOSE COURSES")
        self.course_button.setObjectName("OutlineButton")
        self.course_button.clicked.connect(self.toggle_courses)
        layout.addWidget(self.course_button, 1, 2, 1, 3, alignment=Qt.AlignBottom)
        for column in range(12):
            layout.setColumnStretch(column, 1)

        self.search_helper = QLabel("Fast cache first - use live refresh to confirm current availability")
        self.search_helper.setObjectName("Muted")
        self.search_helper.setWordWrap(True)
        layout.addWidget(self.search_helper, 1, 5, 1, 3)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addStretch()
        self.search_button = QPushButton("FIND TEE TIMES")
        self.search_button.setObjectName("PrimaryButton")
        self.search_button.clicked.connect(self.search_cache)
        actions.addWidget(self.search_button)
        self.live_button = QPushButton("REFRESH LIVE")
        self.live_button.setObjectName("OutlineButton")
        self.live_button.clicked.connect(self.search_live)
        actions.addWidget(self.live_button)
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_scan)
        actions.addWidget(self.stop_button)
        layout.addLayout(actions, 1, 8, 1, 4)
        self.update_day_mode()
        return card

    def day_count(self):
        return len(self.date.selected_qdates())

    def selected_dates(self):
        return [value.toString("yyyy-MM-dd") for value in self.date.selected_qdates()]

    def update_day_mode(self):
        if not hasattr(self, "date"):
            return
        count = self.day_count()
        if hasattr(self, "search_helper"):
            if count == 1:
                self.search_helper.setText("Fast cache first - use live refresh to confirm current availability")
            else:
                self.search_helper.setText(
                    f"Searching {count} selected dates from the fast shared cache"
                )
        if hasattr(self, "live_button"):
            single_day = count == 1
            self.live_button.setEnabled(
                single_day
                and not self._thread_running(self.scan_thread)
                and self.cache_thread is None
            )
            self.live_button.setToolTip(
                "Refresh this date directly from course sites"
                if single_day
                else "Multi-day results use the GitHub cache refreshed every 10 minutes"
            )

    def apply_time_preset(self, preset):
        ranges = {
            "Any time": ("Any", "Any"),
            "Morning": ("6:00 am", "11:30 am"),
            "Midday": ("12:00 pm", "2:30 pm"),
            "Afternoon": ("3:00 pm", "6:30 pm"),
        }
        custom = preset == "Custom range"
        self.custom_time_field.setVisible(custom)
        self.search_helper.setVisible(not custom)
        if not custom:
            start, end = ranges.get(preset, ("Any", "Any"))
            self.time_from.setCurrentText(start)
            self.time_to.setCurrentText(end)

    def toggle_courses(self):
        visible = not self.course_panel.isVisible()
        self.course_panel.setVisible(visible)
        self.splitter.setSizes([340, 1110] if visible else [0, 1450])
        self.course_button.setText("HIDE COURSES" if visible else "CHOOSE COURSES")

    def field(self, title, widget):
        wrap = QWidget()
        box = QVBoxLayout(wrap)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("FieldLabel")
        box.addWidget(label)
        box.addWidget(widget)
        return wrap

    def build_courses(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(290)
        panel.setMaximumWidth(410)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(11)
        title_row = QHBoxLayout()
        title = QLabel("Perth courses")
        title.setObjectName("PanelTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self.selected_count = QLabel("")
        self.selected_count.setObjectName("Muted")
        title_row.addWidget(self.selected_count)
        layout.addLayout(title_row)
        self.course_search = QLineEdit()
        self.course_search.setObjectName("CourseSearch")
        self.course_search.setPlaceholderText("Search courses or suburbs")
        self.course_search.textChanged.connect(self.update_course_visibility)
        layout.addWidget(self.course_search)
        buttons = QHBoxLayout()
        all_button = QPushButton("Select visible")
        none_button = QPushButton("Clear")
        for button in (all_button, none_button):
            button.setObjectName("QuietButton")
        all_button.clicked.connect(lambda: self.set_visible(True))
        none_button.clicked.connect(lambda: self.set_all(False))
        buttons.addWidget(all_button)
        buttons.addWidget(none_button)
        layout.addLayout(buttons)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(7)
        for site in self.sites:
            row = CourseRow(site)
            row.toggled.connect(self.update_selected_count)
            self.course_rows.append(row)
            body_layout.addWidget(row)
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        return panel

    def build_results(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("Tee times")
        title.setObjectName("PanelTitle")
        top.addWidget(title)
        top.addStretch()
        self.status = QLabel("Ready")
        self.status.setObjectName("Muted")
        top.addWidget(self.status)
        layout.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.results_scroll = QScrollArea()
        self.results_scroll.setObjectName("ResultsScroll")
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.viewport().setStyleSheet(f"background: {PALETTE['surface']};")
        self.results_body = QWidget()
        self.results_body.setObjectName("ResultsBody")
        self.results_layout = QVBoxLayout(self.results_body)
        self.results_layout.setContentsMargins(4, 4, 4, 4)
        self.results_layout.setSpacing(11)
        self.results_scroll.setWidget(self.results_body)
        layout.addWidget(self.results_scroll, 1)
        return panel

    def hole_type(self):
        return "9" if self.holes9.isChecked() else "18"

    def selected_sites(self):
        hole = self.hole_type()
        return [row.site for row in self.course_rows if row.check.isChecked() and hole in row.site.holes]

    def params(self):
        sites = self.selected_sites()
        if not sites:
            QMessageBox.information(self, "Choose a course", "Select at least one course for this round type.")
            return None
        players = None if self.players.currentText() == "Any" else int(self.players.currentText())
        date_strings = self.selected_dates()
        return {
            "sites": sites,
            "date": date_strings[0],
            "dates": date_strings,
            "holes": self.hole_type(),
            "from": parse_user_time(self.time_from.currentText()),
            "to": parse_user_time(self.time_to.currentText()),
            "players": players,
        }

    def update_course_visibility(self):
        query = self.course_search.text().strip().lower() if hasattr(self, "course_search") else ""
        hole = self.hole_type()
        for row in self.course_rows:
            visible = hole in row.site.holes and (not query or query in row.site.name.lower())
            row.setVisible(visible)
        self.update_selected_count()

    def update_selected_count(self):
        count = len(self.selected_sites())
        if hasattr(self, "selected_count"):
            self.selected_count.setText(f"{count} selected")
        if hasattr(self, "course_button"):
            self.course_button.setText(f"COURSES  {count} OF {len(self.sites)}")

    def set_visible(self, checked):
        for row in self.course_rows:
            if row.isVisible():
                row.check.setChecked(checked)
        self.update_selected_count()

    def set_all(self, checked):
        for row in self.course_rows:
            row.check.setChecked(checked)
        self.update_selected_count()

    def show_initial_cache(self):
        p = self.params()
        if not p:
            return
        payload = load_local_snapshot(p["date"], p["holes"])
        if payload:
            self.context = p
            self.render_snapshot(payload, "Saved on this device")
        self._cache_search_timer.start(100)

    def _reset_results_scroll(self):
        if self._closing:
            return
        try:
            self.results_scroll.verticalScrollBar().setValue(0)
        except RuntimeError:
            return

    def _stop_deferred_timers(self):
        for timer in (self._initial_cache_timer, self._cache_search_timer, self._scroll_timer):
            timer.stop()

    @staticmethod
    def _snapshot_search_context(context):
        snapshot = dict(context)
        snapshot['sites'] = list(context.get('sites') or [])
        snapshot['dates'] = list(context.get('dates') or [context['date']])
        return snapshot

    def search_cache(self):
        p = self.params()
        if not p:
            return
        p = self._snapshot_search_context(p)
        if self.cache_thread is not None:
            self._pending_cache_context = p
            self.search_button.setText('SEARCH QUEUED')
            self.status.setText('Your updated search is next...')
            self.header_status.setText('UPDATING SEARCH')
            return
        self._start_cache_search(p)

    def _start_cache_search(self, p):
        p = self._snapshot_search_context(p)
        self._active_cache_context = p
        self.context = p
        local_snapshots = {
            date_str: payload
            for date_str in p["dates"]
            if (payload := load_local_snapshot(date_str, p["holes"]))
        }
        if len(p["dates"]) == 1 and local_snapshots:
            self.render_snapshot(local_snapshots[p["date"]], "Saved on this device")
        elif local_snapshots:
            self.render_snapshot_batch(
                local_snapshots,
                {date_str: "Saved on this device" for date_str in local_snapshots},
            )
        else:
            self.render_empty("Checking the shared cache...")
        # Keep Find available while the shared cache is checked. A second click
        # queues the newest controls and starts as soon as this request ends.
        self.search_button.setEnabled(True)
        self.search_button.setText('UPDATE SEARCH')
        self.live_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.status.setText(f"Checking shared cache for {len(p['dates'])} day{'s' if len(p['dates']) != 1 else ''}...")
        self.header_status.setText("CHECKING SHARED CACHE")
        self.cache_thread = QThread()
        self.cache_worker = CacheWorker(p["dates"], p["holes"])
        self.cache_worker.moveToThread(self.cache_thread)
        self.cache_thread.started.connect(self.cache_worker.run)
        self.cache_worker.finished.connect(self.cache_finished)
        self.cache_worker.finished.connect(self.cache_thread.quit)
        self.cache_thread.finished.connect(self.cache_worker.deleteLater)
        self.cache_thread.finished.connect(self.cache_thread.deleteLater)
        self.cache_thread.finished.connect(self.cache_thread_done)
        self.cache_thread.start()

    @Slot(object)
    def cache_finished(self, snapshots):
        if self._closing:
            return
        if self._pending_cache_context is not None:
            # A newer set of controls is queued. Do not flash or leave the old
            # result set on screen while the old thread finishes shutting down.
            self.status.setText('Loading your updated search...')
            self.header_status.setText('UPDATING SEARCH')
            return
        active_context = self._active_cache_context or self.context
        if not active_context:
            return
        self.context = self._snapshot_search_context(active_context)
        dates = self.context.get("dates") or [self.context["date"]]
        if snapshots and "results" in snapshots:
            snapshots = {dates[0]: snapshots}
        snapshots = snapshots or {}
        combined = {}
        sources = {}
        for date_str in dates:
            if snapshots.get(date_str):
                combined[date_str] = snapshots[date_str]
                sources[date_str] = "Shared cache"
                continue
            local = load_local_snapshot(date_str, self.context["holes"])
            if local:
                combined[date_str] = local
                sources[date_str] = "Saved on this device"

        if len(dates) == 1:
            payload = combined.get(dates[0])
            if payload:
                self.render_snapshot(payload, sources[dates[0]])
            else:
                self.search_live(self.context)
            return

        if combined:
            self.render_snapshot_batch(combined, sources)
        else:
            self.render_empty("No cached results were available for these dates. Try a shorter range or search again shortly.")
            self.status.setText("Multi-day cache temporarily unavailable")
            self.header_status.setText("SHARED CACHE UNAVAILABLE")

    def render_snapshot(self, payload, source):
        results = self.add_direct_results(payload.get("results", []), self.context.get("date"))
        age = cache_age_label(payload.get("generated_at"))
        self.render_results(results, f"{source} - updated {age}")
        label = "SHARED CACHE" if source == "Shared cache" else "SAVED CACHE"
        self.header_status.setText(f"{label} / {age.upper()}")

    def render_snapshot_batch(self, snapshots, sources):
        days = []
        dates = self.context.get("dates") or [self.context["date"]]
        for date_str in dates:
            payload = snapshots.get(date_str)
            if payload:
                results = self.add_direct_results(payload.get("results", []), date_str)
                age = cache_age_label(payload.get("generated_at"))
                source = f"{sources.get(date_str, 'Cache')} - updated {age}"
            else:
                results = self.add_direct_results([], date_str)
                source = "Cache unavailable for this date"
            days.append({"date": date_str, "results": results, "source": source, "available": bool(payload)})
        available = sum(bool(day["available"]) for day in days)
        self.render_multi_results(days, f"{available} of {len(days)} dates loaded")
        self.header_status.setText(f"SHARED CACHE / {available} OF {len(days)} DAYS")

    def add_direct_results(self, results, date_str=None):
        selected = {site.name: site for site in self.context.get("sites", [])}
        merged = [result for result in results if result.get("site_name") in selected]
        present = {result.get("site_name") for result in merged}
        for site in selected.values():
            if (getattr(site, "provider", "") or "").lower() == "direct" and site.name not in present:
                # Fast fallback only. The shared/live worker supplies weather off the GUI thread.
                merged.append(direct_result(site, self.context["holes"]))
        return merged

    def search_live(self, context=None):
        p = context if isinstance(context, dict) else self.params()
        if not p or (self.scan_thread and self._thread_running(self.scan_thread)):
            return
        p = self._snapshot_search_context(p)
        if len(p.get("dates") or [p["date"]]) != 1:
            self.status.setText("Live refresh is available for one date; multi-day results use the 10-minute cache")
            return
        self.context = p
        if not self.last_results:
            self.render_empty("Checking courses live...")
        self.status.setText("Checking courses live...")
        self.header_status.setText("LIVE REFRESH IN PROGRESS")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.search_button.setEnabled(False)
        self.live_button.setEnabled(False)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.scan_thread = QThread()
        self.scan_worker = ScanWorker(p["sites"], p["date"], p["holes"], p["from"], p["to"], p["players"])
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self.scan_progress)
        self.scan_worker.finished.connect(self.scan_finished)
        self.scan_worker.failed.connect(self.scan_failed)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.failed.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread_done)
        self.scan_thread.start()

    def stop_scan(self):
        if self.scan_worker:
            self.scan_worker.request_cancel()
        self.stop_button.setEnabled(False)
        self.status.setText("Stopping after current requests...")

    @Slot(int, int, str)
    def scan_progress(self, complete, total, name):
        self.progress.setValue(int(complete / max(1, total) * 100))
        self.status.setText(f"Checked {complete} of {total} - {name}")

    @Slot(list, bool)
    def scan_finished(self, results, cancelled):
        self.search_button.setEnabled(True)
        self.live_button.setEnabled(True)
        self.stop_button.setVisible(False)
        self.progress.setVisible(False)
        if self._closing:
            return
        if cancelled:
            self.status.setText("Stopped - partial results were not saved")
            self.header_status.setText("REFRESH STOPPED / CACHE PRESERVED")
            if not self.last_results:
                self.render_empty("Refresh stopped. Your existing cache was not replaced.")
            return
        self.last_results = results
        try:
            save_local_snapshot(make_snapshot(self.context["date"], self.context["holes"], results))
        except Exception:
            pass
        self.render_results(results, "Live results - updated now")
        self.header_status.setText("LIVE RESULTS / UPDATED NOW")

    @Slot(str)
    def scan_failed(self, error):
        self.search_button.setEnabled(True)
        self.live_button.setEnabled(True)
        self.stop_button.setVisible(False)
        self.progress.setVisible(False)
        self.status.setText("Live refresh failed - cached results preserved")
        self.header_status.setText("LIVE REFRESH FAILED / CACHE PRESERVED")
        if not self._closing:
            QMessageBox.critical(
                self,
                "Could not refresh",
                "GolfHub kept the previous cached results.\n\n" + error.splitlines()[-1],
            )

    @staticmethod
    def _thread_running(thread):
        try:
            return bool(thread and thread.isRunning())
        except RuntimeError:
            return False

    def cache_thread_done(self):
        self.cache_thread = None
        self.cache_worker = None
        self._active_cache_context = None
        if not self._closing and self._pending_cache_context is not None:
            pending = self._pending_cache_context
            self._pending_cache_context = None
            self._start_cache_search(pending)
            return
        self.search_button.setEnabled(not self._thread_running(self.scan_thread))
        self.search_button.setText('FIND TEE TIMES')
        if not self._thread_running(self.scan_thread):
            self.progress.setVisible(False)
        self.update_day_mode()
        self._finish_pending_close()

    def scan_thread_done(self):
        self.scan_thread = None
        self.scan_worker = None
        self._finish_pending_close()

    def _finish_pending_close(self):
        if self._closing and not self._thread_running(self.cache_thread) and not self._thread_running(self.scan_thread):
            self._close_timer.start(0)

    def _booking_choice(self, plan):
        box = QMessageBox(self)
        box.setWindowTitle("Continue to the course")
        box.setIcon(QMessageBox.NoIcon)
        noun = "spot" if plan.requested_players == 1 else "spots"
        box.setText(
            f"<b style='font-size:18px'>How would you like to continue?</b><br>"
            f"<span style='color:#FDBA74'>{plan.course_name} &nbsp; | &nbsp; "
            f"{plan.tee_time} &nbsp; | &nbsp; {plan.requested_players} "
            f"{'player' if plan.requested_players == 1 else 'players'}</span>"
        )
        box.setInformativeText(
            f"<b>Prepare {plan.requested_players} {'player' if plan.requested_players == 1 else 'players'}</b><br>"
            f"Temporarily selects {plan.requested_players} available {noun}, opens player "
            "details, and stops. You review the page and continue yourself.<br><br>"
            "<b>Open normally</b><br>"
            "Nothing is selected. Choose players yourself on the official course page.<br><br>"
            "<span style='color:#B8B8B8'>GolfHub never confirms, checks out or pays. "
            "If you prepare players and stop, use RELEASE HOLDS &amp; CLOSE.</span>"
        )
        hold_button = box.addButton("PREPARE & OPEN", QMessageBox.AcceptRole)
        manual_button = box.addButton("OPEN NORMALLY", QMessageBox.ActionRole)
        back_button = box.addButton("GO BACK", QMessageBox.RejectRole)
        hold_button.setObjectName("ChoicePrimary")
        manual_button.setObjectName("ChoiceSecondary")
        back_button.setObjectName("ChoiceBack")
        box.setDefaultButton(hold_button)
        hold_button.setFocus()
        box.setStyleSheet(
            """
            QMessageBox { background:#101010; color:#F6F6F6; }
            QMessageBox QLabel { color:#F6F6F6; min-width:540px; line-height:1.35; }
            QMessageBox QPushButton {
                min-height:38px; min-width:130px; padding:0 14px; border-radius:8px;
                background:#202020; color:#FFFFFF; border:1px solid #484848; font-weight:800;
            }
            QMessageBox QPushButton:hover { border-color:#F59E0B; }
            QMessageBox QPushButton#ChoicePrimary {
                background:#F59E0B; color:#090909; border-color:#F59E0B;
            }
            QMessageBox QPushButton#ChoicePrimary:hover { background:#FFB020; }
            QMessageBox QPushButton#ChoiceBack {
                background:transparent; color:#C8C8C8; border-color:#383838;
            }
            """
        )
        box.exec()
        if box.clickedButton() is hold_button:
            return "hold"
        if box.clickedButton() is manual_button:
            return "manual"
        return "cancel"

    def _keep_booking_dialog(self, dialog):
        self._booking_dialogs.append(dialog)

        def forget(*_):
            if dialog in self._booking_dialogs:
                self._booking_dialogs.remove(dialog)

        dialog.destroyed.connect(forget)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def open_tee_time(self, result, row):
        source_url = row.get("source_url") or result.get("url")
        if not source_url:
            QMessageBox.information(self, "Booking page unavailable", "This tee time did not include an official booking link.")
            return

        players = self.context.get("players")
        if players is None:
            webbrowser.open(source_url)
            return

        try:
            plan = build_booking_assist_plan(
                source_url=source_url,
                tee_time=str(row.get("time") or ""),
                players=int(players),
                available_spots=int(row.get("spots", 0) or 0),
                provider=result.get("provider"),
                course_name=str(result.get("site_name") or "this course"),
            )
        except (BookingAssistError, TypeError, ValueError) as exc:
            QMessageBox.information(
                self,
                "Open official booking page",
                f"GolfHub cannot safely preselect this tee time: {exc}\n\n"
                "The official page will open for manual selection.",
            )
            webbrowser.open(source_url)
            return

        if not plan.capability.confirmed_temporary_hold_supported:
            QMessageBox.information(
                self,
                "Select players on the official page",
                "This provider does not offer a verified GolfHub player-count hand-off. "
                f"The official page will open; select {players} player(s) there.",
            )
            webbrowser.open(plan.open_url)
            return

        choice = self._booking_choice(plan)
        if choice == "manual":
            webbrowser.open(plan.open_url)
            return
        if choice != "hold":
            return

        try:
            confirmed = build_booking_assist_plan(
                source_url=plan.open_url,
                tee_time=plan.tee_time,
                players=plan.requested_players,
                available_spots=plan.available_spots,
                provider=plan.provider,
                course_name=plan.course_name,
                temporary_hold_confirmed=True,
            )
            dialog = BookingAssistDialog(confirmed, self)
        except (BookingAssistError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Player assist unavailable",
                f"GolfHub did not hold any spots: {exc}\n\n"
                "The official page will open for manual selection.",
            )
            webbrowser.open(plan.open_url)
            return
        self._keep_booking_dialog(dialog)

    def closeEvent(self, event):
        open_bookings = [dialog for dialog in self._booking_dialogs if dialog and dialog.isVisible()]
        if open_bookings:
            dialog = open_bookings[-1]
            dialog.raise_()
            dialog.activateWindow()
            QMessageBox.information(
                self,
                "Finish the booking window first",
                "Close the official booking window first. If GolfHub prepared player spots, use RELEASE HOLDS & CLOSE before leaving.",
            )
            event.ignore()
            return
        if self._thread_running(self.cache_thread) or self._thread_running(self.scan_thread):
            self._closing = True
            self._stop_deferred_timers()
            if self.scan_worker:
                self.scan_worker.request_cancel()
            self.status.setText("Finishing active requests before closing...")
            self.search_button.setEnabled(False)
            self.live_button.setEnabled(False)
            event.ignore()
            return
        self._stop_deferred_timers()
        super().closeEvent(event)

    def filtered_rows(self, rows):
        p = self.context
        filtered = list(rows or [])
        if p.get("players") is not None:
            filtered = [row for row in filtered if int(row.get("spots", 0) or 0) >= p["players"]]
        low, high = p.get("from"), p.get("to")
        if low is not None:
            filtered = [row for row in filtered if int(row.get("minutes", 0) or 0) >= low]
        if high is not None:
            filtered = [row for row in filtered if int(row.get("minutes", 0) or 0) <= high]
        return filtered

    def _populate_day_section(self, layout, visible_results):
        ordered = sorted(
            visible_results,
            key=lambda r: str(r.get("site_name") or "").casefold(),
        )
        rendered = 0
        for result in ordered:
            if should_show_empty_course(result):
                rows = self.filtered_rows(result.get('decorated_rows', []))
                layout.addWidget(ResultCard(result, rows, self.open_tee_time))
                rendered += 1
                continue
            if result.get("direct_booking"):
                continue
            rows = self.filtered_rows(result.get("decorated_rows", []))
            if rows or result.get("error") or result.get("calendar_availability"):
                layout.addWidget(ResultCard(result, rows, self.open_tee_time))
                rendered += 1
        if not rendered:
            note = QLabel("No live tee times matched these filters on this day.")
            note.setObjectName("EmptyNote")
            note.setWordWrap(True)
            layout.addWidget(note)
        layout.addStretch()

    def render_multi_results(self, days, source):
        self.clear_results()
        selected = {site.name for site in self.context.get("sites", [])}
        prepared = []
        total_matches = 0
        all_visible_results = []
        for day in days:
            visible = [result for result in day.get("results", []) if result.get("site_name") in selected]
            matches = sum(len(self.filtered_rows(result.get("decorated_rows", []))) for result in visible)
            matched_courses = sum(
                bool(self.filtered_rows(result.get("decorated_rows", [])))
                for result in visible
                if not result.get("direct_booking")
            )
            calendar_options = sum(result.get("calendar_availability") == "available" for result in visible)
            if matches:
                detail = f"{matches} time{'s' if matches != 1 else ''} across {matched_courses} course{'s' if matched_courses != 1 else ''}"
            elif calendar_options:
                detail = f"Bookings shown on {calendar_options} official calendar{'s' if calendar_options != 1 else ''}"
            else:
                detail = "No matching live times"
            prepared.append(
                {
                    **day,
                    "visible": visible,
                    "matches": matches,
                    "detail": detail,
                    "has_options": bool(matches or calendar_options),
                }
            )
            total_matches += matches
            all_visible_results.extend(visible)

        days_with_options = sum(day["has_options"] for day in prepared)
        direct_by_name = {}
        for day in prepared:
            for result in day["visible"]:
                if result.get("direct_booking"):
                    direct_by_name.setdefault(result.get("site_name"), result)

        summary = QFrame()
        summary.setObjectName("Summary")
        line = QGridLayout(summary)
        line.setContentsMargins(15, 11, 15, 11)
        line.setHorizontalSpacing(16)
        line.setVerticalSpacing(7)
        available_calendar_dates = sum(
            any(
                result.get("calendar_availability") == "available"
                for result in day["visible"]
            )
            for day in prepared
        )
        if total_matches:
            headline = (
                f"{total_matches} matching {'time' if total_matches == 1 else 'times'} "
                f"across {len(prepared)} {'day' if len(prepared) == 1 else 'days'}"
            )
        elif available_calendar_dates:
            headline = f"Wembley bookings available across {available_calendar_dates} date{'s' if available_calendar_dates != 1 else ''}"
        else:
            headline = f"0 matching times across {len(prepared)} days"
        label = QLabel(headline)
        label.setObjectName("SummaryValue")
        line.addWidget(label, 0, 0)
        line.addWidget(QLabel(f"{days_with_options} days with availability"), 0, 1)
        line.addWidget(QLabel(f"{len(direct_by_name)} official course links"), 0, 2)
        source_label = QLabel(source)
        source_label.setObjectName("SourceBadge")
        line.addWidget(source_label, 1, 0, 1, 3, alignment=Qt.AlignLeft)
        line.setColumnStretch(2, 1)
        self.results_layout.addWidget(summary)

        self.day_sections = []
        expand_index = next((index for index, day in enumerate(prepared) if day["has_options"]), 0)
        for index, day in enumerate(prepared):
            section = DaySection(
                day["date"],
                day["detail"],
                day.get("source", "Cache"),
                lambda layout, results=day["visible"]: self._populate_day_section(layout, results),
            )
            self.day_sections.append(section)
            self.results_layout.addWidget(section)
            if index == expand_index:
                section.set_expanded(True)

        if direct_by_name:
            direct_wrap = QFrame()
            direct_wrap.setObjectName("DirectWrap")
            direct_layout = QVBoxLayout(direct_wrap)
            direct_layout.setContentsMargins(16, 14, 16, 16)
            direct_layout.setSpacing(10)
            direct_title = QLabel("Official booking links")
            direct_title.setObjectName("ResultTitle")
            direct_subtitle = QLabel(
                "These courses open their official booking or visitor page, so each link is shown once for the whole date range."
            )
            direct_subtitle.setObjectName("Muted")
            direct_subtitle.setWordWrap(True)
            direct_layout.addWidget(direct_title)
            direct_layout.addWidget(direct_subtitle)
            direct_cards = [
                DirectCourseCard(direct_by_name[name])
                for name in sorted(direct_by_name, key=lambda value: str(value).casefold())
            ]
            direct_layout.addWidget(ResponsiveCardGrid(direct_cards, min_cell_width=280, max_columns=3))
            self.results_layout.addWidget(direct_wrap)

        self.results_layout.addStretch()
        self.last_results = all_visible_results
        if total_matches:
            self.status.setText(
                f"{total_matches} matching tee {'time' if total_matches == 1 else 'times'} "
                f"across {len(prepared)} {'day' if len(prepared) == 1 else 'days'}"
            )
        elif available_calendar_dates:
            self.status.setText(
                f"Wembley has bookings available on {available_calendar_dates} selected "
                f"date{'s' if available_calendar_dates != 1 else ''}"
            )
        else:
            self.status.setText(f"0 matching tee times across {len(prepared)} days")
        self._scroll_timer.start(0)

    def render_results(self, results, source):
        self.clear_results()
        selected = {site.name for site in self.context.get("sites", [])}
        visible_results = [r for r in results if r.get("site_name") in selected]
        matches = sum(len(self.filtered_rows(r.get("decorated_rows", []))) for r in visible_results)
        live_count = sum(1 for r in visible_results if not r.get("error") and not r.get("direct_booking"))
        direct_count = sum(1 for r in visible_results if r.get("direct_booking"))
        no_match_count = sum(1 for r in visible_results if not r.get("direct_booking") and not r.get("error") and not r.get("calendar_availability") and not self.filtered_rows(r.get("decorated_rows", [])))
        summary = QFrame()
        summary.setObjectName("Summary")
        line = QGridLayout(summary)
        line.setContentsMargins(15, 11, 15, 11)
        line.setHorizontalSpacing(16)
        line.setVerticalSpacing(7)
        available_calendar_count = sum(
            r.get("calendar_availability") == "available" for r in visible_results
        )
        if matches:
            headline = f"{matches} matching {'time' if matches == 1 else 'times'}"
        elif available_calendar_count:
            headline = "Wembley bookings available"
        else:
            headline = "0 matching times"
        label = QLabel(headline)
        label.setObjectName("SummaryValue")
        line.addWidget(label, 0, 0)
        line.addWidget(QLabel(f"{live_count} availability feeds"), 0, 1)
        line.addWidget(QLabel(f"{direct_count} official course links"), 0, 2)
        if no_match_count:
            line.addWidget(QLabel(f"{no_match_count} courses with no matching times"), 0, 3)
        source_label = QLabel(source)
        source_label.setObjectName("SourceBadge")
        line.addWidget(source_label, 1, 0, 1, 4, alignment=Qt.AlignLeft)
        line.setColumnStretch(3, 1)
        self.results_layout.addWidget(summary)

        ordered = sorted(
            visible_results,
            key=lambda r: str(r.get("site_name") or "").casefold(),
        )
        direct_results = []
        rendered_live = 0
        for result in ordered:
            if should_show_empty_course(result):
                rows = self.filtered_rows(result.get('decorated_rows', []))
                self.results_layout.addWidget(
                    ResultCard(result, rows, self.open_tee_time)
                )
                rendered_live += 1
                continue
            rows = self.filtered_rows(result.get("decorated_rows", []))
            if result.get("direct_booking"):
                direct_results.append(result)
            elif rows or result.get("error") or result.get("calendar_availability"):
                self.results_layout.addWidget(ResultCard(result, rows, self.open_tee_time))
                rendered_live += 1

        if matches == 0 and rendered_live == 0:
            self.render_empty("No live tee times matched these filters. Try Any time or Any players, or use Refresh Live. Official course links remain available below.", clear=False)

        if direct_results:
            direct_wrap = QFrame()
            direct_wrap.setObjectName("DirectWrap")
            direct_layout = QVBoxLayout(direct_wrap)
            direct_layout.setContentsMargins(16, 14, 16, 16)
            direct_layout.setSpacing(10)
            direct_title = QLabel("More Perth courses")
            direct_title.setObjectName("ResultTitle")
            direct_subtitle = QLabel("Official booking pages and visitor information for public-access courses.")
            direct_subtitle.setObjectName("Muted")
            direct_layout.addWidget(direct_title)
            direct_layout.addWidget(direct_subtitle)
            direct_cards = [
                DirectCourseCard(result)
                for result in sorted(direct_results, key=lambda value: str(value.get("site_name") or "").casefold())
            ]
            direct_layout.addWidget(ResponsiveCardGrid(direct_cards, min_cell_width=280, max_columns=3))
            self.results_layout.addWidget(direct_wrap)
        if not ordered:
            self.render_empty("No results were returned for the selected courses.", clear=False)
        self.results_layout.addStretch()
        self.last_results = visible_results
        if matches:
            matched_course_count = max(0, live_count - no_match_count)
            self.status.setText(
                f"{matches} matching tee {'time' if matches == 1 else 'times'} across "
                f"{matched_course_count} {'course' if matched_course_count == 1 else 'courses'}"
            )
        elif available_calendar_count:
            self.status.setText(
                "Wembley has booking availability - open it to view exact times"
            )
        else:
            self.status.setText(f"0 matching tee times across {max(0, live_count - no_match_count)} courses")
        self._scroll_timer.start(0)

    def clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                # Remove the old card from painting immediately. deleteLater()
                # alone can leave stale tee-time pixels visible until Qt gets a
                # deferred-delete event, even though the replacement data has
                # already been filtered correctly.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.results_body.update()
        self.results_scroll.viewport().update()

    def render_empty(self, message="Choose a date, round and courses to begin.", clear=True):
        if clear:
            self.clear_results()
        frame = QFrame()
        frame.setObjectName("EmptyState")
        box = QVBoxLayout(frame)
        box.setContentsMargins(40, 60, 40, 60)
        title = QLabel("Find a round that fits your day")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        note = QLabel(message)
        note.setObjectName("Muted")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        box.addWidget(title)
        box.addWidget(note)
        self.results_layout.addWidget(frame)
        if clear:
            self.results_layout.addStretch()

    def styles(self):
        p = PALETTE
        return f"""
        QWidget#Root {{ background: {p['bg']}; color: {p['text']}; font-family: 'Segoe UI'; font-size: 13px; }}
        QLabel {{ color: {p['text']}; }}
        QFrame#Hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #151515,stop:0.7 #21180A,stop:1 #3A2708); border:1px solid {p['line']}; border-radius:18px; }}
        QLabel#Logo {{ font-size:30px; font-weight:900; letter-spacing:1px; }}
        QLabel#PerthBadge {{ color:#090909; background:{p['gold']}; padding:5px 9px; border-radius:7px; font-weight:900; }}
        QLabel#Tagline, QLabel#Muted {{ color:{p['muted']}; }}
        QLabel#StatusBadge, QLabel#SourceBadge {{ color:{p['mint']}; background:#2A1C08; border:1px solid #704A0A; border-radius:11px; padding:7px 11px; font-weight:800; }}
        QFrame#SearchCard, QFrame#Panel {{ background:{p['surface']}; border:1px solid {p['line']}; border-radius:16px; }}
        QLabel#PanelTitle {{ font-size:20px; font-weight:850; }}
        QLabel#FieldLabel {{ color:{p['faint']}; font-size:10px; font-weight:900; letter-spacing:1px; }}
        QDateEdit#Input, QComboBox#Input, QLineEdit#CourseSearch {{ background:{p['surface2']}; color:{p['text']}; border:1px solid {p['line']}; border-radius:9px; min-height:38px; padding:0 10px; }}
        QPushButton#DatePickerButton {{ background:{p['surface2']}; color:{p['text']}; border:1px solid {p['line']}; border-radius:9px; min-height:38px; padding:0 13px; text-align:left; font-weight:750; }}
        QPushButton#DatePickerButton:hover {{ border-color:{p['gold']}; }}
        QComboBox QAbstractItemView {{ background:{p['surface2']}; color:{p['text']}; selection-background-color:{p['gold']}; selection-color:#111; }}
        QRadioButton#RoundButton {{ background:{p['surface2']}; border:1px solid {p['line']}; border-radius:9px; padding:11px 13px; font-weight:750; }}
        QRadioButton#RoundButton::indicator {{ width:0; height:0; }}
        QRadioButton#RoundButton:checked {{ background:{p['gold']}; color:#090909; border-color:{p['gold']}; }}
        QPushButton {{ cursor:pointer; }}
        QPushButton#PrimaryButton {{ background:{p['gold']}; color:#090909; border:0; border-radius:10px; min-height:40px; padding:0 20px; font-weight:900; }}
        QPushButton#PrimaryButton:hover {{ background:{p['gold2']}; }}
        QPushButton#OutlineButton, QPushButton#QuietButton {{ background:{p['surface2']}; color:{p['text']}; border:1px solid {p['line']}; border-radius:9px; min-height:38px; padding:0 14px; font-weight:750; }}
        QPushButton#OutlineButton:hover, QPushButton#QuietButton:hover {{ border-color:{p['gold']}; }}
        QPushButton#StopButton {{ background:#351713; color:{p['danger']}; border:1px solid #73352C; border-radius:9px; min-height:40px; padding:0 14px; font-weight:850; }}
        QPushButton:disabled {{ color:{p['faint']}; background:#171717; border-color:#303030; }}
        QScrollArea {{ background:transparent; border:0; }}
        QWidget#ResultsBody {{ background:{p['surface']}; }}
        QFrame#CourseRow {{ background:{p['surface2']}; border:1px solid transparent; border-radius:10px; }}
        QFrame#CourseRow:hover {{ border-color:{p['line2']}; background:{p['surface3']}; }}
        QLabel#CourseName {{ font-weight:800; }} QLabel#CourseMeta {{ color:{p['faint']}; font-size:11px; }}
        QLabel#LiveBadge {{ color:{p['mint']}; background:#10281B; border-radius:6px; padding:3px 6px; font-size:9px; font-weight:900; }}
        QLabel#DirectBadge {{ color:{p['gold2']}; background:#2A1C08; border-radius:6px; padding:3px 6px; font-size:9px; font-weight:900; }}
        QProgressBar {{ background:#202020; border:0; border-radius:3px; max-height:6px; }} QProgressBar::chunk {{ background:{p['gold']}; border-radius:3px; }}
        QFrame#Summary {{ background:#1B160D; border:1px solid #5A3D0B; border-radius:12px; }} QLabel#SummaryValue {{ color:{p['gold2']}; font-size:16px; font-weight:850; }}
        QFrame#DaySection {{ background:#141414; border:1px solid {p['line']}; border-radius:12px; }}
        QFrame#DayHeader {{ background:#1B160D; border:0; border-radius:11px; }}
        QPushButton#DayToggle {{ background:transparent; color:{p['text']}; border:0; text-align:left; padding:2px; font-size:15px; font-weight:900; }}
        QPushButton#DayToggle:hover {{ color:{p['gold2']}; }}
        QLabel#DaySource {{ color:{p['muted']}; font-size:11px; padding-left:4px; }}
        QFrame#ResultCard, QFrame#DirectWrap {{ background:{p['surface2']}; border:1px solid {p['line']}; border-radius:14px; }}
        QFrame#WeatherBadge {{ background:#171717; border:1px solid #4A3A1C; border-radius:9px; }}
        QLabel#WeatherTitle {{ color:{p['text']}; font-weight:800; }} QLabel#WeatherDetail {{ color:{p['muted']}; font-size:11px; }}
        QFrame#DirectCourse {{ background:#171717; border:1px solid #353535; border-radius:11px; }} QLabel#DirectTitle {{ font-size:15px; font-weight:850; }}
        QLabel#ResultTitle {{ font-size:19px; font-weight:850; }}
        QFrame#TeeTime {{ background:#171717; border:1px solid #353535; border-radius:10px; }} QLabel#TeeTimeValue {{ color:{p['gold2']}; font-size:17px; font-weight:900; }}
        QPushButton#MiniButton {{ background:{p['gold']}; color:#090909; border:0; border-radius:7px; padding:7px 10px; font-weight:900; }}
        QLabel#Warning {{ color:#F1B0A3; background:#351713; border-radius:8px; padding:10px; }}
        QLabel#DirectNote, QLabel#EmptyNote {{ color:{p['muted']}; background:#171717; border-radius:8px; padding:11px; }}
        QLabel#AvailabilityAvailable {{ color:{p['mint']}; background:#10281B; border:1px solid #24583A; border-radius:8px; padding:11px; }}
        QLabel#AvailabilityNotice {{ color:{p['gold2']}; background:#2A1C08; border:1px solid #704A0A; border-radius:8px; padding:11px; }}
        QFrame#EmptyState {{ background:{p['surface2']}; border:1px dashed {p['line2']}; border-radius:14px; }} QLabel#EmptyTitle {{ font-size:24px; font-weight:850; }}
        QScrollBar:vertical {{ background:transparent; width:10px; }} QScrollBar::handle:vertical {{ background:#4A4A4A; border-radius:5px; min-height:40px; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QSplitter::handle {{ background:{p['bg']}; width:8px; }}
        QFrame#MultiDatePopup {{ background:#101010; color:{p['text']}; border:1px solid #4A3A1C; border-radius:12px; }}
        QLabel#CalendarTitle {{ color:#FFFFFF; font-size:21px; font-weight:850; }}
        QLabel#CalendarHelp {{ color:{p['muted']}; font-size:13px; }}
        QLabel#CalendarToday {{ color:{p['gold2']}; background:#2A1C08; border:1px solid #704A0A; border-radius:7px; padding:7px 10px; font-size:11px; font-weight:900; }}
        QLabel#CalendarMonth {{ color:#FFFFFF; font-size:14px; font-weight:900; }}
        QLabel#CalendarCount {{ color:{p['gold2']}; font-weight:800; }}
        QLabel#CalendarSummary {{ color:{p['muted']}; background:#171717; border:0; border-radius:7px; padding:8px 10px; font-size:11px; }}
        QPushButton#CalendarPrimary {{ background:{p['gold']}; color:#090909; border:0; border-radius:8px; min-height:38px; padding:0 16px; font-weight:900; }}
        QPushButton#CalendarQuiet {{ background:#202020; color:#FFFFFF; border:1px solid #444; border-radius:8px; min-height:38px; padding:0 14px; font-weight:800; }}
        QPushButton#CalendarNav {{ background:#202020; color:#FFFFFF; border:1px solid #303030; border-radius:7px; min-width:36px; min-height:32px; font-size:16px; font-weight:900; }}
        QPushButton#CalendarNav:hover {{ border-color:{p['gold']}; color:{p['gold2']}; }}
        QPushButton#CalendarNav:disabled {{ color:#555555; background:#171717; border-color:#242424; }}
        QCalendarWidget QWidget {{ alternate-background-color:#171717; background:#171717; color:#F6F6F6; }}
        QCalendarWidget QToolButton {{ color:#FFFFFF; background:#202020; border:0; min-height:34px; font-weight:800; }}
        QCalendarWidget QAbstractItemView {{ selection-background-color:{p['gold']}; selection-color:#090909; outline:0; }}
        """


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Golf Hub Perth")
    app.setWindowIcon(QIcon(str(ASSET_DIR / "golfhub_icon.svg")))
    app.setFont(QFont("Segoe UI", 10))
    window = GolfHub()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

