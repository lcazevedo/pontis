# Pontis v1.0.0 — Release Notes & Announcement Drafts

---

## 1. GitHub Release Notes (`v1.0.0`)

**Pontis v1.0.0** is the first stable Linux release of Pontis — a desktop application (Python/PySide6) for safe bidirectional folder synchronization powered by **rclone** (`>= 1.66.0`).

### Highlights
- **Bidirectional (`rclone bisync`) & One-Way (`rclone sync`) Profiles:** Step-by-step wizard with local and cloud folder browsing, plus `--include`/`--exclude` filters, `--bwlimit`, `--transfers`, `--check-access`, and live command preview.
- **Built-in Safety Guardrails:** Mandatory `--dry-run` simulation before the first sync of any profile, friendly mass-deletion confirmation above threshold (default: 25 files), isolated per-profile `--workdir` and `flock` locking, `--drive-skip-gdocs` enabled by default, and no automatic `--resync` after errors.
- **Interactive Conflict Resolution & History:** Side-by-side resolution for `*.conflict1` / `*.conflict2` files (local and cloud) and rotating execution logs with export.
- **Credentials & Privacy:** Isolated `~/.config/pontis/rclone.conf` (`0600`), optional OS keyring password protection, credential-free JSON profile import/export, `sync.sh` script importer, zero telemetry, and no ads.
- **Bilingual & Accessible UI:** Follows your system locale with English fallback (switchable live between `en` and `pt_BR`), Light/Dark/System themes, and full keyboard navigation.

### Download & Verify (Linux x86_64 AppImage)

Requires `rclone >= 1.66.0` installed on your system:

```bash
sha256sum -c Pontis-1.0.0-x86_64.AppImage.sha256
chmod +x Pontis-1.0.0-x86_64.AppImage
./Pontis-1.0.0-x86_64.AppImage
```

---

## 2. Community Post — English (`r/linux`, `r/opensource`, `r/rclone`, `r/selfhosted`)

**Title:** `Pontis v1.0.0 — A free, open-source Linux GUI for safe two-way cloud sync powered by rclone`

Hi everyone,

I built **Pontis** (GPL-3.0-or-later, Python + PySide6) to solve a problem I ran into on Linux: I wanted a clean desktop UI around `rclone bisync` (Google Drive, OneDrive, Dropbox, S3, SFTP, WebDAV, etc.) with guardrails so I wouldn't accidentally wipe files or forget `--dry-run` / `--resync` rules.

I've been using it daily myself, and today I'm tagging **v1.0.0** for Linux (`x86_64` AppImage + source install).

**What it does:**
- **Mandatory first `--dry-run`** on every new profile, showing planned copies and deletions before touching real files.
- **Mass-deletion protection** (default threshold: 25 files) with an explicit review dialog if exceeded, and **never** auto-running `--resync` after a failure.
- **Conflict resolution UI** for `*.conflict1` / `*.conflict2` files (both local and remote).
- **Isolated credentials:** keeps its own `~/.config/pontis/rclone.conf` (`0600`) without touching `~/.config/rclone/rclone.conf`, with optional OS keyring encryption support.
- **Script importer & CLI:** import existing `sync.sh` scripts, export/import profiles as credential-free JSON, watch folders on demand with `watchdog`, or run headlessly via `pontis run <profile>`.
- **Zero telemetry, no ads, 100% open source.**

*(Note: v1 focuses on reliable manual / on-demand sync on Linux; built-in background scheduling and Windows/macOS support are planned for future versions.)*

- Repository & Docs: <https://github.com/lcazevedo/pontis>
- Download (`v1.0.0` AppImage): <https://github.com/lcazevedo/pontis/releases/tag/v1.0.0>

Feedback, bug reports, and PRs are very welcome!

---

## 3. Community Post — Português (Brasil) (Diolinux Plus, TabNews, `r/brdev`)

**Título:** `Pontis v1.0.0 — Interface gráfica livre para sincronização bidirecional com nuvem no Linux (usando rclone)`

Olá, pessoal!

Acabei de lançar a versão **1.0.0** do **Pontis** — um aplicativo desktop para Linux em Python/PySide6 (licença **GPL-3.0-or-later**) que cria uma camada visual amigável e segura em volta do `rclone bisync` (Google Drive, OneDrive, Dropbox, S3, SFTP, etc.).

Ele nasceu da minha própria rotina no Linux: eu já sincronizava minhas pastas com um script `sync.sh` usando `rclone bisync`, mas queria assistente visual, filtros fáceis, histórico de logs e proteções para evitar exclusões acidentais ou erros com `--resync`.

**Principais recursos da v1.0.0:**
- **Simulação obrigatória (`--dry-run`)** antes da primeira sincronização real de cada perfil.
- **Proteção contra exclusões em massa** (limite padrão configurável de 25 arquivos, com revisão explícita antes de apagar) e **nunca** repete `--resync` automaticamente após erro.
- **Resolução interativa de conflitos** (`*.conflict1` / `*.conflict2`) tanto locais quanto na nuvem.
- **Credenciais isoladas:** usa `~/.config/pontis/rclone.conf` (`0600`) sem mexer no seu `~/.config/rclone/rclone.conf`, com senha opcional no *keyring* do sistema.
- **Importador de `sync.sh`**, exportação/importação de perfis em JSON (sem segredos), observação em tempo real sob demanda (`watchdog`) e modo CLI (`pontis run <perfil>`).
- **Bilíngue (`pt_BR` e `en`)**, temas Claro/Escuro, **zero telemetria** e disponível em **AppImage**.

*(Obs.: na v1 a sincronização é manual/sob demanda; agendamento em segundo plano e suporte a Windows/macOS ficam para versões futuras.)*

- Repositório e guias em PT-BR: <https://github.com/lcazevedo/pontis/blob/main/README.pt-BR.md>
- Download (`v1.0.0` AppImage): <https://github.com/lcazevedo/pontis/releases/tag/v1.0.0>

Feedbacks, sugestões e contribuições são super bem-vindos!
