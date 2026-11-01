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
