# SPDX-License-Identifier: GPL-3.0-or-later
"""Preferences dialog for language, visual theme, rclone location, and updates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import set_language, tr
from pontis.infra.rclone import format_version, locate_rclone
from pontis.infra.settings import (
    AppSettings,
    SettingsManager,
    get_settings_manager,
)
from pontis.services.update_service import UpdateCheckWorker, UpdateInfo
from pontis.ui.icons import get_icon
from pontis.ui.theme import ThemeMode, apply_theme
from pontis.ui.update_dialog import UpdateDialog

if TYPE_CHECKING:
    pass


class PreferencesDialog(QDialog):
    """Preferences dialog allowing runtime customization of Pontis."""

    settings_applied = Signal(object)  # Emits AppSettings

    def __init__(
        self,
        parent: QWidget | None = None,
        settings_manager: SettingsManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = settings_manager or get_settings_manager()
        self._settings: AppSettings = self._manager.load()
        self._update_worker: UpdateCheckWorker | None = None

        self.setWindowTitle(tr("ui.dialog.preferences.title"))
        self.setMinimumSize(560, 440)
        self.setWindowIcon(get_icon("preferences-system"))
        self._init_ui()
        self._load_values()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        self._tabs = QTabWidget(self)
        self._tabs.setAccessibleName(tr("ui.dialog.preferences.title"))

        self._tab_general = QWidget()
        self._setup_general_tab(self._tab_general)
        self._tabs.addTab(self._tab_general, tr("ui.dialog.preferences.tab_general"))

        self._tab_rclone = QWidget()
        self._setup_rclone_tab(self._tab_rclone)
        self._tabs.addTab(self._tab_rclone, tr("ui.dialog.preferences.tab_rclone"))

        self._tab_updates = QWidget()
        self._setup_updates_tab(self._tab_updates)
        self._tabs.addTab(self._tab_updates, tr("ui.dialog.preferences.tab_updates"))

        main_layout.addWidget(self._tabs)

        # Bottom buttons: Save, Cancel, Apply
        button_box = QDialogButtonBox(self)
        self._btn_save = button_box.addButton(
            tr("ui.dialog.preferences.save"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._btn_cancel = button_box.addButton(
            tr("ui.dialog.preferences.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._btn_apply = button_box.addButton(
            tr("ui.dialog.preferences.apply"), QDialogButtonBox.ButtonRole.ApplyRole
        )

        self._btn_save.setDefault(True)
        self._btn_save.setIcon(get_icon("document-save"))
        self._btn_cancel.setIcon(get_icon("process-stop"))
        self._btn_apply.setIcon(get_icon("emblem-default"))

        self._btn_save.clicked.connect(self._on_save)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_apply.clicked.connect(self._on_apply)

        main_layout.addWidget(button_box)

    def _setup_general_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        # Language group
        lang_group = QGroupBox(tr("ui.dialog.preferences.group_language"), tab)
        lang_layout = QVBoxLayout(lang_group)

        lbl_lang = QLabel(tr("ui.dialog.preferences.language_label"), lang_group)
        self._combo_language = QComboBox(lang_group)
        self._combo_language.addItem(tr("ui.dialog.preferences.lang_system"), "system")
        self._combo_language.addItem(tr("ui.dialog.preferences.lang_en"), "en")
        self._combo_language.addItem(tr("ui.dialog.preferences.lang_pt_br"), "pt_BR")
        self._combo_language.setAccessibleName(tr("ui.dialog.preferences.language_label"))

        lang_layout.addWidget(lbl_lang)
        lang_layout.addWidget(self._combo_language)
        layout.addWidget(lang_group)

        # Theme group
        theme_group = QGroupBox(tr("ui.dialog.preferences.group_theme"), tab)
        theme_layout = QVBoxLayout(theme_group)

        lbl_theme = QLabel(tr("ui.dialog.preferences.theme_label"), theme_group)
        self._combo_theme = QComboBox(theme_group)
        self._combo_theme.addItem(tr("ui.actions.theme.system"), "system")
        self._combo_theme.addItem(tr("ui.actions.theme.light"), "light")
        self._combo_theme.addItem(tr("ui.actions.theme.dark"), "dark")
        self._combo_theme.setAccessibleName(tr("ui.dialog.preferences.theme_label"))

        theme_layout.addWidget(lbl_theme)
        theme_layout.addWidget(self._combo_theme)

        hint_label = QLabel(tr("ui.dialog.preferences.accessibility_hint"), theme_group)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        theme_layout.addWidget(hint_label)

        layout.addWidget(theme_group)
        layout.addStretch()

    def _setup_rclone_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        rclone_group = QGroupBox(tr("ui.dialog.preferences.group_rclone"), tab)
        rclone_layout = QVBoxLayout(rclone_group)
        rclone_layout.setSpacing(10)

        lbl_rclone = QLabel(tr("ui.dialog.preferences.rclone_label"), rclone_group)
        lbl_rclone.setWordWrap(True)
        rclone_layout.addWidget(lbl_rclone)

        path_row = QHBoxLayout()
        self._edit_rclone = QLineEdit(rclone_group)
        self._edit_rclone.setPlaceholderText("/usr/bin/rclone")
        self._edit_rclone.setAccessibleName(tr("ui.dialog.preferences.rclone_label"))
        path_row.addWidget(self._edit_rclone, 1)

        self._btn_browse_rclone = QPushButton(
            tr("ui.dialog.preferences.rclone_browse"), rclone_group
        )
        self._btn_browse_rclone.setIcon(get_icon("document-open"))
        self._btn_browse_rclone.clicked.connect(self._on_browse_rclone)
        path_row.addWidget(self._btn_browse_rclone)

        self._btn_auto_rclone = QPushButton(
            tr("ui.dialog.preferences.rclone_autodetect"), rclone_group
        )
        self._btn_auto_rclone.setIcon(get_icon("view-refresh"))
        self._btn_auto_rclone.clicked.connect(self._on_autodetect_rclone)
        path_row.addWidget(self._btn_auto_rclone)

        rclone_layout.addLayout(path_row)

        test_row = QHBoxLayout()
        self._btn_test_rclone = QPushButton(tr("ui.dialog.preferences.rclone_test"), rclone_group)
        self._btn_test_rclone.setIcon(get_icon("system-run"))
        self._btn_test_rclone.clicked.connect(self._on_test_rclone)
        test_row.addWidget(self._btn_test_rclone)

        self._lbl_rclone_status = QLabel(rclone_group)
        self._lbl_rclone_status.setWordWrap(True)
        test_row.addWidget(self._lbl_rclone_status, 1)

        rclone_layout.addLayout(test_row)
        layout.addWidget(rclone_group)
        layout.addStretch()

    def _setup_updates_tab(self, tab: QWidget) -> None:
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        updates_group = QGroupBox(tr("ui.dialog.preferences.group_updates"), tab)
        upd_layout = QVBoxLayout(updates_group)
        upd_layout.setSpacing(10)

        self._chk_check_startup = QCheckBox(
            tr("ui.dialog.preferences.check_startup"), updates_group
        )
        upd_layout.addWidget(self._chk_check_startup)

        btn_row = QHBoxLayout()
        self._btn_check_now = QPushButton(tr("ui.dialog.preferences.check_now"), updates_group)
        self._btn_check_now.setIcon(get_icon("view-refresh"))
        self._btn_check_now.clicked.connect(self._on_check_updates_now)
        btn_row.addWidget(self._btn_check_now)

        self._lbl_update_status = QLabel(updates_group)
        btn_row.addWidget(self._lbl_update_status, 1)
        upd_layout.addLayout(btn_row)

        self._lbl_last_check = QLabel(updates_group)
        self._lbl_last_check.setStyleSheet("color: #64748b; font-size: 9pt;")
        upd_layout.addWidget(self._lbl_last_check)

        layout.addWidget(updates_group)
        layout.addStretch()

    def _load_values(self) -> None:
        """Populate widgets with current AppSettings."""
        # Language
        lang_idx = self._combo_language.findData(self._settings.language)
        if lang_idx >= 0:
            self._combo_language.setCurrentIndex(lang_idx)
        else:
            self._combo_language.setCurrentIndex(0)

        # Theme
        theme_idx = self._combo_theme.findData(self._settings.theme)
        if theme_idx >= 0:
            self._combo_theme.setCurrentIndex(theme_idx)
        else:
            self._combo_theme.setCurrentIndex(0)

        # Rclone
        self._edit_rclone.setText(self._settings.rclone_path)
        self._on_test_rclone()

        # Updates
        self._chk_check_startup.setChecked(self._settings.check_updates_on_startup)
        last_check_str = self._settings.last_update_check or tr(
            "ui.dialog.preferences.never_checked"
        )
        self._lbl_last_check.setText(tr("ui.dialog.preferences.last_check", time=last_check_str))

    def _on_browse_rclone(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ui.dialog.preferences.rclone_browse"),
            self._edit_rclone.text() or "/usr/bin",
        )
        if path:
            self._edit_rclone.setText(path)
            self._on_test_rclone()

    def _on_autodetect_rclone(self) -> None:
        self._edit_rclone.setText("")
        self._on_test_rclone()

    def _on_test_rclone(self) -> None:
        custom_path = self._edit_rclone.text().strip() or None
        try:
            info = locate_rclone(custom_path)
            self._lbl_rclone_status.setText(
                tr(
                    "ui.dialog.preferences.rclone_status_valid",
                    version=format_version(info.version),
                    source=info.source,
                    path=str(info.path),
                )
            )
            self._lbl_rclone_status.setStyleSheet("color: #16a34a; font-weight: 500;")
        except Exception as exc:
            self._lbl_rclone_status.setText(
                tr("ui.dialog.preferences.rclone_status_invalid", error=str(exc))
            )
            self._lbl_rclone_status.setStyleSheet("color: #dc2626; font-weight: 500;")

    def _on_check_updates_now(self) -> None:
        self._btn_check_now.setEnabled(False)
        self._lbl_update_status.setText(tr("ui.dialog.preferences.checking"))

        worker = UpdateCheckWorker()
        self._update_worker = worker
        worker.finished_success.connect(self._on_update_check_success)
        worker.finished_error.connect(self._on_update_check_error)
        worker.start()

    def _on_update_check_success(self, info: UpdateInfo) -> None:
        self._btn_check_now.setEnabled(True)
        self._lbl_update_status.setText("")

        # Record check timestamp
        now_str = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self._settings.last_update_check = now_str
        self._lbl_last_check.setText(tr("ui.dialog.preferences.last_check", time=now_str))
        self._manager.save(self._settings)

        dlg = UpdateDialog(info, parent=self)
        dlg.exec()
        if dlg.ignore_requested and info.has_update:
            self._settings.ignored_update_version = info.latest_version
            self._manager.save(self._settings)

    def _on_update_check_error(self, message: str) -> None:
        self._btn_check_now.setEnabled(True)
        self._lbl_update_status.setText("")
        QMessageBox.warning(
            self,
            tr("ui.dialog.preferences.tab_updates"),
            f"{tr('ui.dialog.preferences.checking')}\n{message}",
        )

    def apply_settings(self) -> AppSettings:
        """Collect widget inputs, persist, apply live runtime settings and notify."""
        selected_lang = str(self._combo_language.currentData() or "system")
        selected_theme = str(self._combo_theme.currentData() or "system")
        rclone_path = self._edit_rclone.text().strip()
        check_startup = self._chk_check_startup.isChecked()

        self._settings.language = selected_lang
        self._settings.theme = selected_theme
        self._settings.rclone_path = rclone_path
        self._settings.check_updates_on_startup = check_startup

        self._manager.save(self._settings)

        # Apply language live (including resetting to "system")
        set_language(selected_lang)

        # Apply theme live
        apply_theme(self, ThemeMode(selected_theme))

        self.settings_applied.emit(self._settings)
        return self._settings

    def _on_apply(self) -> None:
        self.apply_settings()

    def _on_save(self) -> None:
        self.apply_settings()
        self.accept()
