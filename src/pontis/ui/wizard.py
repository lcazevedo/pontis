# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile creation and editing wizard for Pontis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from pontis.domain.models import (
    ConflictPolicy,
    Schedule,
    ScheduleKind,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.i18n import tr
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.ui.advanced_options_dialog import AdvancedOptionsDialog
from pontis.ui.icons import get_icon
from pontis.ui.widgets.endpoint_picker import EndpointPickerWidget

if TYPE_CHECKING:
    pass


class ProfileNamePage(QWizardPage):
    """Step 1: Profile Identification."""

    def __init__(
        self,
        service: ProfileService,
        current_profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._current_profile = current_profile

        self.setTitle(tr("ui.wizard.name.title"))
        self.setSubTitle(tr("ui.wizard.name.subtitle"))

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self._edit_name = QLineEdit(self)
        self._edit_name.setPlaceholderText(tr("ui.wizard.name.placeholder"))
        if current_profile is not None:
            self._edit_name.setText(current_profile.name)
        self._edit_name.textChanged.connect(self._on_text_changed)
        form_layout.addRow(tr("ui.wizard.name.label"), self._edit_name)
        layout.addLayout(form_layout)

        self._lbl_error = QLabel(self)
        self._lbl_error.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self._lbl_error.setVisible(False)
        layout.addWidget(self._lbl_error)
        layout.addStretch()

    def _on_text_changed(self) -> None:
        self._validate()
        self.completeChanged.emit()

    def _validate(self) -> bool:
        name = self._edit_name.text().strip()
        if not name:
            self._lbl_error.setText(tr("ui.wizard.name.error_empty"))
            self._lbl_error.setVisible(True)
            return False

        existing = self._service.get_profile_by_name(name)
        if existing is not None and (
            self._current_profile is None or existing.id != self._current_profile.id
        ):
            self._lbl_error.setText(tr("ui.wizard.name.error_duplicate"))
            self._lbl_error.setVisible(True)
            return False

        self._lbl_error.setVisible(False)
        return True

    def isComplete(self) -> bool:
        return self._validate()

    def profile_name(self) -> str:
        return self._edit_name.text().strip()


class SideAPage(QWizardPage):
    """Step 2: Configure Side A."""

    def __init__(
        self,
        remote_service: RemoteService,
        current_profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle(tr("ui.wizard.side_a.title"))
        self.setSubTitle(tr("ui.wizard.side_a.subtitle"))

        layout = QVBoxLayout(self)
        self.picker = EndpointPickerWidget(remote_service=remote_service, parent=self)
        if current_profile is not None:
            self.picker.set_endpoint(current_profile.side_a)
        self.picker.changed.connect(self.completeChanged)
        layout.addWidget(self.picker)

        self._lbl_error = QLabel(self)
        self._lbl_error.setStyleSheet("color: #b91c1c; font-weight: bold;")
        layout.addWidget(self._lbl_error)

    def isComplete(self) -> bool:
        valid, msg = self.picker.is_valid()
        self._lbl_error.setText(msg)
        self._lbl_error.setVisible(not valid)
        return valid


class SideBPage(QWizardPage):
    """Step 3: Configure Side B."""

    def __init__(
        self,
        remote_service: RemoteService,
        side_a_page: SideAPage,
        current_profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._side_a_page = side_a_page
        self.setTitle(tr("ui.wizard.side_b.title"))
        self.setSubTitle(tr("ui.wizard.side_b.subtitle"))

        layout = QVBoxLayout(self)
        self.picker = EndpointPickerWidget(remote_service=remote_service, parent=self)
        if current_profile is not None:
            self.picker.set_endpoint(current_profile.side_b)
        self.picker.changed.connect(self.completeChanged)
        layout.addWidget(self.picker)

        self._lbl_error = QLabel(self)
        self._lbl_error.setStyleSheet("color: #b91c1c; font-weight: bold;")
        layout.addWidget(self._lbl_error)

    def isComplete(self) -> bool:
        valid, msg = self.picker.is_valid()
        if not valid:
            self._lbl_error.setText(msg)
            self._lbl_error.setVisible(True)
            return False

        endpoint_a = self._side_a_page.picker.get_endpoint()
        endpoint_b = self.picker.get_endpoint()
        if endpoint_a and endpoint_b and endpoint_a.to_rclone() == endpoint_b.to_rclone():
            self._lbl_error.setText(tr("ui.wizard.side_b.error_same"))
            self._lbl_error.setVisible(True)
            return False

        self._lbl_error.setVisible(False)
        return True


class DirectionPage(QWizardPage):
    """Step 4: Sync Direction."""

    def __init__(
        self,
        current_profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle(tr("ui.wizard.direction.title"))
        self.setSubTitle(tr("ui.wizard.direction.subtitle"))

        layout = QVBoxLayout(self)

        self._btn_group = QButtonGroup(self)

        # 1: Bidirectional
        self._rb_bidi = QRadioButton(tr("ui.wizard.direction.bidirectional"), self)
        lbl_bidi = QLabel(tr("ui.wizard.direction.bidirectional_desc"), self)
        lbl_bidi.setStyleSheet("color: #64748b; margin-left: 24px;")

        # 2: A to B
        self._rb_a_to_b = QRadioButton(tr("ui.wizard.direction.a_to_b"), self)
        lbl_a_to_b = QLabel(tr("ui.wizard.direction.a_to_b_desc"), self)
        lbl_a_to_b.setStyleSheet("color: #64748b; margin-left: 24px;")

        # 3: B to A
        self._rb_b_to_a = QRadioButton(tr("ui.wizard.direction.b_to_a"), self)
        lbl_b_to_a = QLabel(tr("ui.wizard.direction.b_to_a_desc"), self)
        lbl_b_to_a.setStyleSheet("color: #64748b; margin-left: 24px;")

        self._btn_group.addButton(self._rb_bidi)
        self._btn_group.addButton(self._rb_a_to_b)
        self._btn_group.addButton(self._rb_b_to_a)

        selected_dir = (
            current_profile.options.direction
            if current_profile is not None
            else SyncDirection.BIDIRECTIONAL
        )
        if selected_dir == SyncDirection.A_TO_B:
            self._rb_a_to_b.setChecked(True)
        elif selected_dir == SyncDirection.B_TO_A:
            self._rb_b_to_a.setChecked(True)
        else:
            self._rb_bidi.setChecked(True)

        layout.addWidget(self._rb_bidi)
        layout.addWidget(lbl_bidi)
        layout.addSpacing(8)
        layout.addWidget(self._rb_a_to_b)
        layout.addWidget(lbl_a_to_b)
        layout.addSpacing(8)
        layout.addWidget(self._rb_b_to_a)
        layout.addWidget(lbl_b_to_a)
        layout.addStretch()

    def sync_direction(self) -> SyncDirection:
        if self._rb_a_to_b.isChecked():
            return SyncDirection.A_TO_B
        if self._rb_b_to_a.isChecked():
            return SyncDirection.B_TO_A
        return SyncDirection.BIDIRECTIONAL


class ConflictPolicyPage(QWizardPage):
    """Step 5: Conflict Policy and Scheduling placeholder."""

    def __init__(
        self,
        current_profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle(tr("ui.wizard.conflict.title"))
        self.setSubTitle(tr("ui.wizard.conflict.subtitle"))

        layout = QVBoxLayout(self)

        # Conflict resolution group
        conflict_group = QGroupBox(tr("ui.wizard.conflict.group"), self)
        conflict_layout = QVBoxLayout(conflict_group)

        self._btn_conflict_group = QButtonGroup(self)
        self._rb_keep_both = QRadioButton(tr("ui.wizard.conflict.keep_both"), self)
        self._rb_newer = QRadioButton(tr("ui.wizard.conflict.newer"), self)
        self._rb_larger = QRadioButton(tr("ui.wizard.conflict.larger"), self)
        self._rb_path1 = QRadioButton(tr("ui.wizard.conflict.path1"), self)
        self._rb_path2 = QRadioButton(tr("ui.wizard.conflict.path2"), self)

        self._btn_conflict_group.addButton(self._rb_keep_both)
        self._btn_conflict_group.addButton(self._rb_newer)
        self._btn_conflict_group.addButton(self._rb_larger)
        self._btn_conflict_group.addButton(self._rb_path1)
        self._btn_conflict_group.addButton(self._rb_path2)

        policy = (
            current_profile.options.conflict_policy
            if current_profile is not None
            else ConflictPolicy.KEEP_BOTH
        )
        if policy == ConflictPolicy.NEWER:
            self._rb_newer.setChecked(True)
        elif policy == ConflictPolicy.LARGER:
            self._rb_larger.setChecked(True)
        elif policy == ConflictPolicy.PATH1:
            self._rb_path1.setChecked(True)
        elif policy == ConflictPolicy.PATH2:
            self._rb_path2.setChecked(True)
        else:
            self._rb_keep_both.setChecked(True)

        conflict_layout.addWidget(self._rb_keep_both)
        conflict_layout.addWidget(self._rb_newer)
        conflict_layout.addWidget(self._rb_larger)
        conflict_layout.addWidget(self._rb_path1)
        conflict_layout.addWidget(self._rb_path2)
        layout.addWidget(conflict_group)

        # Schedule group (visual placeholder disabled for v1)
        schedule_group = QGroupBox(tr("ui.wizard.schedule.group"), self)
        sched_layout = QVBoxLayout(schedule_group)

        rb_manual = QRadioButton(tr("ui.wizard.schedule.manual"), self)
        rb_manual.setChecked(True)
        rb_interval = QRadioButton(tr("ui.wizard.schedule.interval"), self)
        rb_interval.setEnabled(False)

        lbl_sched_notice = QLabel(tr("ui.wizard.schedule.notice"), self)
        lbl_sched_notice.setStyleSheet("color: #64748b; font-style: italic;")

        sched_layout.addWidget(rb_manual)
        sched_layout.addWidget(rb_interval)
        sched_layout.addWidget(lbl_sched_notice)
        layout.addWidget(schedule_group)

    def conflict_policy(self) -> ConflictPolicy:
        if self._rb_newer.isChecked():
            return ConflictPolicy.NEWER
        if self._rb_larger.isChecked():
            return ConflictPolicy.LARGER
        if self._rb_path1.isChecked():
            return ConflictPolicy.PATH1
        if self._rb_path2.isChecked():
            return ConflictPolicy.PATH2
        return ConflictPolicy.KEEP_BOTH

    def set_conflict_policy(self, policy: ConflictPolicy) -> None:
        """Update the selected conflict policy radio button."""
        if policy == ConflictPolicy.NEWER:
            self._rb_newer.setChecked(True)
        elif policy == ConflictPolicy.LARGER:
            self._rb_larger.setChecked(True)
        elif policy == ConflictPolicy.PATH1:
            self._rb_path1.setChecked(True)
        elif policy == ConflictPolicy.PATH2:
            self._rb_path2.setChecked(True)
        else:
            self._rb_keep_both.setChecked(True)


class SummaryPage(QWizardPage):
    """Step 6: Review Summary."""

    def __init__(
        self,
        name_page: ProfileNamePage,
        side_a_page: SideAPage,
        side_b_page: SideBPage,
        direction_page: DirectionPage,
        conflict_page: ConflictPolicyPage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name_page = name_page
        self._side_a_page = side_a_page
        self._side_b_page = side_b_page
        self._direction_page = direction_page
        self._conflict_page = conflict_page

        self.setTitle(tr("ui.wizard.summary.title"))
        self.setSubTitle(tr("ui.wizard.summary.subtitle"))

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self._lbl_name = QLabel(self)
        self._lbl_side_a = QLabel(self)
        self._lbl_direction = QLabel(self)
        self._lbl_side_b = QLabel(self)
        self._lbl_conflict = QLabel(self)
        self._lbl_schedule = QLabel(self)
        self._lbl_filters = QLabel(self)
        self._lbl_max_delete = QLabel(self)

        for lbl in (
            self._lbl_name,
            self._lbl_side_a,
            self._lbl_direction,
            self._lbl_side_b,
            self._lbl_conflict,
            self._lbl_schedule,
            self._lbl_filters,
            self._lbl_max_delete,
        ):
            lbl.setStyleSheet("font-weight: bold;")

        form_layout.addRow(tr("ui.wizard.summary.name"), self._lbl_name)
        form_layout.addRow(tr("ui.wizard.summary.side_a"), self._lbl_side_a)
        form_layout.addRow(tr("ui.wizard.summary.direction"), self._lbl_direction)
        form_layout.addRow(tr("ui.wizard.summary.side_b"), self._lbl_side_b)
        form_layout.addRow(tr("ui.wizard.summary.conflict"), self._lbl_conflict)
        form_layout.addRow(tr("ui.wizard.summary.schedule"), self._lbl_schedule)
        form_layout.addRow(tr("ui.wizard.summary.advanced_filters"), self._lbl_filters)
        form_layout.addRow(tr("ui.wizard.summary.advanced_max_delete"), self._lbl_max_delete)

        layout.addLayout(form_layout)

        # Advanced options button
        adv_btn_layout = QHBoxLayout()
        self._btn_advanced = QPushButton(tr("ui.wizard.btn_advanced"), self)
        self._btn_advanced.setIcon(get_icon("preferences-other"))
        self._btn_advanced.clicked.connect(self._on_open_advanced)
        adv_btn_layout.addWidget(self._btn_advanced)
        adv_btn_layout.addStretch()
        layout.addLayout(adv_btn_layout)

        layout.addStretch()

    def initializePage(self) -> None:
        self._lbl_name.setText(self._name_page.profile_name())

        endpoint_a = self._side_a_page.picker.get_endpoint()
        self._lbl_side_a.setText(endpoint_a.to_rclone() if endpoint_a else "—")

        direction = self._direction_page.sync_direction()
        dir_labels = {
            SyncDirection.BIDIRECTIONAL: "↔ " + tr("ui.wizard.direction.bidirectional"),
            SyncDirection.A_TO_B: "→ " + tr("ui.wizard.direction.a_to_b"),
            SyncDirection.B_TO_A: "← " + tr("ui.wizard.direction.b_to_a"),
        }
        self._lbl_direction.setText(dir_labels.get(direction, str(direction)))

        endpoint_b = self._side_b_page.picker.get_endpoint()
        self._lbl_side_b.setText(endpoint_b.to_rclone() if endpoint_b else "—")

        conflict = self._conflict_page.conflict_policy()
        conflict_labels = {
            ConflictPolicy.KEEP_BOTH: tr("ui.wizard.conflict.keep_both"),
            ConflictPolicy.NEWER: tr("ui.wizard.conflict.newer"),
            ConflictPolicy.LARGER: tr("ui.wizard.conflict.larger"),
            ConflictPolicy.PATH1: tr("ui.wizard.conflict.path1"),
            ConflictPolicy.PATH2: tr("ui.wizard.conflict.path2"),
        }
        self._lbl_conflict.setText(conflict_labels.get(conflict, str(conflict)))
        self._lbl_schedule.setText(tr("ui.wizard.schedule.manual"))

        wizard = self.wizard()
        if isinstance(wizard, ProfileWizard):
            opts = wizard.custom_options
            self._lbl_filters.setText(
                tr(
                    "ui.wizard.summary.advanced_filters_val",
                    excludes=len(opts.excludes),
                    includes=len(opts.includes),
                )
            )
            self._lbl_max_delete.setText(f"{opts.max_delete_percent}%")

    def _on_open_advanced(self) -> None:
        """Open the advanced options dialog and preserve user edits in the wizard."""
        from pontis.domain.models import Endpoint

        wizard = self.wizard()
        if not isinstance(wizard, ProfileWizard):
            return

        name = self._name_page.profile_name()
        side_a = self._side_a_page.picker.get_endpoint() or Endpoint.local("/tmp")
        side_b = self._side_b_page.picker.get_endpoint() or Endpoint.local("/tmp")
        direction = self._direction_page.sync_direction()
        conflict = self._conflict_page.conflict_policy()

        opts_data = wizard.custom_options.to_dict()
        opts_data["direction"] = direction.value
        opts_data["conflict_policy"] = conflict.value
        temp_opts = SyncOptions.from_dict(opts_data)

        temp_profile = SyncProfile(
            name=name,
            side_a=side_a,
            side_b=side_b,
            options=temp_opts,
            id=wizard._profile.id if wizard._profile else None,
        )

        dialog = AdvancedOptionsDialog(
            profile=temp_profile,
            parent=self,
            rclone_binary=wizard._remote_service.binary,
            rclone_config=wizard._remote_service.config_path,
        )
        if dialog.exec():
            wizard.custom_options = dialog.get_options()
            # If conflict was modified in the dialog, reflect it on the conflict page
            self._conflict_page.set_conflict_policy(wizard.custom_options.conflict_policy)
            self.initializePage()


class ProfileWizard(QWizard):
    """Wizard for creating and editing sync profiles."""

    saved_profile: SyncProfile | None = None

    def __init__(
        self,
        service: ProfileService,
        remote_service: RemoteService,
        profile: SyncProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._remote_service = remote_service
        self._profile = profile
        self.saved_profile: SyncProfile | None = None
        self.custom_options: SyncOptions = profile.options if profile is not None else SyncOptions()

        if profile is not None:
            self.setWindowTitle(tr("ui.wizard.title_edit", name=profile.name))
        else:
            self.setWindowTitle(tr("ui.wizard.title_new"))

        self.resize(680, 520)
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)

        self.setButtonText(QWizard.WizardButton.BackButton, tr("ui.wizard.btn_back"))
        self.setButtonText(QWizard.WizardButton.NextButton, tr("ui.wizard.btn_next"))
        self.setButtonText(QWizard.WizardButton.FinishButton, tr("ui.wizard.btn_finish"))
        self.setButtonText(QWizard.WizardButton.CancelButton, tr("ui.wizard.btn_cancel"))

        self._init_pages()

    def _init_pages(self) -> None:
        self.page_name = ProfileNamePage(
            service=self._service, current_profile=self._profile, parent=self
        )
        self.page_side_a = SideAPage(
            remote_service=self._remote_service, current_profile=self._profile, parent=self
        )
        self.page_side_b = SideBPage(
            remote_service=self._remote_service,
            side_a_page=self.page_side_a,
            current_profile=self._profile,
            parent=self,
        )
        self.page_direction = DirectionPage(current_profile=self._profile, parent=self)
        self.page_conflict = ConflictPolicyPage(current_profile=self._profile, parent=self)
        self.page_summary = SummaryPage(
            name_page=self.page_name,
            side_a_page=self.page_side_a,
            side_b_page=self.page_side_b,
            direction_page=self.page_direction,
            conflict_page=self.page_conflict,
            parent=self,
        )

        self.addPage(self.page_name)
        self.addPage(self.page_side_a)
        self.addPage(self.page_side_b)
        self.addPage(self.page_direction)
        self.addPage(self.page_conflict)
        self.addPage(self.page_summary)

    def accept(self) -> None:
        """Persist profile upon Finish."""
        name = self.page_name.profile_name()
        side_a = self.page_side_a.picker.get_endpoint()
        side_b = self.page_side_b.picker.get_endpoint()
        direction = self.page_direction.sync_direction()
        conflict = self.page_conflict.conflict_policy()

        assert side_a is not None
        assert side_b is not None

        opts_data = self.custom_options.to_dict()
        opts_data["direction"] = direction.value
        opts_data["conflict_policy"] = conflict.value
        final_options = SyncOptions.from_dict(opts_data)

        if self._profile is not None:
            # Edit mode: update existing options and fields
            self._profile.name = name
            self._profile.side_a = side_a
            self._profile.side_b = side_b
            self._profile.options = final_options
            self.saved_profile = self._service.update_profile(self._profile)
        else:
            # Create mode
            new_profile = SyncProfile(
                name=name,
                side_a=side_a,
                side_b=side_b,
                options=final_options,
                schedule=Schedule(kind=ScheduleKind.MANUAL),
            )
            self.saved_profile = self._service.add_profile(new_profile)

        super().accept()
