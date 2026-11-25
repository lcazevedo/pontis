# Pontis — Plano de Trabalho

Cada **Parte** é entregue isoladamente e termina com um **critério de teste** para você validar antes de pedirmos a próxima. Peça: *"Faça a Parte N"*.

**Escopo da v1:** Linux, sincronização manual, GPL-3.0-or-later, rclone (híbrido), SQLite, PT-BR + EN.
**Fora da v1:** agendamento, Windows, macOS, empacotamento do rclone.

```mermaid
flowchart LR
    P0[0 Fundação] --> P1[1 Domínio e SQLite] --> P2[2 Rclone e CLI] --> P3[3 Contas na nuvem]
    P3 --> P4[4 GUI base] --> P5[5 Assistente] --> P6[6 Avançado] --> P7[7 Execução na GUI]
    P7 --> P8[8 Histórico e conflitos] --> P9[9 Importador e extras] --> P10[10 i18n e polimento]
    P10 --> P11[11 Documentação] --> P12[12 Empacotamento Linux] --> P13[13 CI e GitHub] --> P14[14 Release 1.0]
```

---

## Parte 0 — Fundação do projeto
**Status:** ✅ Concluída (2026-10-31), aguardando validação do usuário

**Escopo (somente isto):** preparar o projeto vazio e o ambiente. Nenhuma funcionalidade do app.
- Ambiente **conda** `pontis-dev` (Python 3.12), **sem venv**. Instalação com `pip install -e ".[dev]"`.
- Repositório: `git init` e primeiro commit. `.gitignore`, `.editorconfig`.
- `pyproject.toml` com metadados (nome `pontis`, licença `GPL-3.0-or-later`), dependências (PySide6, platformdirs, keyring) e extra `dev` (ruff, mypy, pytest, pytest-qt, pre-commit).
- `LICENSE` (texto da GPL-3.0), cabeçalhos SPDX, `README.md` mínimo.
- Esqueleto `src/pontis/` (`__init__.py`, `__main__.py`) e `tests/` com um teste simples.
- `ruff`, `mypy`, `pytest` e `pre-commit` configurados.
- VS Code: `.vscode/settings.json` e `launch.json` apontando para o ambiente `pontis-dev`.
- Janela vazia do PySide6 abrindo (prova do ambiente).
- Pasta de testes: orientar o usuário a criar `PontisTeste/` no Drive (o agente não cria nem usa nada na nuvem nesta parte).
- **Não fazer:** modelos, banco, rclone, telas reais, i18n completo.
- **Teste:** `conda activate pontis-dev`, `pontis` abre uma janela em branco; `pytest`, `ruff check` e `mypy` passam.

## Parte 1 — Domínio e persistência (SQLite)
**Status:** ✅ Concluída (2026-10-31), aguardando validação do usuário

- Modelos: `SyncProfile`, `Endpoint`, `SyncOptions`, `Schedule` (só `manual`), `RunResult`.
- SQLite com migrações versionadas, diretórios via `platformdirs`; repositórios (CRUD de perfis, histórico).
- Coluna `schedule` reservada para o futuro.
- **Teste:** testes unitários passam; criar, editar e excluir um perfil por script e ver o banco persistir.

## Parte 2 — Motor rclone e CLI
**Status:** ✅ Concluída (2026-10-31), aguardando validação do usuário

- Localizar rclone (app → `PATH` → orientação), checar versão mínima.
- `RcloneAdapter`: montar comando do `bisync`, `--resync` automático na primeira vez (com segurança), `--dry-run`, `--max-delete`, lock por perfil, leitura do `--use-json-log`.
- CLI: `pontis profile add|list|remove`, `pontis run <perfil> [--dry-run]`.
- **Teste:** com pastas locais temporárias, `pontis run` sincroniza nos dois sentidos. Depois, reproduzir seu `sync.sh` (SENAI ↔ gdrive) com `--dry-run` e então de verdade.

## Parte 3 — Contas em nuvem (remotos)
**Status:** ✅ Concluída (2026-11-01), aguardando validação do usuário

- `RemoteService`: listar, criar (fluxo OAuth), testar e remover remotos num `rclone.conf` próprio do app.
- Opção de importar o `rclone.conf` existente; suporte a senha do config via `keyring`.
- Comandos CLI: `pontis remote add|list|test|remove`.
- **Teste:** adicionar uma conta Google Drive (ou importar a existente), listar e testar a conexão.

## Parte 4 — GUI base
**Status:** ✅ Concluída (2026-11-01), aguardando validação do usuário

- Janela principal: tabela de sincronizações, barra de ações, estados (vazio, lista).
- Navegação, ícones, tema claro/escuro, camada de i18n já em uso nas strings (PT-BR e EN).
- Dados vindos do SQLite.
- **Teste:** os perfis criados pelo CLI aparecem na janela, que pode excluí-los.

## Parte 5 — Assistente de criação/edição
**Status:** ✅ Concluída (2026-11-01), aguardando validação do usuário

- Passos: nome → lado A → lado B → direção → conflito → resumo.
- Seletor de local ou remoto, navegador de pastas (local e nuvem), validação em cada passo.
- Reserva visual para agendamento (desativada ou oculta).
- **Teste:** criar e editar um perfil local ↔ Google Drive só pela interface.

## Parte 6 — Janela de opções avançadas
**Status:** ✅ Concluída (2026-11-01), aguardando validação do usuário

- Filtros include/exclude, `max-delete`, `check-access`, limite de banda, transferências paralelas, política de conflito, flags livres com validação.
- Pré-visualização do comando final.
- **Teste:** reproduzir os `--exclude` do seu `sync.sh` pela janela e conferir o comando exibido.

## Parte 7 — Execução na GUI
**Status:** ✅ Concluída (2026-11-02), aguardando validação do usuário

- Botão *Sincronizar agora*, `--dry-run` obrigatório na primeira execução (com resumo do que mudará), confirmação de exclusões em massa.
- Progresso em tempo real, cancelar, bloqueio contra execução dupla, notificações do sistema.
- **Teste:** sincronizar a pasta SENAI pela interface, com a simulação, o progresso e o resultado.

## Parte 8 — Histórico, logs e conflitos
**Status:** ✅ Concluída (2026-11-02), aguardando validação do usuário

- Tela de histórico por perfil e execução, logs rotativos, exportação de log.
- Tratamento de erros do bisync (inclusive pedido de `--resync`, nunca automático após falha).
- Tela de resolução de conflitos.
- **Teste:** provocar um conflito (editar o mesmo arquivo nos dois lados) e resolvê-lo; consultar o histórico.

## Parte 9 — Importador e extras
**Status:** ✅ Concluída (2026-11-04), aguardando validação do usuário

- Importar `sync.sh` (pastas e `--exclude`).
- Exportar e importar perfis (sem segredos).
- Observação de mudanças com `watchdog` (opcional, sob demanda).
- **Teste:** importar o seu `sync.sh` e obter um perfil equivalente.

## Parte 10 — Idiomas e polimento
**Status:** ✅ Concluída (2026-11-10), aguardando validação do usuário

- Revisão completa PT-BR e EN, seletor de idioma nas Preferências, acessibilidade (teclado, contraste).
- Tela de Preferências (idioma, caminho do rclone, tema), aviso de nova versão.
- **Teste:** trocar o idioma em tempo de execução e percorrer todas as telas.

## Parte 11 — Documentação profissional
**Status:** ✅ Concluída (2026-11-25), aguardando validação do usuário

- `README.md` e `README.pt-BR.md` com capturas de tela, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`.
- Guia do usuário, guia de criação de *client_id* do Google, FAQ, ADRs, `THIRD_PARTY_LICENSES.md`.
- Apoio voluntário ao projeto (GitHub Sponsors, Ko-fi e Buy Me a Coffee — sem Pix): `.github/FUNDING.yml`, seções nos READMEs e links discretos na janela *Sobre*, no menu *Ajuda* e na barra de status da janela principal (sem banners nem popups).
- **Teste:** você segue o README do zero numa conta/pasta limpa e confere os links discretos de apoio na janela principal e em *Sobre*.

## Parte 12 — Empacotamento Linux
**Status:** ✅ Concluída (2026-11-25), aguardando validação do usuário

- Build com PyInstaller, **AppImage**, `.desktop` e ícone; Flatpak (manifesto) como segunda opção.
- Verificação do build em uma instalação limpa (sem Python).
- **Teste:** instalar o AppImage em outra máquina ou usuário e usar o app.

## Parte 13 — CI e repositório no GitHub
**Status:** ✅ Concluída (2026-11-25), aguardando publicação/push do usuário no GitHub

- GitHub Actions: lint, tipos, testes, build do AppImage; templates de *issues* e *pull requests*.
- Publicação do repositório, proteção da branch principal, *releases* por tag.
- **Teste:** um *push* dispara o CI e ele passa.

## Parte 14 — Release 1.0
**Status:** ⬜ Pendente

- Revisão final (segurança, licenças, testes de ponta a ponta), versão e `CHANGELOG`.
- Tag `v1.0.0`, publicação do AppImage nos *Releases*, texto de divulgação.
- **Teste:** baixar o AppImage dos Releases e instalar como um usuário novo.

---

## Futuro (pós-v1)
| Item | Observação |
|---|---|
| Agendamento | Agente na bandeja (APScheduler) e/ou systemd, Task Scheduler, launchd; os pontos de extensão já existem desde a Parte 1 |
| Windows | Build no CI, instalador, rclone empacotado, assinatura opcional |
| macOS | Build no CI, DMG, notarização (Apple Developer Program) |
| Rclone empacotado | Etapa do build quando houver Windows/macOS |
| Publicação em lojas | Flathub, AUR, PyPI |

## Registro de decisões e desvios
Cada conversa adiciona aqui, ao concluir sua Parte, o que decidiu ou mudou em relação ao plano.

| Parte | Data | Decisão / desvio |
|---|---|---|
| — | 2026-10-30 | Decisões iniciais: ver `AGENTS.md` e `PROPOSTA_ARQUITETURA.md` §0 |
| 0 | 2026-10-31 | Ambiente conda `pontis-dev` criado em `~/miniconda3` (Python 3.12). Entry point `pontis = pontis.app:main`; janela vazia em `src/pontis/app.py`. `mypy` em modo `strict`; ruff com regras E,F,W,I,B,UP,SIM; hook mypy do pre-commit é `local` (usa o ambiente ativo). Testes de UI rodam com `QT_QPA_PLATFORM=offscreen`. Pasta `PontisTeste/` no Drive: a criar pelo usuário. |
| 1 | 2026-10-31 | Domínio em `domain/models.py` (dataclasses + enums StrEnum, serialização JSON). Padrão de conflito `keep_both` e `max_delete_percent=50`. SQLite em `infra/database.py` com migrações via `PRAGMA user_version` (lista `MIGRATIONS`, nunca editar entradas antigas; sem `;` dentro dos scripts). Tabelas `profiles` (nome único; `schedule` JSON, NULL = manual) e `runs` (FK com cascade). Repositórios em `infra/repositories.py`; `infra/paths.py` (platformdirs); `SchedulerBackend` (Protocol sem implementação). Sem camada `services/` ainda (virá com as Partes 2+). Script manual: `scripts/demo_profiles.py`. Rodar ruff/mypy/pytest exige o env conda fora do sandbox do agente. |
| 2 | 2026-10-31 | `infra/rclone.py` (localização: caminho configurado → `<data>/bin/rclone` → `PATH`; versão mínima **1.66.0**), `infra/rclone_adapter.py` (`RcloneAdapter`), `infra/locking.py` (lock por perfil via `flock`, só POSIX), `services/run_service.py` (`RunService`), `cli.py` e `i18n/__init__.py` (catálogo simples pt_BR/en para o CLI; a ponte com Qt vem na Parte 4). Bisync usa `--workdir` próprio por perfil (`<dir do banco>/bisync/<id>`), assim "primeira vez" = nenhum `*.lst` no workdir. Primeira execução: `--resync --resync-mode newer` (nunca apaga); execuções normais: `--conflict-resolve` conforme a política (`keep_both` = `none`) e `--max-delete <percent>`. **Segurança extra:** a 1ª execução real exige um `--dry-run` bem-sucedido no histórico (`--skip-first-dry-run` ignora); pasta local inexistente aborta antes do rclone; `--resync` nunca é repetido após falha; `extra_flags` com flags gerenciadas pelo app (`--resync`, `--config`, `--max-delete`…) são recusadas. Direções unidirecionais usam `rclone sync` (**sem** `--max-delete` percentual, pois só existe contagem no `sync`). `pontis` sem argumentos abre a janela; com argumentos vira CLI (`--db` opcional para testes). O CLI sempre passa `--config` com o `rclone.conf` do app (`~/.config/pontis/rclone.conf`); `--rclone-config` permite apontar um arquivo explícito (útil até a Parte 3 importar o seu). Ctrl+C termina o rclone e grava a execução como `cancelled`. |
| 3 | 2026-11-01 | Modelos `RemoteInfo` e `RemoteTestResult` em `domain/models.py`. Armazenamento seguro de senhas no keyring do sistema via `infra/keyring_store.py` (`KeyringStore`, chave `rclone_config_pass`). `RemoteService` em `services/remote_service.py` gerenciando remotos no `rclone.conf` exclusivo do Pontis (`~/.config/pontis/rclone.conf`), com permissão restrita 0600: listagem via `rclone config dump`, criação via `rclone config create` (suporta fluxo interativo OAuth no navegador e parâmetros diretos), remoção via `rclone config delete`, teste de conectividade via `rclone about` (cota/armazenamento) com fallback para `rclone lsf`, e importação de arquivos de configuração externos (`rclone.conf` do usuário ou customizado) com preservação de tokens e suporte a senha. `RcloneAdapter` e `RunService` agora injetam `RCLONE_CONFIG_PASS` automaticamente quando há senha salva no keyring. Comandos CLI em `cli.py`: `pontis remote list [--json]`, `pontis remote add <name> <type> [--param KEY=VALUE] [--non-interactive]`, `pontis remote test <name> [--path PATH]`, `pontis remote remove <name>`, `pontis remote import [--from PATH] [--remote NAME] [--overwrite] [--source-password PWD]` e `pontis remote password set|remove|status`. Mensagens i18n em pt_BR e en. |
| 4 | 2026-11-01 | Camada de UI com PySide6 em `src/pontis/ui/`: `MainWindow` com alternância suave entre tabela de sincronizações e `EmptyStateWidget` (quando não há perfis); barra de ações com Novo Perfil (placeholder explicativo indicando o assistente da Parte 5), Excluir (com diálogo de confirmação `QMessageBox` e remoção no SQLite), Atualizar (recarregar dados) e seletor de tema (Claro, Escuro e Sistema). `ProfileService` em `services/profile_service.py` encapsulando operações de perfis e resumos com o último `RunResult`. Helper de ícones em `ui/icons.py` com `QIcon.fromTheme` e desenho vetorial de fallback para suporte headless/offscreen. i18n completo em `i18n/__init__.py` para todas as strings de UI em pt_BR e en sem textos soltos no código. Testes automatizados com `pytest-qt` cobrindo exibição, estados, exclusão, temas e i18n. |
| 5 | 2026-11-01 | Assistente de criação e edição com PySide6 `QWizard` em `src/pontis/ui/wizard.py` (passos: identificação, Lado A, Lado B, direção, política de conflito + reserva visual desativada para agendamento, resumo e persistência). Componentes modulares `EndpointPickerWidget` e `CloudFolderBrowserDialog` para navegação interativa em diretórios remotos via `rclone lsf --dirs-only`. Integração na `MainWindow` com ação "Editar", atalho Ctrl+E, botão na barra de ações, duplo clique na tabela e menu de contexto. Atualizações nos serviços: `ProfileService.update_profile` e `RemoteService.list_directories` com tratamento robusto a falhas. i18n completo pt_BR e en. 60 testes unitários e de interface automatizados. |
| 6 | 2026-11-01 | Janela de opções avançadas com PySide6 em `src/pontis/ui/advanced_options_dialog.py` (`AdvancedOptionsDialog`) organizada em abas: Filtros (gerenciador de listas de inclusão `--include` e exclusão `--exclude` com adição, remoção e limpeza), Segurança e Conflito (seletor de `ConflictPolicy`, slider e spinbox sincronizados para `max_delete_percent` de 0% a 100%, e checkbox `--check-access`), Desempenho e Rede (campo `--bwlimit` com validação de formato e spinbox `--transfers` de 1 a 128), e Flags Livres (área para parâmetros adicionais com validação em tempo real contra `FORBIDDEN_EXTRA_FLAGS` e formatos inválidos, bloqueando o salvamento em caso de flag gerenciada). Painel inferior com pré-visualização em tempo real do comando final montado pelo `RcloneAdapter` com formatação shell (`shlex.join`), alternâncias para simulação (`--dry-run`) e primeira execução (`--resync`), e botão de cópia para a área de transferência. Integração na `MainWindow` (ação na barra de ferramentas, atalho Ctrl+Shift+O, menu Perfil e menu de contexto) e no `ProfileWizard` (botão na página de resumo permitindo pré-configurar opções e refletindo os filtros no perfil persistido). `RcloneAdapter.workdir` e `needs_resync` ajustados para suportar pré-visualizações sem persistência prévia de ID. 69 testes unitários e de interface automatizados passando; ruff e mypy estrito sem erros. |
| 7 | 2026-11-02 | Execução de sincronização integrada na GUI: botão *Sincronizar agora* (Ctrl+R) e *Simular (--dry-run)* (Ctrl+Shift+R) na barra de ferramentas, menu Perfil e menu de contexto. `SyncWorker` em thread de trabalho `QThread` executando `RunService.run` sem congelar a interface. Diálogo de progresso em tempo real `SyncProgressDialog` com métricas ao vivo (transferências, exclusões, erros, velocidade B/s, bytes transmitidos e barra de progresso), log expansível e cancelamento seguro que termina o subprocesso rclone (`cancel()`) e grava o status `cancelled` no SQLite. Na primeira execução (`needs_resync`), diálogo informativo impede sincronização direta e exige simulação inicial obrigatória (`--dry-run`). Diálogo de resumo `DryRunSummaryDialog` exibindo listas de cópias e exclusões planejadas; quando há exclusões, exige confirmação explícita de segurança contra exclusão em massa para habilitar o botão de execução real. **Proteção contra exclusão refinada:** substituição do limite percentual por limite absoluto configurável (padrão de 25 arquivos). Pequenas operações normais (como renomear arquivos ou poucas exclusões abaixo do limite) são auto-resolvidas de forma transparente com `--force` sem disparar alarme falso nem erro para o usuário. Para exclusões acima do limite, a interface adota comunicação amigável com escudo de proteção de segurança (`🛡️ Proteção de Segurança`), notificação clara e botão `Revisar e Autorizar Exclusões` com confirmação explícita. Conexões SQLite ajustadas com `check_same_thread=False` e `WAL` mode para execução em thread. Feedback visual e cursor de espera (`WaitCursor`) na seleção de pastas em nuvem. 86 testes automatizados passando; ruff e mypy estrito sem erros. |
| 8 | 2026-11-02 | Gerenciamento de histórico de execuções com logs rotativos via `RunLogManager` (em `<log_dir>/runs/run_<id>.log`, controle de quantidade e tamanho total) e exportação de logs. Tratamento de erros do bisync: detecção de pedidos de ressincronização (`--resync`), status claro e botão dedicado de ressincronização com confirmação explícita (nunca automático após falhas, seguindo regra de segurança). Tela de histórico `HistoryDialog` integrada na `MainWindow` (Ctrl+H, barra de ferramentas, menu e contexto) com filtros por perfil e status, resumo detalhado e visualizador/copiador/exportador de log completo. Detecção e resolução de conflitos via `ConflictService` e diálogo interativo `ConflictResolutionDialog`: identifica arquivos `*.conflict1` e `*.conflict2` gerados pela política `keep_both` do bisync, exibe pré-visualizações de texto e permite aplicar resoluções individuais ou em lote (Manter Lado A, Manter Lado B, Manter Ambos renomeados, Descartar Ambos) tanto para pastas locais quanto para remotos na nuvem. Ações e botões de atalho integrados na `MainWindow` e no `SyncProgressDialog` ao detectar conflitos. 104 testes automatizados passando; ruff e mypy estrito sem erros. |
| 9 | 2026-11-04 | Importador de scripts shell (ex: `sync.sh`) via `ScriptImporter` em `services/import_export_service.py` extraindo pastas, variáveis do shell, direção (`bisync`/`sync`), política de conflito e filtros `--exclude`/`--include` com descarte de flags de controle. Exportação e importação de perfis em JSON (sem credenciais) via `ProfileTransfer` e `ProfileService.import_profile` com políticas de colisão (`rename` com sufixo numérico, `overwrite` ou `raise`). Observação em tempo real com `watchdog` (`WatchService` e `ProfileWatchHandler`) monitorando pastas locais com debounce configurável e disparo automático de sincronização via `RunService`. Diálogo interativo `WatchDialog` integrado na `MainWindow` (Ctrl+W, toolbar, menu Perfil e menu de contexto) com log de eventos ao vivo. Ações de importação/exportação integradas na `MainWindow` (menu Arquivo, menu Perfil e menu de contexto). Novos comandos CLI: `pontis profile export`, `pontis profile import`, `pontis profile import-script` e `pontis watch`. Dependência `watchdog>=4.0` adicionada ao `pyproject.toml`. 119 testes automatizados passando; ruff e mypy estrito sem erros. |
| 10 | 2026-11-10 | Revisão completa e paridade exata de 100% no catálogo i18n entre `pt_BR` e `en` (442 chaves em cada idioma). Suporte a troca dinâmica de idioma em tempo de execução via `register_language_listener` e `MainWindow.retranslate_ui()`, atualizando instantaneamente títulos, menus, cabeçalhos de tabela, ações e widgets sem reiniciar o app. Sistema de configurações persistentes via `AppSettings` e `SettingsManager` em `infra/settings.py` (`~/.config/pontis/settings.json`) com escrita atômica. Diálogo de Preferências `PreferencesDialog` (Ctrl+,) com abas Geral (idioma e tema), Motor Rclone (caminho configurável com navegação, auto-detecção e teste em tempo real com versão mínima validada) e Atualizações. Serviço de verificação de lançamentos `update_service.py` com comparação semântica de versões e worker assíncrono `UpdateCheckWorker` consultando GitHub Releases com tratamento a falhas de rede, integrado na inicialização e manualmente via `UpdateDialog` (com notas de versão, link para download e opção de ignorar versão). Diálogo Sobre `AboutDialog` (F1) com versão do Pontis, rclone detectado e licença GPLv3+. Acessibilidade completa: atalhos de teclado em todas as ações, navegação lógica por tabulação, `accessibleName`/`accessibleDescription` para leitores de tela e estilos de alto contraste com contorno de foco `:focus` visível em `ui/theme.py` para os temas claro e escuro. 138 testes automatizados passando; ruff e mypy estrito sem erros. |
| 11 | 2026-11-25 | Documentação profissional completa e apoio voluntário discreto: `README.md`, `README.pt-BR.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `THIRD_PARTY_LICENSES.md`, guias bilíngues (`docs/USER_GUIDE*.md`, `docs/GOOGLE_CLIENT_ID*.md`, `docs/FAQ*.md`) e ADRs (`docs/adr/0001` a `0006`). Capturas de tela geradas com dados fictícios via `scripts/generate_screenshots.py` em `docs/screenshots/`. Módulo central `src/pontis/links.py` e `.github/FUNDING.yml` configurados com GitHub Sponsors, Ko-fi e Buy Me a Coffee (sem Pix por privacidade). Integração discreta na interface: `QGroupBox` com botões secundários (`supportLinkButton`) na `AboutDialog`, submenu `Apoiar o Pontis` em `Ajuda` e `QToolButton` discreto (`supportStatusButton`) na barra de status da `MainWindow`, com suporte completo a i18n dinâmico (`pt_BR`/`en`), temas claro/escuro e ícone vetorial de fallback. 141 testes automatizados passando; ruff e mypy estrito sem erros. |
| 12 | 2026-11-25 | Ajuste de idioma padrão para `"system"` (detecta idioma do sistema do usuário via `detect_system_language()` com fallback para `"en"`, mantendo escolha explícita `"en"` ou `"pt_BR"` nas Preferências). Proteção `clean_subprocess_env` em `infra/rclone.py`, `infra/rclone_adapter.py` e `services/remote_service.py` para restaurar/remover `LD_LIBRARY_PATH` do PyInstaller ao invocar o `rclone` externo. Empacotamento Linux em `packaging/`: `pyinstaller.spec` (onedir, sem `rclone`), `pyinstaller_entry.py`, ícone `io.github.lcazevedo.Pontis.svg` + PNG 256x256 via `render_icon.py`, `.desktop`, AppStream `.metainfo.xml`, `AppRun`, `build_appimage.sh` (gera `dist/Pontis-0.1.0.dev0-x86_64.AppImage` + `.sha256`), manifesto Flatpak `packaging/flatpak/io.github.lcazevedo.Pontis.yml` e verificação em container Docker limpo (`ubuntu:24.04` sem Python, `test_appimage_in_docker.sh`) validando CLI, sync real local↔local e inicialização da GUI PySide6. 146 testes automatizados passando; ruff, ruff-format e mypy estrito sem erros. |
| 13 | 2026-11-25 | Ajuste nos links de apoio voluntário removendo temporariamente o Buy Me a Coffee (mantendo apenas GitHub Sponsors e Ko-fi ativos, com atualização em `links.py`, `.github/FUNDING.yml`, UI, READMEs, FAQs e screenshot `about_dialog.png`). Infraestrutura GitHub/CI: `.github/workflows/ci.yml` (`Quality (ruff & mypy)` e `Tests (pytest)` em `ubuntu-24.04`; `Build AppImage (Linux x86_64)` em `ubuntu-22.04` com smoke test de CLI, sync e GUI headless + upload de artefatos), `.github/workflows/release.yml` (acionado por tags `v*`, valida correspondência entre tag e `pontis.__version__`, roda qualidade/testes, compila AppImage e publica Release com `.sha256`), templates `.github/ISSUE_TEMPLATE/{config,bug_report,feature_request}.yml` e `.github/PULL_REQUEST_TEMPLATE.md`, `.github/dependabot.yml`, badges de CI nos READMEs e guia [GITHUB_SETUP.md](GITHUB_SETUP.md) para criação do repositório, primeiro push e proteção da branch `main`. 150 testes automatizados passando; YAML, ruff, ruff-format e mypy estrito sem erros. |

## Como pedir cada Parte (modelo de mensagem)
Abra uma conversa nova e escreva:

> Faça a Parte N do `docs/PLANO_DE_TRABALHO.md`. Siga o `AGENTS.md`.

Ao final, valide o critério de teste e marque a Parte como concluída (ou peça ajustes na mesma conversa) antes de abrir a próxima.

## Regras de trabalho
- Uma parte por vez, com commit ao final de cada uma.
- Cada parte inclui testes automatizados, quando aplicável.
- Antes de uma parte que mexe em suas pastas reais (2, 7), sempre há `--dry-run` e um aviso para fazer backup.
