# SPDX-License-Identifier: GPL-3.0-or-later
"""Advanced options dialog for configuring sync filters, safety, limits, and flags."""

from __future__ import annotations

import contextlib
import re
import shlex
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pontis.domain.models import (
    ConflictPolicy,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.i18n import tr
from pontis.infra.paths import config_dir, default_db_path
from pontis.infra.rclone import locate_rclone
from pontis.infra.rclone_adapter import (
    RcloneAdapter,
    check_extra_flag,
)
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pathlib import Path

_BWLIMIT_RE = re.compile(r"^[0-9a-zA-Z:,\.\s]+$")


class AdvancedOptionsDialog(QDialog):
    """Dialog for fine-tuning profile options with live rclone command preview."""

    def __init__(
        self,
        profile: SyncProfile,
        parent: QWidget | None = None,
        rclone_binary: Path | str | None = None,
        rclone_config: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._options = profile.options

        # Copy collections to allow discarding edits on Cancel
        self._excludes: list[str] = list(self._options.excludes)
        self._includes: list[str] = list(self._options.includes)
        self._extra_flags: list[str] = list(self._options.extra_flags)

        self._result_options: SyncOptions = self._options

        # Setup adapter for previewing commands
        if rclone_binary is not None:
            self._bin_path = rclone_binary
        else:
            try:
                self._bin_path = locate_rclone().path
            except Exception:
                self._bin_path = "rclone"

        self._config_path = rclone_config or (config_dir() / "rclone.conf")
        state_root = default_db_path().parent / "bisync"
        self._adapter = RcloneAdapter(
            binary=self._bin_path,
            state_root=state_root,
            config_path=self._config_path,
        )

        title_name = profile.name or tr("ui.advanced.title_generic")
        self.setWindowTitle(tr("ui.advanced.title", name=title_name))
        self.setWindowIcon(get_icon("preferences-other"))
        self.resize(760, 680)

        self._init_ui()
        self._load_values()
        self._validate_and_refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header: Profile identification and endpoints
        header_widget = self._create_header_widget()
        layout.addWidget(header_widget)

        # Tab widget for categories
        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._create_filters_tab(), tr("ui.advanced.tab_filters"))
        self._tabs.addTab(self._create_safety_tab(), tr("ui.advanced.tab_safety"))
        self._tabs.addTab(self._create_performance_tab(), tr("ui.advanced.tab_performance"))
        self._tabs.addTab(self._create_flags_tab(), tr("ui.advanced.tab_flags"))
        layout.addWidget(self._tabs)

        # Command preview box
        preview_group = self._create_preview_group()
        layout.addWidget(preview_group)

        # Dialog action buttons
        buttons_layout = self._create_buttons_layout()
        layout.addLayout(buttons_layout)

    def _create_header_widget(self) -> QWidget:
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 4)

        icon_lbl = QLabel(widget)
        icon_lbl.setPixmap(get_icon("sync").pixmap(28, 28))
        layout.addWidget(icon_lbl)

        dir_symbol = {
            SyncDirection.BIDIRECTIONAL: "↔",
            SyncDirection.A_TO_B: "→",
            SyncDirection.B_TO_A: "←",
        }.get(self._profile.options.direction, "↔")

        side_a = self._profile.side_a.to_rclone() or "(Lado A)"
        side_b = self._profile.side_b.to_rclone() or "(Lado B)"
        endpoints_text = tr(
            "ui.advanced.header_endpoints",
            side_a=side_a,
            direction=dir_symbol,
            side_b=side_b,
        )

        lbl = QLabel(f"<b>{self._profile.name}</b>: {endpoints_text}", widget)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(lbl, 1)

        return widget

    def _create_filters_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setSpacing(12)

        # Left Column: Excludes (--exclude)
        excludes_group = QGroupBox(tr("ui.advanced.filters.excludes_group"), tab)
        ex_layout = QVBoxLayout(excludes_group)

        ex_desc = QLabel(tr("ui.advanced.filters.excludes_desc"), excludes_group)
        ex_desc.setWordWrap(True)
        ex_layout.addWidget(ex_desc)

        self._list_excludes = QListWidget(excludes_group)
        self._list_excludes.setAlternatingRowColors(True)
        ex_layout.addWidget(self._list_excludes)

        ex_input_layout = QHBoxLayout()
        self._edit_exclude = QLineEdit(excludes_group)
        self._edit_exclude.setPlaceholderText(tr("ui.advanced.filters.placeholder"))
        self._edit_exclude.returnPressed.connect(self._on_add_exclude)
        self._btn_add_exclude = QPushButton(tr("ui.advanced.filters.btn_add"), excludes_group)
        self._btn_add_exclude.setIcon(get_icon("list-add"))
        self._btn_add_exclude.clicked.connect(self._on_add_exclude)
        ex_input_layout.addWidget(self._edit_exclude, 1)
        ex_input_layout.addWidget(self._btn_add_exclude)
        ex_layout.addLayout(ex_input_layout)

        ex_btn_layout = QHBoxLayout()
        self._btn_remove_exclude = QPushButton(tr("ui.advanced.filters.btn_remove"), excludes_group)
        self._btn_remove_exclude.setIcon(get_icon("edit-delete"))
        self._btn_remove_exclude.clicked.connect(self._on_remove_exclude)
        self._btn_clear_excludes = QPushButton(tr("ui.advanced.filters.btn_clear"), excludes_group)
        self._btn_clear_excludes.clicked.connect(self._on_clear_excludes)
        ex_btn_layout.addWidget(self._btn_remove_exclude)
        ex_btn_layout.addWidget(self._btn_clear_excludes)
        ex_layout.addLayout(ex_btn_layout)

        layout.addWidget(excludes_group, 1)

        # Right Column: Includes (--include)
        includes_group = QGroupBox(tr("ui.advanced.filters.includes_group"), tab)
        in_layout = QVBoxLayout(includes_group)

        in_desc = QLabel(tr("ui.advanced.filters.includes_desc"), includes_group)
        in_desc.setWordWrap(True)
        in_layout.addWidget(in_desc)

        self._list_includes = QListWidget(includes_group)
        self._list_includes.setAlternatingRowColors(True)
        in_layout.addWidget(self._list_includes)

        in_input_layout = QHBoxLayout()
        self._edit_include = QLineEdit(includes_group)
        self._edit_include.setPlaceholderText(tr("ui.advanced.filters.placeholder"))
        self._edit_include.returnPressed.connect(self._on_add_include)
        self._btn_add_include = QPushButton(tr("ui.advanced.filters.btn_add"), includes_group)
        self._btn_add_include.setIcon(get_icon("list-add"))
        self._btn_add_include.clicked.connect(self._on_add_include)
        in_input_layout.addWidget(self._edit_include, 1)
        in_input_layout.addWidget(self._btn_add_include)
        in_layout.addLayout(in_input_layout)

        in_btn_layout = QHBoxLayout()
        self._btn_remove_include = QPushButton(tr("ui.advanced.filters.btn_remove"), includes_group)
        self._btn_remove_include.setIcon(get_icon("edit-delete"))
        self._btn_remove_include.clicked.connect(self._on_remove_include)
        self._btn_clear_includes = QPushButton(tr("ui.advanced.filters.btn_clear"), includes_group)
        self._btn_clear_includes.clicked.connect(self._on_clear_includes)
        in_btn_layout.addWidget(self._btn_remove_include)
        in_btn_layout.addWidget(self._btn_clear_includes)
        in_layout.addLayout(in_btn_layout)

        layout.addWidget(includes_group, 1)

        return tab

    def _create_safety_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        # Conflict Policy
        conflict_group = QGroupBox(tr("ui.advanced.safety.conflict_group"), tab)
        conf_layout = QFormLayout(conflict_group)

        self._combo_conflict = QComboBox(conflict_group)
        self._combo_conflict.addItem(tr("ui.wizard.conflict.keep_both"), ConflictPolicy.KEEP_BOTH)
        self._combo_conflict.addItem(tr("ui.wizard.conflict.newer"), ConflictPolicy.NEWER)
        self._combo_conflict.addItem(tr("ui.wizard.conflict.larger"), ConflictPolicy.LARGER)
        self._combo_conflict.addItem(tr("ui.wizard.conflict.path1"), ConflictPolicy.PATH1)
        self._combo_conflict.addItem(tr("ui.wizard.conflict.path2"), ConflictPolicy.PATH2)
        self._combo_conflict.currentIndexChanged.connect(self._on_conflict_changed)
        conf_layout.addRow(tr("ui.advanced.safety.conflict_policy"), self._combo_conflict)
        layout.addWidget(conflict_group)

        # Max Delete Files
        max_del_group = QGroupBox(tr("ui.advanced.safety.max_delete_group"), tab)
        max_del_layout = QVBoxLayout(max_del_group)

        slider_row = QHBoxLayout()
        self._slider_max_delete = QSlider(Qt.Orientation.Horizontal, max_del_group)
        self._slider_max_delete.setRange(1, 100)
        self._spin_max_delete = QSpinBox(max_del_group)
        self._spin_max_delete.setRange(1, 1000)
        self._spin_max_delete.setSuffix(f" {tr('ui.advanced.safety.files_suffix')}")

        self._slider_max_delete.valueChanged.connect(self._spin_max_delete.setValue)
        self._spin_max_delete.valueChanged.connect(self._on_max_delete_changed)

        slider_row.addWidget(self._slider_max_delete, 1)
        slider_row.addWidget(self._spin_max_delete)
        max_del_layout.addLayout(slider_row)

        self._lbl_max_delete_desc = QLabel(max_del_group)
        self._lbl_max_delete_desc.setWordWrap(True)
        max_del_layout.addWidget(self._lbl_max_delete_desc)
        layout.addWidget(max_del_group)

        # Check Access
        check_acc_group = QGroupBox(tab)
        check_layout = QVBoxLayout(check_acc_group)
        self._chk_check_access = QCheckBox(tr("ui.advanced.safety.check_access"), check_acc_group)
        self._chk_check_access.toggled.connect(self._on_check_access_toggled)
        check_layout.addWidget(self._chk_check_access)

        lbl_check_desc = QLabel(tr("ui.advanced.safety.check_access_desc"), check_acc_group)
        lbl_check_desc.setWordWrap(True)
        check_layout.addWidget(lbl_check_desc)
        layout.addWidget(check_acc_group)

        layout.addStretch()
        return tab

    def _create_performance_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        # Bandwidth Limit (--bwlimit)
        bw_group = QGroupBox(tr("ui.advanced.performance.bwlimit_group"), tab)
        bw_layout = QVBoxLayout(bw_group)

        bw_form = QFormLayout()
        self._edit_bwlimit = QLineEdit(bw_group)
        self._edit_bwlimit.setPlaceholderText(tr("ui.advanced.performance.bwlimit_placeholder"))
        self._edit_bwlimit.textChanged.connect(self._on_bwlimit_changed)
        bw_form.addRow(tr("ui.advanced.performance.bwlimit_label"), self._edit_bwlimit)
        bw_layout.addLayout(bw_form)

        bw_desc = QLabel(tr("ui.advanced.performance.bwlimit_desc"), bw_group)
        bw_desc.setWordWrap(True)
        bw_layout.addWidget(bw_desc)

        self._lbl_bw_error = QLabel(bw_group)
        self._lbl_bw_error.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self._lbl_bw_error.setVisible(False)
        bw_layout.addWidget(self._lbl_bw_error)

        layout.addWidget(bw_group)

        # Parallel Transfers (--transfers)
        trans_group = QGroupBox(tr("ui.advanced.performance.transfers_group"), tab)
        trans_layout = QVBoxLayout(trans_group)

        self._chk_enable_transfers = QCheckBox(
            tr("ui.advanced.performance.transfers_enable"), trans_group
        )
        self._chk_enable_transfers.toggled.connect(self._on_transfers_toggled)
        trans_layout.addWidget(self._chk_enable_transfers)

        trans_form = QFormLayout()
        self._spin_transfers = QSpinBox(trans_group)
        self._spin_transfers.setRange(1, 128)
        self._spin_transfers.setValue(4)
        self._spin_transfers.setEnabled(False)
        self._spin_transfers.valueChanged.connect(self._on_transfers_changed)
        trans_form.addRow(tr("ui.advanced.performance.transfers_label"), self._spin_transfers)
        trans_layout.addLayout(trans_form)

        trans_desc = QLabel(tr("ui.advanced.performance.transfers_desc"), trans_group)
        trans_desc.setWordWrap(True)
        trans_layout.addWidget(trans_desc)

        layout.addWidget(trans_group)
        layout.addStretch()
        return tab

    def _create_flags_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        flags_group = QGroupBox(tr("ui.advanced.flags.group"), tab)
        fg_layout = QVBoxLayout(flags_group)

        desc = QLabel(tr("ui.advanced.flags.desc"), flags_group)
        desc.setWordWrap(True)
        fg_layout.addWidget(desc)

        self._edit_flags = QPlainTextEdit(flags_group)
        self._edit_flags.setPlaceholderText(tr("ui.advanced.flags.placeholder"))
        self._edit_flags.textChanged.connect(self._on_flags_text_changed)
        fg_layout.addWidget(self._edit_flags)

        self._lbl_flags_error = QLabel(flags_group)
        self._lbl_flags_error.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self._lbl_flags_error.setWordWrap(True)
        self._lbl_flags_error.setVisible(False)
        fg_layout.addWidget(self._lbl_flags_error)

        layout.addWidget(flags_group)
        return tab

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox(tr("ui.advanced.preview.title"), self)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        controls_row = QHBoxLayout()

        self._chk_dry_run = QCheckBox(tr("ui.advanced.preview.dry_run"), group)
        self._chk_dry_run.toggled.connect(self._validate_and_refresh)
        controls_row.addWidget(self._chk_dry_run)

        is_bisync = self._profile.options.direction is SyncDirection.BIDIRECTIONAL
        self._chk_resync = QCheckBox(tr("ui.advanced.preview.first_run"), group)
        self._chk_resync.setEnabled(is_bisync)
        self._chk_resync.toggled.connect(self._validate_and_refresh)
        controls_row.addWidget(self._chk_resync)

        controls_row.addStretch()

        self._btn_copy = QPushButton(tr("ui.advanced.preview.btn_copy"), group)
        self._btn_copy.setIcon(get_icon("edit-copy"))
        self._btn_copy.clicked.connect(self._on_copy_command)
        controls_row.addWidget(self._btn_copy)

        layout.addLayout(controls_row)

        self._preview_text = QPlainTextEdit(group)
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(85)
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self._preview_text.setFont(mono_font)
        layout.addWidget(self._preview_text)

        return group

    def _create_buttons_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_reset = QPushButton(tr("ui.advanced.btn_reset"), self)
        self._btn_reset.setIcon(get_icon("view-refresh"))
        self._btn_reset.clicked.connect(self._on_reset_defaults)
        layout.addWidget(self._btn_reset)

        layout.addStretch()

        self._btn_cancel = QPushButton(tr("ui.advanced.btn_cancel"), self)
        self._btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self._btn_cancel)

        self._btn_save = QPushButton(tr("ui.advanced.btn_save"), self)
        self._btn_save.setIcon(get_icon("list-add"))
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._on_save)
        layout.addWidget(self._btn_save)

        return layout

    def _load_values(self) -> None:
        """Populate widgets with current profile options."""
        opts = self._options

        # Excludes
        self._list_excludes.clear()
        for pattern in self._excludes:
            self._list_excludes.addItem(pattern)

        # Includes
        self._list_includes.clear()
        for pattern in self._includes:
            self._list_includes.addItem(pattern)

        # Conflict policy
        for i in range(self._combo_conflict.count()):
            val = self._combo_conflict.itemData(i)
            if val == opts.conflict_policy or str(val) == opts.conflict_policy.value:
                self._combo_conflict.setCurrentIndex(i)
                break

        # Max delete
        self._slider_max_delete.setValue(min(opts.max_delete_files, 100))
        self._spin_max_delete.setValue(opts.max_delete_files)
        self._update_max_delete_label(opts.max_delete_files)

        # Check access
        self._chk_check_access.setChecked(opts.check_access)

        # Bandwidth limit
        self._edit_bwlimit.setText(opts.bandwidth_limit or "")

        # Transfers
        if opts.transfers is not None:
            self._chk_enable_transfers.setChecked(True)
            self._spin_transfers.setEnabled(True)
            self._spin_transfers.setValue(opts.transfers)
        else:
            self._chk_enable_transfers.setChecked(False)
            self._spin_transfers.setEnabled(False)
            self._spin_transfers.setValue(4)

        # Extra flags
        self._edit_flags.setPlainText("\n".join(self._extra_flags))

    # ---------------------------------------------------------------- Slots & Event Handlers

    def _on_add_exclude(self) -> None:
        pattern = self._edit_exclude.text().strip()
        if not pattern:
            return
        if pattern not in self._excludes:
            self._excludes.append(pattern)
            self._list_excludes.addItem(pattern)
            self._validate_and_refresh()
        self._edit_exclude.clear()

    def _on_remove_exclude(self) -> None:
        row = self._list_excludes.currentRow()
        if 0 <= row < len(self._excludes):
            self._excludes.pop(row)
            item = self._list_excludes.takeItem(row)
            del item
            self._validate_and_refresh()

    def _on_clear_excludes(self) -> None:
        if not self._excludes:
            return
        self._excludes.clear()
        self._list_excludes.clear()
        self._validate_and_refresh()

    def _on_add_include(self) -> None:
        pattern = self._edit_include.text().strip()
        if not pattern:
            return
        if pattern not in self._includes:
            self._includes.append(pattern)
            self._list_includes.addItem(pattern)
            self._validate_and_refresh()
        self._edit_include.clear()

    def _on_remove_include(self) -> None:
        row = self._list_includes.currentRow()
        if 0 <= row < len(self._includes):
            self._includes.pop(row)
            item = self._list_includes.takeItem(row)
            del item
            self._validate_and_refresh()

    def _on_clear_includes(self) -> None:
        if not self._includes:
            return
        self._includes.clear()
        self._list_includes.clear()
        self._validate_and_refresh()

    def _on_conflict_changed(self) -> None:
        self._validate_and_refresh()

    def _on_max_delete_changed(self, value: int) -> None:
        if self._slider_max_delete.value() != min(value, 100):
            self._slider_max_delete.blockSignals(True)
            self._slider_max_delete.setValue(min(value, 100))
            self._slider_max_delete.blockSignals(False)
        self._update_max_delete_label(value)
        self._validate_and_refresh()

    def _update_max_delete_label(self, count: int) -> None:
        self._lbl_max_delete_desc.setText(tr("ui.advanced.safety.max_delete_desc", count=count))

    def _on_check_access_toggled(self) -> None:
        self._validate_and_refresh()

    def _on_bwlimit_changed(self) -> None:
        self._validate_and_refresh()

    def _on_transfers_toggled(self, checked: bool) -> None:
        self._spin_transfers.setEnabled(checked)
        self._validate_and_refresh()

    def _on_transfers_changed(self) -> None:
        self._validate_and_refresh()

    def _on_flags_text_changed(self) -> None:
        self._validate_and_refresh()

    def _on_copy_command(self) -> None:
        text = self._preview_text.toPlainText().strip()
        if text:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
            orig_text = tr("ui.advanced.preview.btn_copy")
            self._btn_copy.setText(tr("ui.advanced.preview.copied"))

            def _reset_copy_btn() -> None:
                with contextlib.suppress(RuntimeError):
                    self._btn_copy.setText(orig_text)

            QTimer.singleShot(2000, _reset_copy_btn)

    def _on_reset_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            tr("ui.advanced.btn_reset"),
            tr("ui.advanced.reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            defaults = SyncOptions()
            self._excludes.clear()
            self._includes.clear()
            self._extra_flags.clear()
            self._options = defaults
            self._load_values()
            self._validate_and_refresh()

    # ---------------------------------------------------------------- Validation & Command Assembly

    def _parse_flags(self) -> tuple[list[str], str | None]:
        raw_text = self._edit_flags.toPlainText().strip()
        if not raw_text:
            return [], None

        try:
            tokens = shlex.split(raw_text)
        except ValueError:
            tokens = raw_text.split()

        flags: list[str] = []
        for token in tokens:
            cleaned = token.strip()
            if not cleaned:
                continue
            err = check_extra_flag(cleaned)
            if err is not None:
                # Provide a user-friendly localized message
                flag_name = cleaned.split("=", 1)[0]
                if not cleaned.startswith("-"):
                    return [], tr("ui.advanced.flags.invalid_warning")
                return [], tr("ui.advanced.flags.forbidden_warning", flag=flag_name)
            flags.append(cleaned)
        return flags, None

    def _validate_and_refresh(self) -> None:
        """Validate all current inputs and rebuild the rclone command preview."""
        has_errors = False

        # 1. Bandwidth limit validation
        bw_val = self._edit_bwlimit.text().strip()
        if bw_val and not _BWLIMIT_RE.match(bw_val):
            self._lbl_bw_error.setText(tr("ui.advanced.performance.bwlimit_invalid"))
            self._lbl_bw_error.setVisible(True)
            has_errors = True
        else:
            self._lbl_bw_error.setVisible(False)

        # 2. Extra flags validation
        flags, flags_err = self._parse_flags()
        if flags_err is not None:
            self._lbl_flags_error.setText(flags_err)
            self._lbl_flags_error.setVisible(True)
            has_errors = True
        else:
            self._lbl_flags_error.setVisible(False)

        self._btn_save.setEnabled(not has_errors)

        if has_errors:
            self._preview_text.setPlainText("...")
            return

        # 3. Assemble temporary SyncOptions
        raw_conflict = self._combo_conflict.currentData()
        try:
            conflict_val = ConflictPolicy(str(raw_conflict))
        except (ValueError, TypeError):
            conflict_val = ConflictPolicy.KEEP_BOTH

        transfers_val: int | None = None
        if self._chk_enable_transfers.isChecked():
            transfers_val = self._spin_transfers.value()

        current_options = SyncOptions(
            direction=self._profile.options.direction,
            conflict_policy=conflict_val,
            max_delete_files=self._spin_max_delete.value(),
            check_access=self._chk_check_access.isChecked(),
            excludes=tuple(self._excludes),
            includes=tuple(self._includes),
            bandwidth_limit=bw_val or None,
            transfers=transfers_val,
            extra_flags=tuple(flags),
        )

        # 4. Generate command preview using RcloneAdapter
        temp_profile = SyncProfile(
            name=self._profile.name or "preview",
            side_a=self._profile.side_a,
            side_b=self._profile.side_b,
            options=current_options,
            id=self._profile.id,
        )

        dry_run = self._chk_dry_run.isChecked()
        resync_opt: bool | None = None
        if self._profile.options.direction is SyncDirection.BIDIRECTIONAL:
            resync_opt = bool(self._chk_resync.isChecked())

        try:
            cmd = self._adapter.build_command(
                temp_profile,
                dry_run=dry_run,
                resync=resync_opt,
            )
            # Pretty-print command for terminal preview
            command_line = shlex.join(cmd)
            self._preview_text.setPlainText(command_line)
        except Exception as e:
            self._preview_text.setPlainText(f"# Error generating preview: {e}")

    def _on_save(self) -> None:
        """Validate and apply options."""
        flags, flags_err = self._parse_flags()
        if flags_err is not None:
            self._tabs.setCurrentIndex(3)
            return

        bw_val = self._edit_bwlimit.text().strip()
        if bw_val and not _BWLIMIT_RE.match(bw_val):
            self._tabs.setCurrentIndex(2)
            return

        raw_conflict = self._combo_conflict.currentData()
        try:
            conflict_val = ConflictPolicy(str(raw_conflict))
        except (ValueError, TypeError):
            conflict_val = ConflictPolicy.KEEP_BOTH

        transfers_val: int | None = None
        if self._chk_enable_transfers.isChecked():
            transfers_val = self._spin_transfers.value()

        self._result_options = SyncOptions(
            direction=self._profile.options.direction,
            conflict_policy=conflict_val,
            max_delete_files=self._spin_max_delete.value(),
            check_access=self._chk_check_access.isChecked(),
            excludes=tuple(self._excludes),
            includes=tuple(self._includes),
            bandwidth_limit=bw_val or None,
            transfers=transfers_val,
            extra_flags=tuple(flags),
        )

        self.save_to_profile(self._profile)
        self.accept()

    def get_options(self) -> SyncOptions:
        """Return the finalized :class:`SyncOptions`."""
        return self._result_options

    def save_to_profile(self, profile: SyncProfile) -> None:
        """Apply the finalized options to a target profile."""
        profile.options = self._result_options
