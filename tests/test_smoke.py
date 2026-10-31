# SPDX-License-Identifier: GPL-3.0-or-later
"""Smoke tests for the project skeleton."""

from pytestqt.qtbot import QtBot

import pontis
from pontis.app import create_window


def test_version_is_defined() -> None:
    assert pontis.__version__


def test_empty_window_opens(qtbot: QtBot) -> None:
    window = create_window()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
    assert window.windowTitle() == "Pontis"
