# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window for Pontis: displays sync profiles, action bar, and empty states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHeaderView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QWidget,
)

from pontis.domain.models import RunResult, RunStatus, SyncDirection, SyncProfile
from pontis.i18n import register_language_listener, tr, unregister_language_listener
from pontis.infra.database import connect
from pontis.infra.keyring_store import KEY_RCLONE_CONFIG_PASS, KeyringStore
from pontis.infra.paths import config_dir, default_db_path
from pontis.infra.rclone import locate_rclone
from pontis.infra.rclone_adapter import RcloneAdapter
from pontis.infra.repositories import RunRepository
from pontis.infra.settings import AppSettings, SettingsManager, get_settings_manager
from pontis.links import BUYMEACOFFEE_URL, GITHUB_SPONSORS_URL, KOFI_URL
from pontis.services.import_export_service import ProfileTransfer, ScriptImporter
from pontis.services.profile_service import ProfileService, ProfileSummary
from pontis.services.remote_service import RemoteService
from pontis.services.run_service import RunService
from pontis.services.update_service import UpdateCheckWorker, UpdateInfo
from pontis.ui.about_dialog import AboutDialog
from pontis.ui.advanced_options_dialog import AdvancedOptionsDialog
from pontis.ui.conflict_resolution_dialog import ConflictResolutionDialog
from pontis.ui.dry_run_summary_dialog import DryRunSummaryDialog
from pontis.ui.history_dialog import HistoryDialog
from pontis.ui.icons import get_icon
from pontis.ui.preferences_dialog import PreferencesDialog
from pontis.ui.sync_progress_dialog import SyncProgressDialog
from pontis.ui.theme import ThemeMode, apply_theme
from pontis.ui.update_dialog import UpdateDialog
from pontis.ui.watch_dialog import WatchDialog
from pontis.ui.widgets.empty_state import EmptyStateWidget
from pontis.ui.wizard import ProfileWizard

if TYPE_CHECKING:
    from pathlib import Path


class MainWindow(QMainWindow):
    """Main application window for Pontis."""

    def __init__(
        self,
        service: ProfileService | None = None,
        remote_service: RemoteService | None = None,
        run_service: RunService | None = None,
        db_path: Path | None = None,
        rclone_binary: Path | str | None = None,
        rclone_config: Path | None = None,
        settings_manager: SettingsManager | None = None,
        check_updates_on_startup: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_manager = settings_manager or get_settings_manager()
        self._settings: AppSettings = self._settings_manager.load()
        self._startup_worker: UpdateCheckWorker | None = None
        self._update_worker: UpdateCheckWorker | None = None

        self._service = service if service is not None else ProfileService(db_path=db_path)
        self._rclone_config = rclone_config or (config_dir() / "rclone.conf")
        if rclone_binary is not None:
            self._rclone_binary: Path | str = rclone_binary
        elif self._settings.rclone_path:
            self._rclone_binary = self._settings.rclone_path
        else:
            try:
                self._rclone_binary = locate_rclone().path
            except Exception:
                self._rclone_binary = "rclone"

        if remote_service is not None:
            self._remote_service = remote_service
        else:
            self._remote_service = RemoteService(
                binary=self._rclone_binary, config_path=self._rclone_config
            )

        self._run_conn = None
        if run_service is not None:
            self._run_service = run_service
        else:
            state_root = (db_path.parent if db_path else default_db_path().parent) / "bisync"
            lock_dir = (db_path.parent if db_path else default_db_path().parent) / "locks"
            keyring_store = KeyringStore()
            password = keyring_store.get_password(KEY_RCLONE_CONFIG_PASS)
            env = {"RCLONE_CONFIG_PASS": password} if password else None
            adapter = RcloneAdapter(
                self._rclone_binary,
                state_root,
                config_path=self._rclone_config,
                env=env,
            )
            # Create a dedicated connection for background runs with check_same_thread=False
            self._run_conn = connect(db_path, check_same_thread=False)
            self._run_service = RunService(
                adapter,
                RunRepository(self._run_conn),
                lock_dir=lock_dir,
            )

        self._running_profile_ids: set[int] = set()
        self._summaries: list[ProfileSummary] = []
        try:
            self._current_theme = ThemeMode(self._settings.theme)
        except ValueError:
            self._current_theme = ThemeMode.SYSTEM

        self.setWindowTitle(tr("ui.main.title"))
        self.resize(950, 560)
        self.setWindowIcon(get_icon("sync"))

        self._init_ui()
        self.load_profiles()
        register_language_listener(self.retranslate_ui)

        if check_updates_on_startup:
            QTimer.singleShot(1000, self._check_updates_startup)

    def _init_ui(self) -> None:
        """Construct actions, toolbar, stacked widget, and status bar."""
        self._create_actions()
        self._create_toolbar()
        self._create_menus()
        self._create_central_widget()
        self._create_support_status_button()
        self.statusBar().showMessage(tr("ui.statusbar.ready"))

    def _create_actions(self) -> None:
        """Create QAction instances for toolbar and menus."""
        self._action_sync = QAction(
            get_icon("media-playback-start"), tr("ui.actions.sync_now"), self
        )
        self._action_sync.setToolTip(tr("ui.actions.sync_now.tooltip"))
        self._action_sync.setShortcut(QKeySequence("Ctrl+R"))
        self._action_sync.setEnabled(False)
        self._action_sync.triggered.connect(self._on_sync_now)

        self._action_dry_run = QAction(get_icon("view-refresh"), tr("ui.actions.dry_run"), self)
        self._action_dry_run.setToolTip(tr("ui.actions.dry_run.tooltip"))
        self._action_dry_run.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self._action_dry_run.setEnabled(False)
        self._action_dry_run.triggered.connect(self._on_dry_run)

        self._action_new = QAction(get_icon("list-add"), tr("ui.actions.new"), self)
        self._action_new.setToolTip(tr("ui.actions.new.tooltip"))
        self._action_new.setShortcut(QKeySequence("Ctrl+N"))
        self._action_new.triggered.connect(self._on_new_profile)

        self._action_edit = QAction(get_icon("document-edit"), tr("ui.actions.edit"), self)
        self._action_edit.setToolTip(tr("ui.actions.edit.tooltip"))
        self._action_edit.setShortcut(QKeySequence("Ctrl+E"))
        self._action_edit.setEnabled(False)
        self._action_edit.triggered.connect(self._on_edit_profile)

        self._action_advanced = QAction(
            get_icon("preferences-other"), tr("ui.actions.advanced_options"), self
        )
        self._action_advanced.setToolTip(tr("ui.actions.advanced_options.tooltip"))
        self._action_advanced.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._action_advanced.setEnabled(False)
        self._action_advanced.triggered.connect(self._on_advanced_options)

        self._action_conflicts = QAction(
            get_icon("emblem-important"), tr("ui.actions.conflicts"), self
        )
        self._action_conflicts.setToolTip(tr("ui.actions.conflicts.tooltip"))
        self._action_conflicts.setEnabled(False)
        self._action_conflicts.triggered.connect(self._on_conflicts)

        self._action_history = QAction(
            get_icon("document-open-recent"), tr("ui.actions.history"), self
        )
        self._action_history.setToolTip(tr("ui.actions.history.tooltip"))
        self._action_history.setShortcut(QKeySequence("Ctrl+H"))
        self._action_history.triggered.connect(self._on_history)

        self._action_delete = QAction(get_icon("edit-delete"), tr("ui.actions.delete"), self)
        self._action_delete.setToolTip(tr("ui.actions.delete.tooltip"))
        self._action_delete.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self._action_delete.setEnabled(False)
        self._action_delete.triggered.connect(self._on_delete_profile)

        self._action_refresh = QAction(get_icon("view-refresh"), tr("ui.actions.refresh"), self)
        self._action_refresh.setToolTip(tr("ui.actions.refresh.tooltip"))
        self._action_refresh.setShortcut(QKeySequence("F5"))
        self._action_refresh.triggered.connect(self._on_refresh)

        self._action_watch = QAction(get_icon("system-search"), tr("ui.actions.watch"), self)
        self._action_watch.setToolTip(tr("ui.actions.watch.tooltip"))
        self._action_watch.setShortcut(QKeySequence("Ctrl+W"))
        self._action_watch.setEnabled(False)
        self._action_watch.triggered.connect(self._on_watch_profile)

        self._action_import_profile = QAction(
            get_icon("document-open"), tr("ui.actions.import_profile"), self
        )
        self._action_import_profile.setToolTip(tr("ui.actions.import_profile.tooltip"))
        self._action_import_profile.triggered.connect(self._on_import_profile)

        self._action_export_profile = QAction(
            get_icon("document-save-as"), tr("ui.actions.export_profile"), self
        )
        self._action_export_profile.setToolTip(tr("ui.actions.export_profile.tooltip"))
        self._action_export_profile.setEnabled(False)
        self._action_export_profile.triggered.connect(self._on_export_profile)

        self._action_import_script = QAction(
            get_icon("text-x-script"), tr("ui.actions.import_script"), self
        )
        self._action_import_script.setToolTip(tr("ui.actions.import_script.tooltip"))
        self._action_import_script.triggered.connect(self._on_import_script)

        self._action_preferences = QAction(
            get_icon("preferences-system"), tr("ui.actions.preferences"), self
        )
        self._action_preferences.setToolTip(tr("ui.actions.preferences.tooltip"))
        self._action_preferences.setShortcut(QKeySequence("Ctrl+,"))
        self._action_preferences.triggered.connect(self._on_preferences)

        self._action_check_updates = QAction(
            get_icon("system-software-update"), tr("ui.actions.check_updates"), self
        )
        self._action_check_updates.setToolTip(tr("ui.actions.check_updates.tooltip"))
        self._action_check_updates.triggered.connect(self._on_check_updates)

        self._action_about = QAction(get_icon("help-about"), tr("ui.actions.about"), self)
        self._action_about.setToolTip(tr("ui.actions.about.tooltip"))
        self._action_about.setShortcut(QKeySequence("F1"))
        self._action_about.triggered.connect(self._on_about)

        self._action_support_sponsors = self._make_support_action(
            "ui.support.github_sponsors", GITHUB_SPONSORS_URL
        )
        self._action_support_kofi = self._make_support_action("ui.support.kofi", KOFI_URL)
        self._action_support_bmc = self._make_support_action(
            "ui.support.buymeacoffee", BUYMEACOFFEE_URL
        )

        self._action_quit = QAction(tr("ui.actions.quit"), self)
        self._action_quit.setToolTip(tr("ui.actions.quit.tooltip"))
        self._action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._action_quit.triggered.connect(self.close)

    def _create_toolbar(self) -> None:
        """Create the top action toolbar."""
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        toolbar.addAction(self._action_sync)
        toolbar.addAction(self._action_dry_run)
        toolbar.addAction(self._action_watch)
        toolbar.addSeparator()
        toolbar.addAction(self._action_new)
        toolbar.addAction(self._action_edit)
        toolbar.addAction(self._action_advanced)
        toolbar.addAction(self._action_conflicts)
        toolbar.addAction(self._action_history)
        toolbar.addAction(self._action_delete)
        toolbar.addAction(self._action_refresh)
        toolbar.addSeparator()
        toolbar.addAction(self._action_preferences)
        toolbar.addSeparator()

        # Theme selector button
        self._theme_button = QToolButton(self)
        self._theme_button.setIcon(get_icon("preferences-system"))
        self._theme_button.setText(tr("ui.actions.theme"))
        self._theme_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._theme_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        theme_menu = QMenu(self)
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self._theme_system_action = QAction(
            get_icon("computer"), tr("ui.actions.theme.system"), self, checkable=True
        )
        self._theme_light_action = QAction(
            get_icon("weather-clear"), tr("ui.actions.theme.light"), self, checkable=True
        )
        self._theme_dark_action = QAction(
            get_icon("weather-clear-night"), tr("ui.actions.theme.dark"), self, checkable=True
        )

        self._theme_system_action.setChecked(self._current_theme == ThemeMode.SYSTEM)
        self._theme_light_action.setChecked(self._current_theme == ThemeMode.LIGHT)
        self._theme_dark_action.setChecked(self._current_theme == ThemeMode.DARK)

        theme_group.addAction(self._theme_system_action)
        theme_group.addAction(self._theme_light_action)
        theme_group.addAction(self._theme_dark_action)

        self._theme_system_action.triggered.connect(lambda: self.set_theme(ThemeMode.SYSTEM))
        self._theme_light_action.triggered.connect(lambda: self.set_theme(ThemeMode.LIGHT))
        self._theme_dark_action.triggered.connect(lambda: self.set_theme(ThemeMode.DARK))

        theme_menu.addAction(self._theme_system_action)
        theme_menu.addAction(self._theme_light_action)
        theme_menu.addAction(self._theme_dark_action)
        self._theme_button.setMenu(theme_menu)

        toolbar.addWidget(self._theme_button)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _create_menus(self) -> None:
        """Create the top menu bar."""
        menubar = self.menuBar()

        self._menu_file = menubar.addMenu(tr("ui.menu.file"))
        self._menu_file.addAction(self._action_new)
        self._menu_file.addSeparator()
        self._menu_file.addAction(self._action_import_profile)
        self._menu_file.addAction(self._action_import_script)
        self._menu_file.addAction(self._action_export_profile)
        self._menu_file.addSeparator()
        self._menu_file.addAction(self._action_preferences)
        self._menu_file.addSeparator()
        self._menu_file.addAction(self._action_quit)

        self._menu_edit = menubar.addMenu(tr("ui.menu.edit"))
        self._menu_edit.addAction(self._action_edit)
        self._menu_edit.addAction(self._action_advanced)
        self._menu_edit.addAction(self._action_conflicts)
        self._menu_edit.addSeparator()
        self._menu_edit.addAction(self._action_preferences)

        self._menu_profile = menubar.addMenu(tr("ui.menu.profile"))
        self._menu_profile.addAction(self._action_sync)
        self._menu_profile.addAction(self._action_dry_run)
        self._menu_profile.addAction(self._action_watch)
        self._menu_profile.addSeparator()
        self._menu_profile.addAction(self._action_new)
        self._menu_profile.addAction(self._action_edit)
        self._menu_profile.addAction(self._action_advanced)
        self._menu_profile.addAction(self._action_conflicts)
        self._menu_profile.addAction(self._action_history)
        self._menu_profile.addSeparator()
        self._menu_profile.addAction(self._action_import_profile)
        self._menu_profile.addAction(self._action_import_script)
        self._menu_profile.addAction(self._action_export_profile)
        self._menu_profile.addSeparator()
        self._menu_profile.addAction(self._action_delete)
        self._menu_profile.addAction(self._action_refresh)

        self._menu_view = menubar.addMenu(tr("ui.menu.view"))
        self._theme_submenu = self._menu_view.addMenu(tr("ui.actions.theme"))
        self._theme_submenu.addAction(self._theme_system_action)
        self._theme_submenu.addAction(self._theme_light_action)
        self._theme_submenu.addAction(self._theme_dark_action)

        self._menu_help = menubar.addMenu(tr("ui.menu.help"))
        self._menu_help.addAction(self._action_check_updates)
        self._support_menu = self._menu_help.addMenu(
            get_icon("emblem-favorite"), tr("ui.menu.support")
        )
        self._support_menu.addAction(self._action_support_sponsors)
        self._support_menu.addAction(self._action_support_kofi)
        self._support_menu.addAction(self._action_support_bmc)
        self._menu_help.addSeparator()
        self._menu_help.addAction(self._action_about)

    def _create_central_widget(self) -> None:
        """Create the stacked widget holding the table and empty state."""
        self._stack = QStackedWidget(self)

        # 0: Profiles Table
        self._table = QTableWidget(self)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            [
                tr("ui.table.header.name"),
                tr("ui.table.header.source"),
                tr("ui.table.header.direction"),
                tr("ui.table.header.destination"),
                tr("ui.table.header.last_run"),
                tr("ui.table.header.status"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setAccessibleName(tr("ui.table.header.name"))
        self._table.setAccessibleDescription(tr("ui.main.title"))

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)

        # 1: Empty state
        self._empty_state = EmptyStateWidget(self)
        self._empty_state.create_requested.connect(self._on_new_profile)

        self._stack.addWidget(self._table)  # index 0
        self._stack.addWidget(self._empty_state)  # index 1

        self.setCentralWidget(self._stack)

    def _make_support_action(self, label_key: str, url: str) -> QAction:
        """Create a QAction that opens a voluntary support page."""
        action = QAction(tr(label_key), self)
        action.setToolTip(url)
        action.triggered.connect(
            lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target))
        )
        return action

    def _create_support_status_button(self) -> None:
        """Add a discreet, non-intrusive voluntary support menu button to the status bar."""
        self._support_button = QToolButton(self)
        self._support_button.setObjectName("supportStatusButton")
        self._support_button.setAutoRaise(True)
        self._support_button.setIcon(get_icon("emblem-favorite"))
        self._support_button.setText(tr("ui.actions.support"))
        self._support_button.setToolTip(tr("ui.actions.support.tooltip"))
        self._support_button.setAccessibleName(tr("ui.actions.support"))
        self._support_button.setAccessibleDescription(tr("ui.actions.support.tooltip"))
        self._support_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._support_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._support_button.setMenu(self._support_menu)
        self.statusBar().addPermanentWidget(self._support_button)

    def load_profiles(self) -> None:
        """Fetch profiles from SQLite and refresh the view."""
        self._summaries = self._service.list_summaries()

        if not self._summaries:
            self._table.setRowCount(0)
            self._stack.setCurrentIndex(1)
            self._action_delete.setEnabled(False)
            self._action_edit.setEnabled(False)
            self.statusBar().showMessage(tr("ui.statusbar.profiles_count", count=0))
            return

        self._table.setRowCount(len(self._summaries))
        for row, item in enumerate(self._summaries):
            profile = item.profile
            last_run = item.last_run

            # Column 0: Name
            name_widget = QTableWidgetItem(profile.name)
            name_widget.setData(Qt.ItemDataRole.UserRole, profile.id)
            self._table.setItem(row, 0, name_widget)

            # Column 1: Source (Side A)
            self._table.setItem(row, 1, QTableWidgetItem(profile.side_a.to_rclone()))

            # Column 2: Direction symbol
            direction_symbol = {
                SyncDirection.BIDIRECTIONAL: "↔",
                SyncDirection.A_TO_B: "→",
                SyncDirection.B_TO_A: "←",
            }.get(profile.options.direction, "↔")
            dir_item = QTableWidgetItem(direction_symbol)
            dir_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, dir_item)

            # Column 3: Destination (Side B)
            self._table.setItem(row, 3, QTableWidgetItem(profile.side_b.to_rclone()))

            # Column 4: Last Run timestamp
            last_run_str = "—"
            if last_run and last_run.started_at:
                last_run_str = last_run.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            self._table.setItem(row, 4, QTableWidgetItem(last_run_str))

            # Column 5: Status with icon
            if profile.id in self._running_profile_ids:
                status_item = QTableWidgetItem(get_icon("status_running"), tr("ui.status.running"))
            else:
                status_item = self._build_status_item(last_run)
            self._table.setItem(row, 5, status_item)

        self._stack.setCurrentIndex(0)
        self._on_selection_changed()
        self.statusBar().showMessage(tr("ui.statusbar.profiles_count", count=len(self._summaries)))

    def _build_status_item(self, last_run: object) -> QTableWidgetItem:
        """Format the execution status cell with a colored icon."""
        if not isinstance(last_run, RunResult):
            item = QTableWidgetItem(get_icon("status_never_run"), tr("ui.status.never_run"))
            return item

        suffix = tr("ui.status.dry_run_tag") if last_run.dry_run else ""
        if last_run.status == RunStatus.SUCCESS:
            text = tr("ui.status.success") + suffix
            return QTableWidgetItem(get_icon("status_success"), text)
        if last_run.status == RunStatus.ERROR:
            text = tr("ui.status.error") + suffix
            return QTableWidgetItem(get_icon("status_error"), text)
        if last_run.status == RunStatus.RUNNING:
            text = tr("ui.status.running") + suffix
            return QTableWidgetItem(get_icon("status_running"), text)
        if last_run.status == RunStatus.CANCELLED:
            text = tr("ui.status.cancelled") + suffix
            return QTableWidgetItem(get_icon("status_cancelled"), text)

        return QTableWidgetItem(get_icon("status_never_run"), tr("ui.status.never_run"))

    def _selected_summary(self) -> ProfileSummary | None:
        """Return the currently selected ProfileSummary, or None."""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        if 0 <= row < len(self._summaries):
            return self._summaries[row]
        return None

    def _on_selection_changed(self) -> None:
        """Update action availability based on table selection."""
        selected = self._selected_summary()
        has_sel = selected is not None and selected.profile.id is not None
        profile_id = (
            selected.profile.id
            if (selected is not None and selected.profile.id is not None)
            else None
        )
        is_running = (profile_id in self._running_profile_ids) if profile_id is not None else False
        self._action_sync.setEnabled(has_sel and not is_running)
        self._action_dry_run.setEnabled(has_sel and not is_running)
        self._action_watch.setEnabled(has_sel and not is_running)
        self._action_delete.setEnabled(has_sel and not is_running)
        self._action_edit.setEnabled(has_sel and not is_running)
        self._action_advanced.setEnabled(has_sel and not is_running)
        self._action_conflicts.setEnabled(has_sel and not is_running)
        self._action_export_profile.setEnabled(has_sel and not is_running)

    def _on_table_context_menu(self, pos: QPoint) -> None:
        """Show context menu on right-click."""
        menu = QMenu(self)
        if self._selected_summary() is not None:
            menu.addAction(self._action_sync)
            menu.addAction(self._action_dry_run)
            menu.addAction(self._action_watch)
            menu.addSeparator()
            menu.addAction(self._action_edit)
            menu.addAction(self._action_advanced)
            menu.addAction(self._action_conflicts)
            menu.addAction(self._action_history)
            menu.addAction(self._action_export_profile)
            menu.addAction(self._action_delete)
            menu.addSeparator()
        else:
            menu.addAction(self._action_history)
            menu.addSeparator()
        menu.addAction(self._action_new)
        menu.addAction(self._action_import_profile)
        menu.addAction(self._action_import_script)
        menu.addAction(self._action_refresh)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_sync_now(self) -> None:
        """Execute real synchronization or safety dry-run if first time."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return
        profile = summary.profile
        if profile.id in self._running_profile_ids:
            QMessageBox.warning(
                self,
                tr("ui.actions.sync_now"),
                tr("ui.alert.already_running", name=profile.name),
            )
            return

        if self._run_service.needs_first_run_dry_run(profile):
            reply = QMessageBox.information(
                self,
                tr("ui.dialog.first_run.title"),
                tr("ui.dialog.first_run.message", name=profile.name),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return
            self._execute_profile(profile, dry_run=True, is_first_run=True)
            return

        self._execute_profile(profile, dry_run=False)

    def _on_dry_run(self) -> None:
        """Run a simulation (dry-run) for the selected sync profile."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return
        profile = summary.profile
        if profile.id in self._running_profile_ids:
            QMessageBox.warning(
                self,
                tr("ui.actions.dry_run"),
                tr("ui.alert.already_running", name=profile.name),
            )
            return
        self._execute_profile(profile, dry_run=True)

    def _execute_profile(
        self,
        profile: SyncProfile,
        *,
        dry_run: bool,
        is_first_run: bool = False,
        force: bool = False,
        resync: bool = False,
    ) -> None:
        """Launch the sync progress dialog and track execution lifecycle."""
        if profile.id is None:
            return
        self._running_profile_ids.add(profile.id)
        self.load_profiles()
        self._on_selection_changed()

        apply_real_after_dry_run = False
        apply_real_force = False
        apply_resync = False

        dialog = SyncProgressDialog(
            profile,
            self._run_service,
            dry_run=dry_run,
            force=force,
            resync=resync,
            parent=self,
        )

        def _on_apply_requested() -> None:
            nonlocal apply_real_after_dry_run
            apply_real_after_dry_run = True

        def _on_force_requested(is_dry: bool) -> None:
            nonlocal apply_real_after_dry_run, apply_real_force
            if is_dry:
                self._execute_profile(profile, dry_run=True, force=True)
            else:
                apply_real_after_dry_run = True
                apply_real_force = True

        def _on_resync_requested() -> None:
            nonlocal apply_resync
            apply_resync = True

        dialog.apply_real_sync_requested.connect(_on_apply_requested)
        dialog.force_sync_requested.connect(_on_force_requested)
        dialog.resync_requested.connect(_on_resync_requested)
        dialog.exec()

        self._running_profile_ids.discard(profile.id)
        self.load_profiles()
        self._on_selection_changed()

        if apply_resync:
            self._execute_profile(profile, dry_run=False, resync=True)
            return

        if apply_real_after_dry_run:
            self._execute_profile(profile, dry_run=False, force=apply_real_force)
            return

        # If it was a first-run dry run and finished with success, present summary
        if (
            is_first_run
            and dialog.run_result
            and dialog.run_result.status == RunStatus.SUCCESS
            and not apply_real_after_dry_run
        ):
            summary_dialog = DryRunSummaryDialog(profile, dialog.outcome, parent=self)
            if summary_dialog.exec() and summary_dialog.should_apply_sync:
                self._execute_profile(profile, dry_run=False, force=summary_dialog.apply_with_force)

    def _on_history(self) -> None:
        """Open execution history and log viewer dialog."""
        summary = self._selected_summary()
        initial_id = summary.profile.id if (summary and summary.profile.id) else None
        dialog = HistoryDialog(self._service, initial_profile_id=initial_id, parent=self)
        dialog.exec()

    def _on_conflicts(self) -> None:
        """Open conflict resolution dialog for the selected profile."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dialog = ConflictResolutionDialog(
                profile=summary.profile,
                rclone_binary=self._rclone_binary,
                rclone_config=self._rclone_config,
                parent=self,
            )
        finally:
            QApplication.restoreOverrideCursor()

        if dialog.exec() and dialog.should_sync_after:
            self._execute_profile(summary.profile, dry_run=False)

    def _on_advanced_options(self) -> None:
        """Open the advanced options dialog for the selected sync profile."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return
        dialog = AdvancedOptionsDialog(
            profile=summary.profile,
            parent=self,
            rclone_binary=self._rclone_binary,
            rclone_config=self._rclone_config,
        )
        if dialog.exec():
            self._service.update_profile(summary.profile)
            self.statusBar().showMessage(
                tr("ui.statusbar.options_saved", name=summary.profile.name), 4000
            )
            self.load_profiles()

    def _on_new_profile(self) -> None:
        """Open the wizard to create a new sync profile."""
        wizard = ProfileWizard(
            service=self._service,
            remote_service=self._remote_service,
            parent=self,
        )
        if wizard.exec() and wizard.saved_profile is not None:
            self.statusBar().showMessage(
                tr("ui.statusbar.profile_created", name=wizard.saved_profile.name), 4000
            )
            self.load_profiles()

    def _on_edit_profile(self) -> None:
        """Open the wizard to edit the selected sync profile."""
        summary = self._selected_summary()
        if summary is None:
            return
        wizard = ProfileWizard(
            service=self._service,
            remote_service=self._remote_service,
            profile=summary.profile,
            parent=self,
        )
        if wizard.exec() and wizard.saved_profile is not None:
            self.statusBar().showMessage(
                tr("ui.statusbar.profile_updated", name=wizard.saved_profile.name), 4000
            )
            self.load_profiles()

    def _on_table_cell_double_clicked(self, row: int, column: int) -> None:
        """Double clicking a row triggers profile edition."""
        self._on_edit_profile()

    def _on_delete_profile(self) -> None:
        """Prompt confirmation and delete the selected profile from SQLite."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return

        profile = summary.profile
        profile_id = profile.id
        assert profile_id is not None

        reply = QMessageBox.question(
            self,
            tr("ui.dialog.delete.title"),
            tr("ui.dialog.delete.confirm", name=profile.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._service.delete_profile(profile_id)
            self.statusBar().showMessage(
                tr("ui.statusbar.profile_deleted", name=profile.name), 4000
            )
            self.load_profiles()

    def _on_refresh(self) -> None:
        """Reload profiles from SQLite."""
        self.load_profiles()

    def set_theme(self, mode: ThemeMode) -> None:
        """Switch between Light, Dark, and System appearance."""
        self._current_theme = mode
        apply_theme(self, mode)
        self._settings.theme = str(mode.value)
        self._settings_manager.save(self._settings)

    def _on_preferences(self) -> None:
        """Open Preferences dialog."""
        dlg = PreferencesDialog(parent=self, settings_manager=self._settings_manager)
        dlg.settings_applied.connect(self._on_settings_applied)
        if dlg.exec():
            self._on_settings_applied(dlg.apply_settings())

    def _on_settings_applied(self, settings: AppSettings) -> None:
        """React to applied settings updates."""
        self._settings = settings
        if settings.rclone_path:
            self._rclone_binary = settings.rclone_path
        try:
            theme_mode = ThemeMode(settings.theme)
            self._current_theme = theme_mode
            apply_theme(self, theme_mode)
            self._theme_system_action.setChecked(theme_mode == ThemeMode.SYSTEM)
            self._theme_light_action.setChecked(theme_mode == ThemeMode.LIGHT)
            self._theme_dark_action.setChecked(theme_mode == ThemeMode.DARK)
        except ValueError:
            pass

    def _on_about(self) -> None:
        """Open About dialog."""
        dlg = AboutDialog(rclone_binary=self._rclone_binary, parent=self)
        dlg.exec()

    def _on_check_updates(self) -> None:
        """Trigger an update check and display results."""
        self.statusBar().showMessage(tr("ui.dialog.preferences.checking"))
        worker = UpdateCheckWorker()
        self._update_worker = worker

        def on_success(info: UpdateInfo) -> None:
            self.statusBar().showMessage(tr("ui.statusbar.ready"))
            dlg = UpdateDialog(info, parent=self)
            dlg.exec()
            if dlg.ignore_requested and info.has_update:
                self._settings.ignored_update_version = info.latest_version
                self._settings_manager.save(self._settings)

        def on_error(msg: str) -> None:
            self.statusBar().showMessage(tr("ui.statusbar.ready"))
            QMessageBox.warning(
                self,
                tr("ui.actions.check_updates"),
                f"{tr('ui.dialog.preferences.checking')}\n{msg}",
            )

        worker.finished_success.connect(on_success)
        worker.finished_error.connect(on_error)
        worker.start()

    def _check_updates_startup(self) -> None:
        """Quiet background update check on app launch."""
        if not self._settings.check_updates_on_startup:
            return

        worker = UpdateCheckWorker()
        self._startup_worker = worker

        def on_success(info: UpdateInfo) -> None:
            if info.has_update and info.latest_version != self._settings.ignored_update_version:
                dlg = UpdateDialog(info, parent=self)
                dlg.exec()
                if dlg.ignore_requested:
                    self._settings.ignored_update_version = info.latest_version
                    self._settings_manager.save(self._settings)

        worker.finished_success.connect(on_success)
        worker.start()

    def retranslate_ui(self) -> None:
        """Update all user interface texts dynamically when language changes."""
        self.setWindowTitle(tr("ui.main.title"))

        # Menus
        self._menu_file.setTitle(tr("ui.menu.file"))
        self._menu_edit.setTitle(tr("ui.menu.edit"))
        self._menu_profile.setTitle(tr("ui.menu.profile"))
        self._menu_view.setTitle(tr("ui.menu.view"))
        self._menu_help.setTitle(tr("ui.menu.help"))
        self._theme_submenu.setTitle(tr("ui.actions.theme"))

        # Actions
        self._action_sync.setText(tr("ui.actions.sync_now"))
        self._action_sync.setToolTip(tr("ui.actions.sync_now.tooltip"))
        self._action_dry_run.setText(tr("ui.actions.dry_run"))
        self._action_dry_run.setToolTip(tr("ui.actions.dry_run.tooltip"))
        self._action_watch.setText(tr("ui.actions.watch"))
        self._action_watch.setToolTip(tr("ui.actions.watch.tooltip"))
        self._action_new.setText(tr("ui.actions.new"))
        self._action_new.setToolTip(tr("ui.actions.new.tooltip"))
        self._action_edit.setText(tr("ui.actions.edit"))
        self._action_edit.setToolTip(tr("ui.actions.edit.tooltip"))
        self._action_advanced.setText(tr("ui.actions.advanced_options"))
        self._action_advanced.setToolTip(tr("ui.actions.advanced_options.tooltip"))
        self._action_conflicts.setText(tr("ui.actions.conflicts"))
        self._action_conflicts.setToolTip(tr("ui.actions.conflicts.tooltip"))
        self._action_history.setText(tr("ui.actions.history"))
        self._action_history.setToolTip(tr("ui.actions.history.tooltip"))
        self._action_delete.setText(tr("ui.actions.delete"))
        self._action_delete.setToolTip(tr("ui.actions.delete.tooltip"))
        self._action_refresh.setText(tr("ui.actions.refresh"))
        self._action_refresh.setToolTip(tr("ui.actions.refresh.tooltip"))
        self._action_import_profile.setText(tr("ui.actions.import_profile"))
        self._action_import_profile.setToolTip(tr("ui.actions.import_profile.tooltip"))
        self._action_export_profile.setText(tr("ui.actions.export_profile"))
        self._action_export_profile.setToolTip(tr("ui.actions.export_profile.tooltip"))
        self._action_import_script.setText(tr("ui.actions.import_script"))
        self._action_import_script.setToolTip(tr("ui.actions.import_script.tooltip"))
        self._action_preferences.setText(tr("ui.actions.preferences"))
        self._action_preferences.setToolTip(tr("ui.actions.preferences.tooltip"))
        self._action_check_updates.setText(tr("ui.actions.check_updates"))
        self._action_check_updates.setToolTip(tr("ui.actions.check_updates.tooltip"))
        self._action_about.setText(tr("ui.actions.about"))
        self._action_about.setToolTip(tr("ui.actions.about.tooltip"))
        self._support_menu.setTitle(tr("ui.menu.support"))
        self._action_support_sponsors.setText(tr("ui.support.github_sponsors"))
        self._action_support_kofi.setText(tr("ui.support.kofi"))
        self._action_support_bmc.setText(tr("ui.support.buymeacoffee"))
        self._support_button.setText(tr("ui.actions.support"))
        self._support_button.setToolTip(tr("ui.actions.support.tooltip"))
        self._support_button.setAccessibleName(tr("ui.actions.support"))
        self._support_button.setAccessibleDescription(tr("ui.actions.support.tooltip"))
        self._action_quit.setText(tr("ui.actions.quit"))
        self._action_quit.setToolTip(tr("ui.actions.quit.tooltip"))

        # Theme actions
        self._theme_button.setText(tr("ui.actions.theme"))
        self._theme_system_action.setText(tr("ui.actions.theme.system"))
        self._theme_light_action.setText(tr("ui.actions.theme.light"))
        self._theme_dark_action.setText(tr("ui.actions.theme.dark"))

        # Table headers and accessibility
        self._table.setHorizontalHeaderLabels(
            [
                tr("ui.table.header.name"),
                tr("ui.table.header.source"),
                tr("ui.table.header.direction"),
                tr("ui.table.header.destination"),
                tr("ui.table.header.last_run"),
                tr("ui.table.header.status"),
            ]
        )
        self._table.setAccessibleName(tr("ui.table.header.name"))
        self._table.setAccessibleDescription(tr("ui.main.title"))

        # Empty state & status bar
        self._empty_state.retranslate_ui()
        self.statusBar().showMessage(tr("ui.statusbar.ready"))
        self.load_profiles()

    def _on_import_profile(self) -> None:
        """Import profiles from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ui.dialog.import_profile.title"),
            "",
            tr("ui.dialog.import_profile.filter"),
        )
        if not file_path:
            return

        try:
            profiles = ProfileTransfer.import_from_file(file_path)
            saved = self._service.import_profiles(profiles, on_conflict="rename")
            self.load_profiles()
            names = ", ".join(p.name for p in saved)
            QMessageBox.information(
                self,
                tr("ui.dialog.import_profile.title"),
                tr("profile.imported_count", count=len(saved), names=names),
            )
        except Exception as err:
            QMessageBox.critical(
                self,
                tr("ui.dialog.import_profile.title"),
                str(err),
            )

    def _on_export_profile(self) -> None:
        """Export the selected profile to a JSON file."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return

        profile = summary.profile
        default_file = f"{profile.name.strip().replace(' ', '_')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("ui.dialog.export_profile.title"),
            default_file,
            tr("ui.dialog.export_profile.filter"),
        )
        if not file_path:
            return

        try:
            ProfileTransfer.export_to_file(profile, file_path)
            self.statusBar().showMessage(
                tr("profile.exported", count=1, path=file_path),
                4000,
            )
        except Exception as err:
            QMessageBox.critical(
                self,
                tr("ui.dialog.export_profile.title"),
                str(err),
            )

    def _on_import_script(self) -> None:
        """Import folders and options from a shell script (e.g. sync.sh)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ui.dialog.import_script.title"),
            "",
            tr("ui.dialog.import_script.filter"),
        )
        if not file_path:
            return

        try:
            imported_profile = ScriptImporter.parse_file(file_path)
        except Exception as err:
            QMessageBox.critical(
                self,
                tr("ui.dialog.import_script.title"),
                tr("script.import_failed", error=str(err)),
            )
            return

        # If a profile with the same name already exists, suggest a unique candidate
        if self._service.get_profile_by_name(imported_profile.name) is not None:
            base_name = imported_profile.name
            idx = 1
            while self._service.get_profile_by_name(f"{base_name} ({idx})") is not None:
                idx += 1
            imported_profile.name = f"{base_name} ({idx})"

        # Open wizard pre-filled with the imported profile for review and saving
        wizard = ProfileWizard(
            service=self._service,
            remote_service=self._remote_service,
            profile=imported_profile,
            parent=self,
        )
        if wizard.exec() and wizard.saved_profile is not None:
            self.statusBar().showMessage(
                tr("ui.statusbar.profile_created", name=wizard.saved_profile.name), 4000
            )
            self.load_profiles()

    def _on_watch_profile(self) -> None:
        """Open watchdog observation dialog for the selected profile."""
        summary = self._selected_summary()
        if summary is None or summary.profile.id is None:
            return

        dialog = WatchDialog(
            profile=summary.profile,
            run_service=self._run_service,
            parent=self,
        )
        dialog.exec()
        self.load_profiles()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up resources on window close."""
        unregister_language_listener(self.retranslate_ui)
        if self._startup_worker is not None and self._startup_worker.isRunning():
            self._startup_worker.requestInterruption()
            self._startup_worker.quit()
            self._startup_worker.wait(500)
        if self._update_worker is not None and self._update_worker.isRunning():
            self._update_worker.requestInterruption()
            self._update_worker.quit()
            self._update_worker.wait(500)
        if self._run_conn is not None:
            self._run_conn.close()
        self._service.close()
        super().closeEvent(event)
