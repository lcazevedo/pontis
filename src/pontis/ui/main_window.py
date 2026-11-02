# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window for Pontis: displays sync profiles, action bar, and empty states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from pontis.i18n import tr
from pontis.infra.keyring_store import KEY_RCLONE_CONFIG_PASS, KeyringStore
from pontis.infra.paths import config_dir, default_db_path
from pontis.infra.rclone import locate_rclone
from pontis.infra.rclone_adapter import RcloneAdapter
from pontis.infra.repositories import RunRepository
from pontis.services.profile_service import ProfileService, ProfileSummary
from pontis.services.remote_service import RemoteService
from pontis.services.run_service import RunService
from pontis.ui.advanced_options_dialog import AdvancedOptionsDialog
from pontis.ui.dry_run_summary_dialog import DryRunSummaryDialog
from pontis.ui.icons import get_icon
from pontis.ui.sync_progress_dialog import SyncProgressDialog
from pontis.ui.theme import ThemeMode, apply_theme
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service if service is not None else ProfileService(db_path=db_path)
        self._rclone_config = rclone_config or (config_dir() / "rclone.conf")
        if rclone_binary is not None:
            self._rclone_binary: Path | str = rclone_binary
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
            self._run_service = RunService(
                adapter,
                RunRepository(self._service.connection),
                lock_dir=lock_dir,
            )

        self._running_profile_ids: set[int] = set()
        self._summaries: list[ProfileSummary] = []
        self._current_theme: ThemeMode = ThemeMode.SYSTEM

        self.setWindowTitle(tr("ui.main.title"))
        self.resize(950, 560)
        self.setWindowIcon(get_icon("sync"))

        self._init_ui()
        self.load_profiles()

    def _init_ui(self) -> None:
        """Construct actions, toolbar, stacked widget, and status bar."""
        self._create_actions()
        self._create_toolbar()
        self._create_menus()
        self._create_central_widget()
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

        self._action_delete = QAction(get_icon("edit-delete"), tr("ui.actions.delete"), self)
        self._action_delete.setToolTip(tr("ui.actions.delete.tooltip"))
        self._action_delete.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self._action_delete.setEnabled(False)
        self._action_delete.triggered.connect(self._on_delete_profile)

        self._action_refresh = QAction(get_icon("view-refresh"), tr("ui.actions.refresh"), self)
        self._action_refresh.setToolTip(tr("ui.actions.refresh.tooltip"))
        self._action_refresh.setShortcut(QKeySequence("F5"))
        self._action_refresh.triggered.connect(self._on_refresh)

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
        toolbar.addSeparator()
        toolbar.addAction(self._action_new)
        toolbar.addAction(self._action_edit)
        toolbar.addAction(self._action_advanced)
        toolbar.addAction(self._action_delete)
        toolbar.addAction(self._action_refresh)
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

        self._theme_system_action.setChecked(True)
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

        file_menu = menubar.addMenu(tr("ui.menu.file"))
        file_menu.addAction(self._action_new)
        file_menu.addSeparator()
        file_menu.addAction(self._action_quit)

        profile_menu = menubar.addMenu(tr("ui.menu.profile"))
        profile_menu.addAction(self._action_sync)
        profile_menu.addAction(self._action_dry_run)
        profile_menu.addSeparator()
        profile_menu.addAction(self._action_new)
        profile_menu.addAction(self._action_edit)
        profile_menu.addAction(self._action_advanced)
        profile_menu.addAction(self._action_delete)
        profile_menu.addAction(self._action_refresh)

        view_menu = menubar.addMenu(tr("ui.menu.view"))
        theme_submenu = view_menu.addMenu(tr("ui.actions.theme"))
        theme_submenu.addAction(self._theme_system_action)
        theme_submenu.addAction(self._theme_light_action)
        theme_submenu.addAction(self._theme_dark_action)

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
        self._action_delete.setEnabled(has_sel and not is_running)
        self._action_edit.setEnabled(has_sel and not is_running)
        self._action_advanced.setEnabled(has_sel and not is_running)

    def _on_table_context_menu(self, pos: QPoint) -> None:
        """Show context menu on right-click."""
        menu = QMenu(self)
        if self._selected_summary() is not None:
            menu.addAction(self._action_sync)
            menu.addAction(self._action_dry_run)
            menu.addSeparator()
            menu.addAction(self._action_edit)
            menu.addAction(self._action_advanced)
            menu.addAction(self._action_delete)
            menu.addSeparator()
        menu.addAction(self._action_new)
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
        self, profile: SyncProfile, *, dry_run: bool, is_first_run: bool = False
    ) -> None:
        """Launch the sync progress dialog and track execution lifecycle."""
        if profile.id is None:
            return
        self._running_profile_ids.add(profile.id)
        self.load_profiles()
        self._on_selection_changed()

        apply_real_after_dry_run = False

        dialog = SyncProgressDialog(
            profile,
            self._run_service,
            dry_run=dry_run,
            parent=self,
        )

        def _on_apply_requested() -> None:
            nonlocal apply_real_after_dry_run
            apply_real_after_dry_run = True

        dialog.apply_real_sync_requested.connect(_on_apply_requested)
        dialog.exec()

        self._running_profile_ids.discard(profile.id)
        self.load_profiles()
        self._on_selection_changed()

        if apply_real_after_dry_run:
            self._execute_profile(profile, dry_run=False)
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
                self._execute_profile(profile, dry_run=False)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up resources on window close."""
        self._service.close()
        super().closeEvent(event)
