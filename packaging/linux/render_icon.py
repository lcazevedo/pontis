# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the Pontis SVG icon into a 256x256 PNG for AppImage/desktop packaging."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> int:
    """Render ``io.github.lcazevedo.Pontis.svg`` to PNG."""
    here = Path(__file__).resolve().parent
    svg_path = here / "io.github.lcazevedo.Pontis.svg"
    png_path = here / "io.github.lcazevedo.Pontis.png"

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        print(f"Invalid SVG icon: {svg_path}", file=sys.stderr)
        return 1

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    if not image.save(str(png_path), "PNG"):
        print(f"Failed to save PNG icon: {png_path}", file=sys.stderr)
        return 1

    print(f"Rendered {png_path} ({png_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
