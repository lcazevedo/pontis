# SPDX-License-Identifier: GPL-3.0-or-later
"""Message catalog (pt_BR and en) for both CLI and GUI strings.

All user-facing text goes through :func:`tr` so no string is hard-coded at
the call site.
"""

from __future__ import annotations

import os

DEFAULT_LANGUAGE = "en"
_OVERRIDE_LANG: str | None = None

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        # Profile CLI messages
        "profile.added": "Profile '{name}' created (id {id}).",
        "profile.duplicate": "A profile named '{name}' already exists.",
        "profile.removed": "Profile '{name}' removed.",
        "profile.not_found": "Profile '{name}' not found.",
        "profile.none": "No profiles yet. Create one with 'pontis profile add'.",
        "profile.invalid": "Invalid profile: {error}",
        "profile.direction.bidirectional": "<->",
        "profile.direction.a_to_b": "->",
        "profile.direction.b_to_a": "<-",
        # Run CLI messages
        "run.starting": "Running '{name}'{mode}...",
        "run.mode_dry": " (dry run)",
        "run.first_sync": "First run: a safe initial --resync will be performed.",
        "run.success": "Finished: {transferred} transferred, {deleted} deleted, {errors} errors.",
        "run.success_dry": "Dry run finished: {transferred} to copy, {deleted} to delete.",
        "run.failed": "Run failed:\n{message}",
        "run.needs_resync": (
            "bisync reports that it needs a --resync to recover. Pontis never does this "
            "automatically; review both folders (and make a backup) first."
        ),
        "run.cancelled": "Run cancelled.",
        "run.locked": "Profile '{name}' is already running.",
        "run.missing_dir": "Local folder not found: {path}. Is the disk mounted?",
        "run.first_dry_required": (
            "First run of '{name}': run 'pontis run \"{name}\" --dry-run' first and review "
            "the result."
        ),
        # Rclone messages
        "rclone.not_found": (
            "rclone was not found. Install it (https://rclone.org/install/) or pass --rclone."
        ),
        "rclone.too_old": "rclone {found} is too old; version {minimum} or newer is required.",
        "rclone.config_missing": "rclone config file not found: {path}",
        "error.flag": "Invalid option: {error}",
        # Remote messages
        "remote.none": (
            "No cloud remotes configured yet. Add one with 'pontis remote add' or "
            "'pontis remote import'."
        ),
        "remote.added": "Remote '{name}' ({type}) configured successfully.",
        "remote.duplicate": "A remote named '{name}' already exists.",
        "remote.removed": "Remote '{name}' removed.",
        "remote.not_found": "Remote '{name}' not found.",
        "remote.invalid_name": (
            "Invalid remote name '{name}'. Names must start with an alphanumeric character "
            "and contain no colons."
        ),
        "remote.operation_failed": "Remote operation failed: {error}",
        "remote.test_success": "Remote '{name}': connected successfully.",
        "remote.test_success_storage": (
            "Remote '{name}': connected successfully (Total: {total}, Used: {used}, Free: {free})."
        ),
        "remote.test_failed": "Remote '{name}': connection test failed.\n{message}",
        "remote.imported": "Successfully imported {count} remote(s): {names}",
        "remote.import_none": "No remotes were imported.",
        "remote.import_source_not_found": "Source config file not found: {path}",
        "remote.password_set": "Configuration password stored in the system keyring.",
        "remote.password_removed": "Configuration password removed from the system keyring.",
        "remote.password_status_set": (
            "A configuration password is currently stored in the keyring."
        ),
        "remote.password_status_not_set": "No configuration password stored in the keyring.",
        # GUI: Main Window
        "ui.app.name": "Pontis",
        "ui.main.title": "Pontis — Two-Way File Sync",
        "ui.menu.file": "File",
        "ui.menu.profile": "Profile",
        "ui.menu.view": "View",
        "ui.menu.help": "Help",
        # GUI: Actions
        "ui.actions.new": "New Profile",
        "ui.actions.new.tooltip": "Create a new sync profile",
        "ui.actions.edit": "Edit",
        "ui.actions.edit.tooltip": "Edit the selected sync profile",
        "ui.actions.delete": "Delete",
        "ui.actions.delete.tooltip": "Delete the selected sync profile",
        "ui.actions.refresh": "Refresh",
        "ui.actions.refresh.tooltip": "Reload profiles from database",
        "ui.actions.theme": "Theme",
        "ui.actions.theme.light": "Light Theme",
        "ui.actions.theme.dark": "Dark Theme",
        "ui.actions.theme.system": "System Theme",
        "ui.actions.quit": "Quit",
        "ui.actions.quit.tooltip": "Exit the application",
        # GUI: Table Headers
        "ui.table.header.name": "Name",
        "ui.table.header.source": "Source (Side A)",
        "ui.table.header.direction": "Direction",
        "ui.table.header.destination": "Destination (Side B)",
        "ui.table.header.last_run": "Last Run",
        "ui.table.header.status": "Status",
        # GUI: Run Status
        "ui.status.never_run": "Never executed",
        "ui.status.running": "Running...",
        "ui.status.success": "Success",
        "ui.status.error": "Error",
        "ui.status.cancelled": "Cancelled",
        "ui.status.dry_run_tag": " (dry run)",
        # GUI: Empty State
        "ui.empty.title": "No sync profiles configured",
        "ui.empty.subtitle": (
            "Create a profile to sync files between local directories and cloud storage."
        ),
        "ui.empty.action_button": "Create Profile",
        "ui.empty.cli_hint": (
            "Tip: You can also manage profiles from the terminal with 'pontis profile add'."
        ),
        # GUI: Dialogs
        "ui.dialog.delete.title": "Delete Profile",
        "ui.dialog.delete.confirm": (
            "Are you sure you want to delete profile '{name}'?\n\n"
            "This removes the sync configuration from Pontis. "
            "No files in your local or remote folders will be touched."
        ),
        "ui.dialog.coming_soon.title": "Feature Coming Soon",
        "ui.dialog.coming_soon.message": (
            "The visual profile creation wizard will arrive in Part 5.\n\n"
            "In the meantime, you can create profiles via the CLI:\n"
            "pontis profile add <name> --a <path> --b <path>"
        ),
        # GUI: Statusbar
        "ui.statusbar.ready": "Ready",
        "ui.statusbar.profiles_count": "{count} profile(s)",
        "ui.statusbar.profile_deleted": "Profile '{name}' deleted.",
        "ui.statusbar.profile_created": "Profile '{name}' created.",
        "ui.statusbar.profile_updated": "Profile '{name}' updated.",
        # GUI: Profile Wizard
        "ui.wizard.title_new": "New Sync Profile",
        "ui.wizard.title_edit": "Edit Profile: {name}",
        "ui.wizard.btn_back": "< Back",
        "ui.wizard.btn_next": "Next >",
        "ui.wizard.btn_finish": "Finish",
        "ui.wizard.btn_cancel": "Cancel",
        "ui.wizard.name.title": "Profile Identification",
        "ui.wizard.name.subtitle": "Choose a unique name for this sync profile.",
        "ui.wizard.name.label": "Profile Name:",
        "ui.wizard.name.placeholder": "e.g., Work Documents",
        "ui.wizard.name.error_empty": "Profile name cannot be empty.",
        "ui.wizard.name.error_duplicate": "A profile with this name already exists.",
        "ui.wizard.side_a.title": "Side A (Source / Folder 1)",
        "ui.wizard.side_a.subtitle": (
            "Select whether Side A is a local directory or a cloud remote."
        ),
        "ui.wizard.side_b.title": "Side B (Destination / Folder 2)",
        "ui.wizard.side_b.subtitle": (
            "Select whether Side B is a local directory or a cloud remote."
        ),
        "ui.wizard.side_b.error_same": "Side A and Side B cannot point to the exact same location.",
        "ui.endpoint.kind_local": "Local Folder",
        "ui.endpoint.kind_remote": "Cloud Storage (Remote)",
        "ui.endpoint.local_path": "Local Path:",
        "ui.endpoint.browse_local": "Browse...",
        "ui.endpoint.remote_name": "Cloud Remote:",
        "ui.endpoint.remote_path": "Folder inside Remote:",
        "ui.endpoint.browse_remote": "Browse Cloud...",
        "ui.endpoint.no_remotes": (
            "No cloud remotes configured yet. "
            "Use 'pontis remote add' in the terminal to configure one."
        ),
        "ui.endpoint.error_no_local_path": "Please select a local path.",
        "ui.endpoint.error_no_remote": "Please select a cloud remote.",
        "ui.endpoint.dialog_select_local": "Select Local Folder",
        "ui.wizard.direction.title": "Sync Direction",
        "ui.wizard.direction.subtitle": "Select how files should flow between Side A and Side B.",
        "ui.wizard.direction.bidirectional": "Two-Way / Bidirectional (↔)",
        "ui.wizard.direction.bidirectional_desc": (
            "Recommended: changes on either side are replicated to the other."
        ),
        "ui.wizard.direction.a_to_b": "One-Way: Side A to Side B (→)",
        "ui.wizard.direction.a_to_b_desc": (
            "Mirror changes from Side A to Side B. Side B changes will not affect Side A."
        ),
        "ui.wizard.direction.b_to_a": "One-Way: Side B to Side A (←)",
        "ui.wizard.direction.b_to_a_desc": (
            "Mirror changes from Side B to Side A. Side A changes will not affect Side B."
        ),
        "ui.wizard.conflict.title": "Conflict Resolution & Scheduling",
        "ui.wizard.conflict.subtitle": (
            "Choose how to handle files modified simultaneously on both sides."
        ),
        "ui.wizard.conflict.group": "Conflict Policy",
        "ui.wizard.conflict.keep_both": "Keep both versions (safer, adds .conflict suffix)",
        "ui.wizard.conflict.newer": "Keep the most recently modified file",
        "ui.wizard.conflict.larger": "Keep the larger file",
        "ui.wizard.conflict.path1": "Keep Side A version",
        "ui.wizard.conflict.path2": "Keep Side B version",
        "ui.wizard.schedule.group": "Execution Schedule",
        "ui.wizard.schedule.manual": "Manual execution only (default)",
        "ui.wizard.schedule.interval": "Run periodically (coming soon)",
        "ui.wizard.schedule.notice": (
            "Automatic background scheduling is reserved for future versions. "
            "In v1, sync runs on demand."
        ),
        "ui.wizard.summary.title": "Configuration Summary",
        "ui.wizard.summary.subtitle": "Review the profile settings before saving.",
        "ui.wizard.summary.name": "Profile Name:",
        "ui.wizard.summary.side_a": "Side A:",
        "ui.wizard.summary.direction": "Direction:",
        "ui.wizard.summary.side_b": "Side B:",
        "ui.wizard.summary.conflict": "Conflict Policy:",
        "ui.wizard.summary.schedule": "Schedule:",
        # GUI: Cloud Browser
        "ui.cloud_browser.title": "Browse Cloud Remote",
        "ui.cloud_browser.remote": "Remote:",
        "ui.cloud_browser.path": "Current Path:",
        "ui.cloud_browser.root": "(Root folder)",
        "ui.cloud_browser.up": "Up",
        "ui.cloud_browser.refresh": "Refresh",
        "ui.cloud_browser.new_folder": "New Folder",
        "ui.cloud_browser.select_current": "Select Current Folder",
        "ui.cloud_browser.loading": "Loading cloud folders, please wait...",
        "ui.cloud_browser.empty": "No subdirectories found.",
        "ui.cloud_browser.error": "Could not list directories: {error}",
        "ui.cloud_browser.new_folder_title": "Create Folder",
        "ui.cloud_browser.new_folder_prompt": "Folder name:",
        # GUI: Advanced Options
        "ui.actions.advanced_options": "Advanced Options...",
        "ui.actions.advanced_options.tooltip": (
            "Configure filters, limits, and advanced rclone flags"
        ),
        "ui.wizard.btn_advanced": "Advanced Options...",
        "ui.statusbar.options_saved": "Advanced options saved for '{name}'.",
        "ui.advanced.title": "Advanced Options — {name}",
        "ui.advanced.title_generic": "Advanced Options",
        "ui.advanced.header_endpoints": "{side_a} {direction} {side_b}",
        "ui.advanced.tab_filters": "Filters",
        "ui.advanced.tab_safety": "Safety & Conflict",
        "ui.advanced.tab_performance": "Performance & Network",
        "ui.advanced.tab_flags": "Custom Flags",
        "ui.advanced.filters.excludes_group": "Exclude Patterns (--exclude)",
        "ui.advanced.filters.excludes_desc": (
            "Files or patterns matching these rules will be ignored during synchronization."
        ),
        "ui.advanced.filters.includes_group": "Include Patterns (--include)",
        "ui.advanced.filters.includes_desc": "Only include files matching these patterns.",
        "ui.advanced.filters.placeholder": "e.g. *.tmp, sync.sh, **/node_modules/**",
        "ui.advanced.filters.btn_add": "Add",
        "ui.advanced.filters.btn_remove": "Remove",
        "ui.advanced.filters.btn_clear": "Clear All",
        "ui.advanced.filters.empty_excludes": "No exclude patterns defined.",
        "ui.advanced.filters.empty_includes": "No include patterns defined (all files included).",
        "ui.advanced.safety.conflict_group": "Conflict Resolution Policy",
        "ui.advanced.safety.conflict_policy": "Conflict policy:",
        "ui.advanced.safety.max_delete_group": "Safety Deletion Threshold (--max-delete)",
        "ui.advanced.safety.max_delete_label": "Max deletion percentage:",
        "ui.advanced.safety.max_delete_desc": (
            "Abort the sync if more than {percent}% of files would be deleted "
            "(prevents accidental mass deletion)."
        ),
        "ui.advanced.safety.check_access": (
            "Verify access integrity with test file (--check-access)"
        ),
        "ui.advanced.safety.check_access_desc": (
            "Creates and validates temporary RCLONE_TEST files on both sides before running bisync."
        ),
        "ui.advanced.performance.bwlimit_group": "Bandwidth Limitation (--bwlimit)",
        "ui.advanced.performance.bwlimit_label": "Bandwidth limit:",
        "ui.advanced.performance.bwlimit_placeholder": (
            "e.g. 10M, 500k, 10M:off (leave empty for unlimited)"
        ),
        "ui.advanced.performance.bwlimit_desc": (
            "Throttle network transfer speed (e.g., '10M' for 10 MByte/s, '500k' for 500 kByte/s)."
        ),
        "ui.advanced.performance.bwlimit_invalid": (
            "Invalid bandwidth limit format. Examples: 10M, 500k, 10M:off"
        ),
        "ui.advanced.performance.transfers_group": "Parallel Transfers (--transfers)",
        "ui.advanced.performance.transfers_enable": "Specify custom parallel transfers limit",
        "ui.advanced.performance.transfers_label": "Parallel transfers:",
        "ui.advanced.performance.transfers_desc": (
            "Number of file transfers to run concurrently (rclone default is 4)."
        ),
        "ui.advanced.flags.group": "Free-Form Rclone Flags",
        "ui.advanced.flags.desc": (
            "Additional rclone command-line arguments (one per line or separated by spaces)."
        ),
        "ui.advanced.flags.placeholder": "e.g. --fast-list\n--drive-skip-gdocs",
        "ui.advanced.flags.forbidden_warning": (
            "Flag '{flag}' is managed internally by Pontis and cannot be specified manually."
        ),
        "ui.advanced.flags.invalid_warning": "Each flag must start with '-' or '--'.",
        "ui.advanced.preview.title": "Command Preview",
        "ui.advanced.preview.dry_run": "Simulate dry-run (--dry-run)",
        "ui.advanced.preview.first_run": "Simulate initial sync (--resync)",
        "ui.advanced.preview.btn_copy": "Copy Command",
        "ui.advanced.preview.copied": "Copied!",
        "ui.advanced.btn_save": "Save Options",
        "ui.advanced.btn_cancel": "Cancel",
        "ui.advanced.btn_reset": "Reset to Defaults",
        "ui.advanced.reset_confirm": (
            "Are you sure you want to reset all advanced options to defaults?"
        ),
        "ui.wizard.summary.advanced_filters": "Filters:",
        "ui.wizard.summary.advanced_filters_val": "{excludes} exclude(s), {includes} include(s)",
        "ui.wizard.summary.advanced_max_delete": "Max Delete:",
        # GUI: Run Actions
        "ui.actions.sync_now": "Sync Now",
        "ui.actions.sync_now.tooltip": "Run synchronization for the selected profile",
        "ui.actions.dry_run": "Simulate (Dry Run)",
        "ui.actions.dry_run.tooltip": "Simulate synchronization without making changes",
        # GUI: First Run Dialog
        "ui.dialog.first_run.title": "First Run — Safety Simulation",
        "ui.dialog.first_run.message": (
            "This is the first time profile '{name}' is being synchronized.\n\n"
            "For your safety, Pontis will first run a simulation (--dry-run) to show what will "
            "change before any files are modified."
        ),
        "ui.dialog.first_run.btn_continue": "Run Simulation",
        "ui.dialog.first_run.btn_cancel": "Cancel",
        # GUI: Progress Dialog
        "ui.progress.title_sync": "Synchronizing: {name}",
        "ui.progress.title_dry_run": "Simulating: {name}",
        "ui.progress.badge_sync": "SYNCHRONIZATION",
        "ui.progress.badge_dry_run": "SIMULATION (DRY RUN)",
        "ui.progress.status_starting": "Starting sync engine...",
        "ui.progress.status_comparing": "Comparing files and detecting changes...",
        "ui.progress.status_transferring": "Transferring files...",
        "ui.progress.status_success": "Completed successfully",
        "ui.progress.status_success_dry": "Simulation completed",
        "ui.progress.status_cancelled": "Cancelled by user",
        "ui.progress.status_error": "Synchronization failed",
        "ui.progress.metric_transfers": "Transferred",
        "ui.progress.metric_planned_transfers": "To Transfer",
        "ui.progress.metric_deletes": "Deleted",
        "ui.progress.metric_planned_deletes": "To Delete",
        "ui.progress.metric_errors": "Errors",
        "ui.progress.metric_speed": "Speed",
        "ui.progress.metric_bytes": "Data",
        "ui.progress.log_section": "Execution Log:",
        "ui.progress.btn_cancel": "Cancel",
        "ui.progress.btn_close": "Close",
        "ui.progress.btn_show_summary": "View Summary & Apply...",
        "ui.progress.cancel_confirm": (
            "Are you sure you want to cancel the active synchronization?"
        ),
        "ui.progress.cancelling": "Cancelling...",
        # GUI: Dry Run Summary
        "ui.dry_run.title": "Simulation Summary — {name}",
        "ui.dry_run.subtitle": "No files have been modified. Review the planned changes below.",
        "ui.dry_run.tab_copies": "Copies / Transfers ({count})",
        "ui.dry_run.tab_deletes": "Deletions ({count})",
        "ui.dry_run.empty_copies": "No files need to be copied.",
        "ui.dry_run.empty_deletes": "No files will be deleted.",
        "ui.dry_run.mass_delete_warning": (
            "Warning: {count} file(s) are planned to be permanently deleted!"
        ),
        "ui.dry_run.mass_delete_confirm": (
            "I have reviewed the files and confirm that these deletions are intended."
        ),
        "ui.dry_run.btn_apply": "Run Real Synchronization Now",
        "ui.dry_run.btn_cancel": "Close",
        # GUI: Notifications
        "ui.notify.sync_success_title": "Pontis — Sync Completed",
        "ui.notify.sync_success_msg": "{name}: {count} file(s) transferred successfully.",
        "ui.notify.dry_success_title": "Pontis — Simulation Completed",
        "ui.notify.dry_success_msg": "{name}: {count} file(s) would be modified.",
        "ui.notify.error_title": "Pontis — Synchronization Failed",
        "ui.notify.error_msg": "{name}: an error occurred during synchronization.",
        # GUI: Alerts
        "ui.alert.already_running": "Profile '{name}' is already currently running.",
        "ui.alert.endpoint_missing": (
            "Local folder not found: {path}\n"
            "Please check if the folder exists and if any external drive is connected."
        ),
    },
    "pt_BR": {
        # Profile CLI messages
        "profile.added": "Perfil '{name}' criado (id {id}).",
        "profile.duplicate": "Já existe um perfil chamado '{name}'.",
        "profile.removed": "Perfil '{name}' removido.",
        "profile.not_found": "Perfil '{name}' não encontrado.",
        "profile.none": "Nenhum perfil ainda. Crie um com 'pontis profile add'.",
        "profile.invalid": "Perfil inválido: {error}",
        "profile.direction.bidirectional": "<->",
        "profile.direction.a_to_b": "->",
        "profile.direction.b_to_a": "<-",
        # Run CLI messages
        "run.starting": "Executando '{name}'{mode}...",
        "run.mode_dry": " (simulação)",
        "run.first_sync": "Primeira execução: será feito um --resync inicial seguro.",
        "run.success": (
            "Concluído: {transferred} transferidos, {deleted} excluídos, {errors} erros."
        ),
        "run.success_dry": "Simulação concluída: {transferred} a copiar, {deleted} a excluir.",
        "run.failed": "A execução falhou:\n{message}",
        "run.needs_resync": (
            "O bisync informa que precisa de um --resync para se recuperar. O Pontis nunca "
            "faz isso automaticamente; confira as duas pastas (e faça backup) antes."
        ),
        "run.cancelled": "Execução cancelada.",
        "run.locked": "O perfil '{name}' já está em execução.",
        "run.missing_dir": "Pasta local não encontrada: {path}. O disco está montado?",
        "run.first_dry_required": (
            "Primeira execução de '{name}': rode antes 'pontis run \"{name}\" --dry-run' e "
            "confira o resultado."
        ),
        # Rclone messages
        "rclone.not_found": (
            "rclone não encontrado. Instale-o (https://rclone.org/install/) ou use --rclone."
        ),
        "rclone.too_old": (
            "rclone {found} é antigo demais; é preciso a versão {minimum} ou mais nova."
        ),
        "rclone.config_missing": "Arquivo de configuração do rclone não encontrado: {path}",
        "error.flag": "Opção inválida: {error}",
        # Remote messages
        "remote.none": (
            "Nenhum remoto em nuvem configurado ainda. Adicione um com 'pontis remote add' ou "
            "'pontis remote import'."
        ),
        "remote.added": "Remoto '{name}' ({type}) configurado com sucesso.",
        "remote.duplicate": "Já existe um remoto chamado '{name}'.",
        "remote.removed": "Remoto '{name}' removido.",
        "remote.not_found": "Remoto '{name}' não encontrado.",
        "remote.invalid_name": (
            "Nome de remoto inválido '{name}'. Nomes devem começar com letra/número e não conter "
            "dois-pontos."
        ),
        "remote.operation_failed": "Operação de remoto falhou: {error}",
        "remote.test_success": "Remoto '{name}': conexão bem-sucedida.",
        "remote.test_success_storage": (
            "Remoto '{name}': conexão bem-sucedida (Total: {total}, Usado: {used}, Livre: {free})."
        ),
        "remote.test_failed": "Remoto '{name}': o teste de conexão falhou.\n{message}",
        "remote.imported": "{count} remoto(s) importado(s) com sucesso: {names}",
        "remote.import_none": "Nenhum remoto foi importado.",
        "remote.import_source_not_found": (
            "Arquivo de configuração de origem não encontrado: {path}"
        ),
        "remote.password_set": "Senha de configuração salva no chaveiro do sistema.",
        "remote.password_removed": "Senha de configuração removida do chaveiro do sistema.",
        "remote.password_status_set": (
            "Uma senha de configuração está atualmente salva no chaveiro."
        ),
        "remote.password_status_not_set": "Nenhuma senha de configuração salva no chaveiro.",
        # GUI: Main Window
        "ui.app.name": "Pontis",
        "ui.main.title": "Pontis — Sincronização Bidirecional de Arquivos",
        "ui.menu.file": "Arquivo",
        "ui.menu.profile": "Perfil",
        "ui.menu.view": "Exibir",
        "ui.menu.help": "Ajuda",
        # GUI: Actions
        "ui.actions.new": "Novo Perfil",
        "ui.actions.new.tooltip": "Criar um novo perfil de sincronização",
        "ui.actions.edit": "Editar",
        "ui.actions.edit.tooltip": "Editar o perfil de sincronização selecionado",
        "ui.actions.delete": "Excluir",
        "ui.actions.delete.tooltip": "Excluir o perfil de sincronização selecionado",
        "ui.actions.refresh": "Atualizar",
        "ui.actions.refresh.tooltip": "Recarregar perfis do banco de dados",
        "ui.actions.theme": "Tema",
        "ui.actions.theme.light": "Tema Claro",
        "ui.actions.theme.dark": "Tema Escuro",
        "ui.actions.theme.system": "Tema do Sistema",
        "ui.actions.quit": "Sair",
        "ui.actions.quit.tooltip": "Fechar o Pontis",
        # GUI: Table Headers
        "ui.table.header.name": "Nome",
        "ui.table.header.source": "Origem (Lado A)",
        "ui.table.header.direction": "Direção",
        "ui.table.header.destination": "Destino (Lado B)",
        "ui.table.header.last_run": "Última Execução",
        "ui.table.header.status": "Status",
        # GUI: Run Status
        "ui.status.never_run": "Nunca executado",
        "ui.status.running": "Em execução...",
        "ui.status.success": "Sucesso",
        "ui.status.error": "Erro",
        "ui.status.cancelled": "Cancelado",
        "ui.status.dry_run_tag": " (simulação)",
        # GUI: Empty State
        "ui.empty.title": "Nenhum perfil de sincronização configurado",
        "ui.empty.subtitle": (
            "Crie um perfil para sincronizar arquivos entre pastas locais e armazenamento na nuvem."
        ),
        "ui.empty.action_button": "Criar Perfil",
        "ui.empty.cli_hint": (
            "Dica: você também pode gerenciar perfis pelo terminal com 'pontis profile add'."
        ),
        # GUI: Dialogs
        "ui.dialog.delete.title": "Excluir Perfil",
        "ui.dialog.delete.confirm": (
            "Tem certeza de que deseja excluir o perfil '{name}'?\n\n"
            "Isso remove a configuração de sincronização do Pontis. "
            "Nenhum arquivo local ou na nuvem será alterado."
        ),
        "ui.dialog.coming_soon.title": "Recurso em Breve",
        "ui.dialog.coming_soon.message": (
            "O assistente visual de criação de perfis estará disponível na Parte 5.\n\n"
            "Enquanto isso, você pode criar perfis pela linha de comando:\n"
            "pontis profile add <nome> --a <caminho> --b <caminho>"
        ),
        # GUI: Statusbar
        "ui.statusbar.ready": "Pronto",
        "ui.statusbar.profiles_count": "{count} perfil(is)",
        "ui.statusbar.profile_deleted": "Perfil '{name}' excluído.",
        "ui.statusbar.profile_created": "Perfil '{name}' criado com sucesso.",
        "ui.statusbar.profile_updated": "Perfil '{name}' atualizado com sucesso.",
        # GUI: Profile Wizard
        "ui.wizard.title_new": "Novo Perfil de Sincronização",
        "ui.wizard.title_edit": "Editar Perfil: {name}",
        "ui.wizard.btn_back": "< Voltar",
        "ui.wizard.btn_next": "Avançar >",
        "ui.wizard.btn_finish": "Concluir",
        "ui.wizard.btn_cancel": "Cancelar",
        "ui.wizard.name.title": "Identificação do Perfil",
        "ui.wizard.name.subtitle": "Escolha um nome único para este perfil de sincronização.",
        "ui.wizard.name.label": "Nome do Perfil:",
        "ui.wizard.name.placeholder": "ex: Documentos Trabalho",
        "ui.wizard.name.error_empty": "O nome do perfil não pode ficar em branco.",
        "ui.wizard.name.error_duplicate": "Já existe um perfil com este nome.",
        "ui.wizard.side_a.title": "Lado A (Origem / Pasta 1)",
        "ui.wizard.side_a.subtitle": (
            "Selecione se o Lado A é uma pasta local ou um remoto na nuvem."
        ),
        "ui.wizard.side_b.title": "Lado B (Destino / Pasta 2)",
        "ui.wizard.side_b.subtitle": (
            "Selecione se o Lado B é uma pasta local ou um remoto na nuvem."
        ),
        "ui.wizard.side_b.error_same": "O Lado A e o Lado B não podem apontar para o mesmo local.",
        "ui.endpoint.kind_local": "Pasta Local",
        "ui.endpoint.kind_remote": "Armazenamento em Nuvem (Remoto)",
        "ui.endpoint.local_path": "Caminho Local:",
        "ui.endpoint.browse_local": "Procurar...",
        "ui.endpoint.remote_name": "Remoto em Nuvem:",
        "ui.endpoint.remote_path": "Pasta no Remoto:",
        "ui.endpoint.browse_remote": "Navegar na Nuvem...",
        "ui.endpoint.no_remotes": (
            "Nenhum remoto em nuvem configurado. "
            "Use 'pontis remote add' no terminal para adicionar."
        ),
        "ui.endpoint.error_no_local_path": "Por favor selecione um caminho local.",
        "ui.endpoint.error_no_remote": "Por favor selecione um remoto em nuvem.",
        "ui.endpoint.dialog_select_local": "Selecionar Pasta Local",
        "ui.wizard.direction.title": "Direção de Sincronização",
        "ui.wizard.direction.subtitle": (
            "Escolha como os arquivos devem trafegar entre o Lado A e o Lado B."
        ),
        "ui.wizard.direction.bidirectional": "Bidirecional (↔)",
        "ui.wizard.direction.bidirectional_desc": (
            "Recomendado: alterações em qualquer um dos lados são refletidas no outro."
        ),
        "ui.wizard.direction.a_to_b": "Unidirecional: Lado A para Lado B (→)",
        "ui.wizard.direction.a_to_b_desc": (
            "Espelha alterações do Lado A para o Lado B. Alterações em B não afetam A."
        ),
        "ui.wizard.direction.b_to_a": "Unidirecional: Lado B para Lado A (←)",
        "ui.wizard.direction.b_to_a_desc": (
            "Espelha alterações do Lado B para o Lado A. Alterações em A não afetam B."
        ),
        "ui.wizard.conflict.title": "Resolução de Conflitos e Agendamento",
        "ui.wizard.conflict.subtitle": (
            "Escolha como tratar arquivos alterados simultaneamente nos dois lados."
        ),
        "ui.wizard.conflict.group": "Política de Conflito",
        "ui.wizard.conflict.keep_both": (
            "Manter ambas as versões (mais seguro, adiciona sufixo .conflict)"
        ),
        "ui.wizard.conflict.newer": "Manter o arquivo modificado mais recentemente",
        "ui.wizard.conflict.larger": "Manter o arquivo com maior tamanho",
        "ui.wizard.conflict.path1": "Manter a versão do Lado A",
        "ui.wizard.conflict.path2": "Manter a versão do Lado B",
        "ui.wizard.schedule.group": "Agendamento de Execução",
        "ui.wizard.schedule.manual": "Execução somente manual (padrão)",
        "ui.wizard.schedule.interval": "Executar periodicamente (em breve)",
        "ui.wizard.schedule.notice": (
            "O agendamento automático em segundo plano está reservado para versões futuras. "
            "Na v1, a sincronização é manual."
        ),
        "ui.wizard.summary.title": "Resumo da Configuração",
        "ui.wizard.summary.subtitle": "Revise as configurações do perfil antes de salvar.",
        "ui.wizard.summary.name": "Nome do Perfil:",
        "ui.wizard.summary.side_a": "Lado A:",
        "ui.wizard.summary.direction": "Direção:",
        "ui.wizard.summary.side_b": "Lado B:",
        "ui.wizard.summary.conflict": "Política de Conflito:",
        "ui.wizard.summary.schedule": "Agendamento:",
        # GUI: Cloud Browser
        "ui.cloud_browser.title": "Navegar na Nuvem",
        "ui.cloud_browser.remote": "Remoto:",
        "ui.cloud_browser.path": "Caminho Atual:",
        "ui.cloud_browser.root": "(Pasta raiz)",
        "ui.cloud_browser.up": "Subir",
        "ui.cloud_browser.refresh": "Atualizar",
        "ui.cloud_browser.new_folder": "Nova Pasta",
        "ui.cloud_browser.select_current": "Selecionar Esta Pasta",
        "ui.cloud_browser.loading": "Carregando pastas da nuvem, aguarde...",
        "ui.cloud_browser.empty": "Nenhuma subpasta encontrada.",
        "ui.cloud_browser.error": "Não foi possível listar as pastas: {error}",
        "ui.cloud_browser.new_folder_title": "Criar Pasta",
        "ui.cloud_browser.new_folder_prompt": "Nome da pasta:",
        # GUI: Advanced Options
        "ui.actions.advanced_options": "Opções Avançadas...",
        "ui.actions.advanced_options.tooltip": (
            "Configurar filtros, limites de segurança e flags do rclone"
        ),
        "ui.wizard.btn_advanced": "Opções Avançadas...",
        "ui.statusbar.options_saved": "Opções avançadas salvas para '{name}'.",
        "ui.advanced.title": "Opções Avançadas — {name}",
        "ui.advanced.title_generic": "Opções Avançadas",
        "ui.advanced.header_endpoints": "{side_a} {direction} {side_b}",
        "ui.advanced.tab_filters": "Filtros",
        "ui.advanced.tab_safety": "Segurança e Conflitos",
        "ui.advanced.tab_performance": "Desempenho e Rede",
        "ui.advanced.tab_flags": "Flags Livres",
        "ui.advanced.filters.excludes_group": "Padrões de Exclusão (--exclude)",
        "ui.advanced.filters.excludes_desc": (
            "Arquivos ou pastas correspondentes a estas regras serão ignorados "
            "durante a sincronização."
        ),
        "ui.advanced.filters.includes_group": "Padrões de Inclusão (--include)",
        "ui.advanced.filters.includes_desc": (
            "Incluir apenas arquivos correspondentes a estes padrões."
        ),
        "ui.advanced.filters.placeholder": "ex: *.tmp, sync.sh, **/node_modules/**",
        "ui.advanced.filters.btn_add": "Adicionar",
        "ui.advanced.filters.btn_remove": "Remover",
        "ui.advanced.filters.btn_clear": "Limpar Tudo",
        "ui.advanced.filters.empty_excludes": "Nenhum padrão de exclusão configurado.",
        "ui.advanced.filters.empty_includes": (
            "Nenhum padrão de inclusão configurado (todos os arquivos incluídos)."
        ),
        "ui.advanced.safety.conflict_group": "Política de Resolução de Conflitos",
        "ui.advanced.safety.conflict_policy": "Política de conflito:",
        "ui.advanced.safety.max_delete_group": "Limite de Exclusão de Segurança (--max-delete)",
        "ui.advanced.safety.max_delete_label": "Percentual máximo de exclusão:",
        "ui.advanced.safety.max_delete_desc": (
            "Interrompe a sincronização se mais de {percent}% dos arquivos forem apagados "
            "(protege contra perda acidental em massa)."
        ),
        "ui.advanced.safety.check_access": (
            "Verificar integridade do acesso com arquivo de teste (--check-access)"
        ),
        "ui.advanced.safety.check_access_desc": (
            "Cria e valida o arquivo temporário RCLONE_TEST em ambos os lados antes do bisync "
            "para assegurar que os dois lados estão operacionais."
        ),
        "ui.advanced.performance.bwlimit_group": "Limite de Largura de Banda (--bwlimit)",
        "ui.advanced.performance.bwlimit_label": "Limite de banda:",
        "ui.advanced.performance.bwlimit_placeholder": (
            "ex: 10M, 500k, 10M:off (deixe vazio para ilimitado)"
        ),
        "ui.advanced.performance.bwlimit_desc": (
            "Controla a taxa de transferência de rede "
            "(ex: '10M' para 10 MB/s, '500k' para 500 kB/s)."
        ),
        "ui.advanced.performance.bwlimit_invalid": (
            "Formato de limite de banda inválido. Exemplos: 10M, 500k, 10M:off"
        ),
        "ui.advanced.performance.transfers_group": "Transferências Paralelas (--transfers)",
        "ui.advanced.performance.transfers_enable": (
            "Personalizar limite de transferências paralelas"
        ),
        "ui.advanced.performance.transfers_label": "Transferências simultâneas:",
        "ui.advanced.performance.transfers_desc": (
            "Quantidade de transferências de arquivos simultâneas (o padrão do rclone é 4)."
        ),
        "ui.advanced.flags.group": "Flags Adicionais do Rclone",
        "ui.advanced.flags.desc": (
            "Parâmetros de linha de comando adicionais passados diretamente ao rclone "
            "(um por linha ou separados por espaço)."
        ),
        "ui.advanced.flags.placeholder": "ex: --fast-list\n--drive-skip-gdocs",
        "ui.advanced.flags.forbidden_warning": (
            "A flag '{flag}' é gerenciada internamente pelo Pontis e não pode ser especificada "
            "manualmente."
        ),
        "ui.advanced.flags.invalid_warning": "Cada flag deve começar com '-' ou '--'.",
        "ui.advanced.preview.title": "Pré-visualização do Comando",
        "ui.advanced.preview.dry_run": "Simular (--dry-run)",
        "ui.advanced.preview.first_run": "Simular primeira execução (--resync)",
        "ui.advanced.preview.btn_copy": "Copiar Comando",
        "ui.advanced.preview.copied": "Copiado!",
        "ui.advanced.btn_save": "Salvar Opções",
        "ui.advanced.btn_cancel": "Cancelar",
        "ui.advanced.btn_reset": "Restaurar Padrões",
        "ui.advanced.reset_confirm": (
            "Tem certeza que deseja restaurar todas as opções avançadas para os padrões?"
        ),
        "ui.wizard.summary.advanced_filters": "Filtros:",
        "ui.wizard.summary.advanced_filters_val": (
            "{excludes} exclusão(ões), {includes} inclusão(ões)"
        ),
        "ui.wizard.summary.advanced_max_delete": "Limite exclusão:",
        # GUI: Run Actions
        "ui.actions.sync_now": "Sincronizar Agora",
        "ui.actions.sync_now.tooltip": "Executar sincronização para o perfil selecionado",
        "ui.actions.dry_run": "Simular (--dry-run)",
        "ui.actions.dry_run.tooltip": "Simular a sincronização sem alterar arquivos",
        # GUI: First Run Dialog
        "ui.dialog.first_run.title": "Primeira Execução — Simulação de Segurança",
        "ui.dialog.first_run.message": (
            "Esta é a primeira vez que o perfil '{name}' será sincronizado.\n\n"
            "Por segurança, o Pontis realizará primeiro uma simulação (--dry-run) para mostrar o "
            "que mudará antes de modificar qualquer arquivo."
        ),
        "ui.dialog.first_run.btn_continue": "Iniciar Simulação",
        "ui.dialog.first_run.btn_cancel": "Cancelar",
        # GUI: Progress Dialog
        "ui.progress.title_sync": "Sincronizando: {name}",
        "ui.progress.title_dry_run": "Simulando: {name}",
        "ui.progress.badge_sync": "SINCRONIZAÇÃO",
        "ui.progress.badge_dry_run": "SIMULAÇÃO (--DRY-RUN)",
        "ui.progress.status_starting": "Iniciando motor de sincronização...",
        "ui.progress.status_comparing": "Comparando arquivos e detectando mudanças...",
        "ui.progress.status_transferring": "Transferindo arquivos...",
        "ui.progress.status_success": "Concluído com sucesso",
        "ui.progress.status_success_dry": "Simulação concluída",
        "ui.progress.status_cancelled": "Cancelado pelo usuário",
        "ui.progress.status_error": "Falha na sincronização",
        "ui.progress.metric_transfers": "Transferidos",
        "ui.progress.metric_planned_transfers": "A Transferir",
        "ui.progress.metric_deletes": "Excluídos",
        "ui.progress.metric_planned_deletes": "A Excluir",
        "ui.progress.metric_errors": "Erros",
        "ui.progress.metric_speed": "Velocidade",
        "ui.progress.metric_bytes": "Dados",
        "ui.progress.log_section": "Registro de Execução (Log):",
        "ui.progress.btn_cancel": "Cancelar",
        "ui.progress.btn_close": "Fechar",
        "ui.progress.btn_show_summary": "Ver Resumo e Aplicar...",
        "ui.progress.cancel_confirm": (
            "Tem certeza de que deseja cancelar a sincronização em andamento?"
        ),
        "ui.progress.cancelling": "Cancelando...",
        # GUI: Dry Run Summary
        "ui.dry_run.title": "Resumo da Simulação — {name}",
        "ui.dry_run.subtitle": (
            "Nenhum arquivo foi modificado ainda. Revise as alterações planejadas abaixo."
        ),
        "ui.dry_run.tab_copies": "Cópias / Transferências ({count})",
        "ui.dry_run.tab_deletes": "Exclusões ({count})",
        "ui.dry_run.empty_copies": "Nenhum arquivo precisa ser copiado.",
        "ui.dry_run.empty_deletes": "Nenhum arquivo será excluído.",
        "ui.dry_run.mass_delete_warning": (
            "Atenção: {count} arquivo(s) estão planejados para serem excluídos permanentemente!"
        ),
        "ui.dry_run.mass_delete_confirm": (
            "Revisei os arquivos e confirmo que estas exclusões são intencionais."
        ),
        "ui.dry_run.btn_apply": "Executar Sincronização Real Agora",
        "ui.dry_run.btn_cancel": "Fechar",
        # GUI: Notifications
        "ui.notify.sync_success_title": "Pontis — Sincronização Concluída",
        "ui.notify.sync_success_msg": "{name}: {count} arquivo(s) transferidos com sucesso.",
        "ui.notify.dry_success_title": "Pontis — Simulação Concluída",
        "ui.notify.dry_success_msg": "{name}: {count} arquivo(s) seriam alterados.",
        "ui.notify.error_title": "Pontis — Falha na Sincronização",
        "ui.notify.error_msg": "{name}: ocorreu um erro durante a sincronização.",
        # GUI: Alerts
        "ui.alert.already_running": "O perfil '{name}' já está em execução no momento.",
        "ui.alert.endpoint_missing": (
            "Pasta local não encontrada: {path}\n"
            "Por favor, verifique se a pasta existe e se o disco está conectado."
        ),
    },
}


def set_language(lang: str | None) -> None:
    """Explicitly set the active UI language (e.g. 'pt_BR' or 'en'), or reset."""
    global _OVERRIDE_LANG
    _OVERRIDE_LANG = lang


def current_language() -> str:
    """Return the active language ('pt_BR' or 'en')."""
    if _OVERRIDE_LANG is not None:
        return _OVERRIDE_LANG

    for var in ("PONTIS_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value.lower().startswith("pt"):
            return "pt_BR"
        if value:
            return "en"
    return DEFAULT_LANGUAGE


def tr(key: str, **params: object) -> str:
    """Return the message for ``key`` in the current language, formatted."""
    catalog = _CATALOG.get(current_language(), _CATALOG[DEFAULT_LANGUAGE])
    template = catalog.get(key) or _CATALOG[DEFAULT_LANGUAGE].get(key, key)
    try:
        return template.format(**params)
    except KeyError:
        return template
