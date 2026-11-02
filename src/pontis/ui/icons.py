# SPDX-License-Identifier: GPL-3.0-or-later
"""Icon helpers with graceful vector fallbacks for headless or bare environments."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

_ICON_CACHE: dict[str, QIcon] = {}


def _create_fallback_icon(name: str) -> QIcon:
    """Render a clean 24x24 vector icon when the system theme lacks one."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if name in ("list-add", "add"):
        pen = QPen(QColor(46, 125, 50), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(12, 5, 12, 19)
        painter.drawLine(5, 12, 19, 12)
    elif name in ("edit-delete", "trash"):
        pen = QPen(QColor(198, 40, 40), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawRect(7, 8, 10, 11)
        painter.drawLine(5, 8, 19, 8)
        painter.drawLine(9, 5, 15, 5)
        painter.drawLine(10, 11, 10, 16)
        painter.drawLine(14, 11, 14, 16)
    elif name in ("view-refresh", "refresh"):
        pen = QPen(QColor(25, 118, 210), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(4, 4, 16, 16, 45 * 16, 270 * 16)
        # Arrow tip
        painter.drawLine(16, 4, 20, 7)
        painter.drawLine(15, 10, 20, 7)
    elif name in ("weather-clear", "light-mode"):
        painter.setPen(QPen(QColor(245, 124, 0), 2.0))
        painter.setBrush(QColor(255, 183, 77))
        painter.drawEllipse(7, 7, 10, 10)
    elif name in ("weather-clear-night", "dark-mode"):
        painter.setPen(QPen(QColor(126, 87, 194), 2.0))
        painter.setBrush(QColor(149, 117, 205))
        painter.drawEllipse(6, 6, 12, 12)
    elif name in ("computer", "system"):
        painter.setPen(QPen(QColor(100, 116, 139), 2.0))
        painter.drawRect(5, 5, 14, 10)
        painter.drawLine(9, 18, 15, 18)
        painter.drawLine(12, 15, 12, 18)
    elif name == "status_success":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(46, 125, 50))
        painter.drawEllipse(6, 6, 12, 12)
    elif name == "status_error":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(198, 40, 40))
        painter.drawEllipse(6, 6, 12, 12)
    elif name == "status_running":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(25, 118, 210))
        painter.drawEllipse(6, 6, 12, 12)
    elif name in ("document-edit", "edit"):
        pen = QPen(QColor(2, 136, 209), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(5, 19, 9, 19)
        painter.drawLine(7, 17, 16, 8)
        painter.drawLine(14, 6, 18, 10)
    elif name in ("folder", "folder-open"):
        painter.setPen(QPen(QColor(217, 119, 6), 1.5))
        painter.setBrush(QColor(245, 158, 11))
        painter.drawRect(4, 8, 16, 11)
        painter.drawRect(4, 6, 8, 3)
    elif name in ("folder-remote", "network-server"):
        painter.setPen(QPen(QColor(14, 116, 144), 1.5))
        painter.setBrush(QColor(6, 182, 212))
        painter.drawRect(4, 9, 16, 10)
        painter.drawLine(12, 4, 12, 8)
        painter.drawEllipse(10, 2, 4, 4)
    elif name in ("go-up", "up"):
        pen = QPen(QColor(71, 85, 105), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(12, 6, 12, 18)
        painter.drawLine(7, 11, 12, 6)
        painter.drawLine(17, 11, 12, 6)
    elif name in ("folder-new", "folder-add"):
        painter.setPen(QPen(QColor(217, 119, 6), 1.5))
        painter.setBrush(QColor(245, 158, 11))
        painter.drawRect(4, 8, 12, 11)
        painter.drawRect(4, 6, 7, 3)
        pen_plus = QPen(QColor(46, 125, 50), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_plus)
        painter.drawLine(18, 14, 18, 20)
        painter.drawLine(15, 17, 21, 17)
    elif name in ("preferences-other", "configure", "settings"):
        pen = QPen(QColor(100, 116, 139), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(7, 7, 10, 10)
        # Sliders / notches
        painter.drawLine(12, 3, 12, 6)
        painter.drawLine(12, 18, 12, 21)
        painter.drawLine(3, 12, 6, 12)
        painter.drawLine(18, 12, 21, 12)
    elif name in ("edit-copy", "copy"):
        pen = QPen(QColor(71, 85, 105), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawRect(8, 8, 11, 12)
        painter.drawLine(5, 16, 5, 5)
        painter.drawLine(5, 5, 15, 5)
    elif name == "status_cancelled":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(239, 108, 0))
        painter.drawEllipse(6, 6, 12, 12)
    elif name == "status_never_run":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(158, 158, 158))
        painter.drawEllipse(7, 7, 10, 10)
    else:
        # Generic dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(120, 120, 120))
        painter.drawEllipse(7, 7, 10, 10)

    painter.end()
    return QIcon(pixmap)


def get_icon(name: str) -> QIcon:
    """Return a themed icon with an automatic fallback."""
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]

    icon = QIcon.fromTheme(name)
    if icon.isNull():
        icon = _create_fallback_icon(name)

    _ICON_CACHE[name] = icon
    return icon
