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
