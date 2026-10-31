# AGENTS.md — Instruções para agentes de IA (projeto Pontis)

Pontis é um app desktop em Python para sincronização bidirecional entre pastas locais e nuvem, usando **rclone**. Responda ao usuário em **português (Brasil)**.

## Leia antes de qualquer ação
1. [docs/PLANO_DE_TRABALHO.md](docs/PLANO_DE_TRABALHO.md): fonte da verdade sobre **o que é cada Parte**, o status e o registro de decisões.
2. [docs/PROPOSTA_ARQUITETURA.md](docs/PROPOSTA_ARQUITETURA.md): arquitetura, decisões e estrutura do repositório.

## Decisões fixas (não reabrir sem pedido do usuário)
- Motor: **rclone** (`rclone bisync` padrão). Não usar rsync.
- Nome: **Pontis**. Pacote Python: `pontis`, layout `src/pontis/`.
- Linguagem: Python 3.12. GUI: **PySide6** (nunca PyQt6).
- Persistência: **SQLite** (stdlib `sqlite3`, migrações versionadas), caminhos via `platformdirs`.
- Segredos: `keyring`. Credenciais OAuth ficam no `rclone.conf` **próprio do app** (`--config`), nunca no `~/.config/rclone/rclone.conf` do usuário.
- Licença: **GPL-3.0-or-later** (cabeçalho SPDX em cada arquivo-fonte: `# SPDX-License-Identifier: GPL-3.0-or-later`).
- Idiomas: **pt_BR e en** desde o início; nenhuma string de UI solta no código, sempre via i18n.
- Plataforma da v1: **somente Linux**. Código não deve ter nada que impeça Windows/macOS depois (usar `pathlib`, `platformdirs`).
- **Agendamento fora da v1**: execução só manual. Apenas preparar os pontos de extensão (campo `schedule`, interface `SchedulerBackend`, CLI `pontis run`). Não implementar agendador.
- rclone: abordagem híbrida (rclone do app → `PATH` → orientar instalação), versão mínima validada, caminho configurável. Na v1 não empacotar o rclone.

## Ambiente de desenvolvimento
- Usar **conda (miniconda)**, ambiente **`pontis-dev`** com Python 3.12. **Nunca usar `python -m venv`, virtualenv, poetry ou pipenv.**
- Dependências instaladas com `pip install -e ".[dev]"` dentro do ambiente conda, a partir do `pyproject.toml`.
- O `conda` pode não estar no `PATH` do shell do agente. Se faltar, procure em `~/miniconda3/bin/conda` ou use `~/miniconda3/envs/pontis-dev/bin/python`. Nunca instale pacotes no Python do sistema nem no ambiente `base`.
- Ferramentas: `ruff` (lint e formatação), `mypy`, `pytest`, `pytest-qt`, `pre-commit`.
- Editor do usuário: VS Code (configurar `.vscode/` apontando para o ambiente `pontis-dev`).
- Docker e KVM só entram nas Partes 12 e 13 (testar AppImage numa VM limpa; CI).

## Segurança dos dados do usuário
- **Nunca** executar sincronização real em `~/Documents/SENAI` ou em qualquer pasta real do usuário durante o desenvolvimento. Usar pastas temporárias (`/tmp`, `tmp_path` do pytest) ou a pasta de testes `PontisTeste/` indicada pelo usuário.
- `sync.sh` na raiz é o script original do usuário: **não modificar nem apagar**.
- Em qualquer teste que use nuvem: `--dry-run` primeiro e `--max-delete` ativo.
- Nunca repetir `--resync` automaticamente após uma falha do bisync.
- Não executar comandos destrutivos (`rm -rf`, `rclone sync/delete/purge`) fora de diretórios temporários sem confirmação.

## Como trabalhar (uma Parte por conversa)
O usuário pede, em uma conversa nova, algo como "Faça a Parte N". Então:
1. Leia o plano e a arquitetura; confirme qual é a Parte N pelo plano (a numeração começa em 0).
2. Confirme que as Partes anteriores estão marcadas como concluídas no plano. Se não estiverem, avise o usuário e pare.
3. Faça **somente** o escopo da Parte N. Não adiante trabalho de partes futuras.
4. Escreva testes automatizados quando aplicável e rode `ruff`, `mypy` e `pytest`.
5. Ao terminar: atualize o status da Parte N no plano (checklist, data, decisões e desvios no "Registro de decisões"), faça um commit git (`Parte N: <título>`) e entregue ao usuário um resumo curto com **como testar** (o critério de teste da Parte).
6. **Pare** e aguarde o usuário validar. Não comece a próxima Parte.

## Convenções de código
- Camadas: `domain/` (modelos puros, sem Qt nem I/O), `services/`, `infra/`, `ui/`. A UI não chama o rclone diretamente; passa pelos serviços.
- Type hints em todo código novo; docstrings em inglês; mensagens ao usuário via i18n.
- Commits em português, no formato `Parte N: descrição`.
- Mantenha comentários e docstrings existentes que não tenham relação com a mudança.
