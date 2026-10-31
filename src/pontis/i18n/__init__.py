# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal message catalog (pt_BR and en) for non-Qt code such as the CLI.

The Qt translation layer arrives with the GUI; until then all user-facing text
goes through :func:`tr` so no string is hard-coded at the call site.
"""

from __future__ import annotations

import os

DEFAULT_LANGUAGE = "en"

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "profile.added": "Profile '{name}' created (id {id}).",
        "profile.duplicate": "A profile named '{name}' already exists.",
        "profile.removed": "Profile '{name}' removed.",
        "profile.not_found": "Profile '{name}' not found.",
        "profile.none": "No profiles yet. Create one with 'pontis profile add'.",
        "profile.invalid": "Invalid profile: {error}",
        "profile.direction.bidirectional": "<->",
        "profile.direction.a_to_b": "->",
        "profile.direction.b_to_a": "<-",
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
        "rclone.not_found": (
            "rclone was not found. Install it (https://rclone.org/install/) or pass --rclone."
        ),
        "rclone.too_old": "rclone {found} is too old; version {minimum} or newer is required.",
        "rclone.config_missing": "rclone config file not found: {path}",
        "error.flag": "Invalid option: {error}",
    },
    "pt_BR": {
        "profile.added": "Perfil '{name}' criado (id {id}).",
        "profile.duplicate": "Já existe um perfil chamado '{name}'.",
        "profile.removed": "Perfil '{name}' removido.",
        "profile.not_found": "Perfil '{name}' não encontrado.",
        "profile.none": "Nenhum perfil ainda. Crie um com 'pontis profile add'.",
        "profile.invalid": "Perfil inválido: {error}",
        "profile.direction.bidirectional": "<->",
        "profile.direction.a_to_b": "->",
        "profile.direction.b_to_a": "<-",
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
        "rclone.not_found": (
            "rclone não encontrado. Instale-o (https://rclone.org/install/) ou use --rclone."
        ),
        "rclone.too_old": (
            "rclone {found} é antigo demais; é preciso a versão {minimum} ou mais nova."
        ),
        "rclone.config_missing": "Arquivo de configuração do rclone não encontrado: {path}",
        "error.flag": "Opção inválida: {error}",
    },
}


def current_language() -> str:
    """Pick ``pt_BR`` or ``en`` from the environment locale."""
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
    template = catalog.get(key) or _CATALOG[DEFAULT_LANGUAGE][key]
    return template.format(**params)
