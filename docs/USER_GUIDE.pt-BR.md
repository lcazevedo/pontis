# Guia do Usuário do Pontis

> 🌐 **Idioma:** [English](USER_GUIDE.md) | **Português (Brasil)**

Este guia explica como usar o **Pontis** no dia a dia no Linux, desde a conexão de contas na nuvem até a resolução de conflitos, consulta de logs e uso pelo terminal.

---

## 1. Gerenciando contas na nuvem (Remotos)

O Pontis mantém um arquivo próprio e isolado em `~/.config/pontis/rclone.conf` (permissão `0600`), sem nunca alterar o seu `~/.config/rclone/rclone.conf` pessoal.

### Importar um `rclone.conf` existente

Se você já usa o `rclone` no terminal:

```bash
pontis remote import
```

Também é possível importar apenas um remoto específico ou indicar outro arquivo (inclusive criptografado):

```bash
pontis remote import --remote gdrive
pontis remote import --from /caminho/para/rclone.conf --overwrite
```

### Adicionar uma nova conta na nuvem

Use `pontis remote add <nome> <tipo>`:

```bash
# Fluxo OAuth no navegador (exemplo com Google Drive)
pontis remote add gdrive drive

# Recomendado: informar seu próprio client_id e client_secret do Google
pontis remote add gdrive drive \
  --param client_id=SEU_ID.apps.googleusercontent.com \
  --param client_secret=SEU_SECRET
```

Veja o [Guia de Client ID do Google](GOOGLE_CLIENT_ID.pt-BR.md) para criar suas credenciais gratuitas.

### Listar, testar, remover e proteger com senha

```bash
pontis remote list
pontis remote test gdrive
pontis remote remove gdrive

# Opcional: salvar a senha do rclone.conf no cofre do sistema (keyring)
pontis remote password set
pontis remote password status
pontis remote password remove
```

---

## 2. Criando e editando perfis

Abra o `pontis` e clique em **Novo Perfil** (`Ctrl+N`), ou edite um perfil existente (`Ctrl+E` ou duplo clique na linha).

O **Assistente de Perfil** conduz por 6 etapas:

1. **Nome:** identificador único do perfil.
2. **Lado A:** pasta local ou remoto na nuvem (com navegador visual de pastas).
3. **Lado B:** pasta local ou remoto na nuvem.
4. **Direção:**
   - **Bidirecional (`↔`):** usa `rclone bisync` (padrão).
   - **A → B (`→`):** sincronização unidirecional (`rclone sync`) de A para B.
   - **B → A (`←`):** sincronização unidirecional (`rclone sync`) de B para A.
5. **Política de conflito:**
   - **Manter ambos (`keep_both`, padrão mais seguro):** preserva os dois arquivos como `*.conflict1` / `*.conflict2` (mantendo a extensão) para você decidir depois.
   - **Mais recente (`newer`)**, **Maior (`larger`)**, **Lado A vence (`path1`)** ou **Lado B vence (`path2`)**.
   - *(Obs.: a opção de agendamento aparece desativada na v1; nesta versão a execução é manual.)*
6. **Resumo:** revise os dados e, se quiser, abra **Opções Avançadas** antes de salvar.

---

## 3. Opções avançadas e filtros

Selecione um perfil e pressione `Ctrl+Shift+O` (ou clique em **Opções Avançadas**):

- **Filtros:** adicione padrões `--include` e `--exclude` (ex.: `*.tmp`, `node_modules/**`, `.git/**`).
- **Segurança e Conflito:**
  - Altere a política de conflito.
  - Ajuste o limite de segurança para exclusões em massa (`max_delete_files`, padrão **25 arquivos**).
  - Ative `--check-access` (exige arquivo marcador `RCLONE_TEST` nos dois lados).
- **Desempenho e Rede:**
  - Limite de banda (`--bwlimit`, ex.: `5M`, `500K`).
  - Transferências paralelas (`--transfers`).
- **Flags Livres:** adicione parâmetros extras do rclone. Flags críticas controladas pelo Pontis (`--resync`, `--force`, `--config`, `--workdir`, `--max-delete`, `--dry-run`, `--use-json-log`, etc.) são bloqueadas por segurança.
- **Pré-visualização do comando:** veja e copie o comando exato que será executado, alternando a prévia entre simulação (`--dry-run`) e primeira execução (`--resync`).

---

## 4. Executando sincronizações com segurança

### Primeira execução (simulação obrigatória)

Na primeira vez que um novo perfil é executado, o Pontis exige uma simulação `--dry-run` bem-sucedida antes de alterar arquivos reais:

1. Selecione o perfil e clique em **Sincronizar agora** (`Ctrl+R`) ou **Simular (Dry Run)** (`Ctrl+Shift+R`).
2. O Pontis executa em modo de simulação e exibe o **Resumo da Simulação** com cópias e exclusões previstas.
3. Confirme o resumo para rodar a sincronização inicial (`--resync --resync-mode newer`, que copia arquivos ausentes sem apagar nada).

### Proteção contra exclusão em massa

Em execuções normais, se o `rclone bisync` detectar mais exclusões do que o limite configurado (padrão: **25 arquivos**):

- Exclusões **dentro do limite** (como renomear alguns arquivos ou pequenas limpezas) seguem normalmente sem alarme falso.
- Exclusões **acima do limite** são interrompidas com um aviso amigável de **Proteção de Segurança**, permitindo revisar os arquivos antes de autorizar explicitamente.

### Recuperação após falha no `bisync`

Se uma sincronização bidirecional falhar no meio (queda de rede ou interrupção), o `rclone bisync` pode pedir um `--resync` manual. **O Pontis nunca repete `--resync` automaticamente após uma falha.** Consulte os detalhes no **Histórico** (`Ctrl+H`) e só acione o botão de ressincronização quando tiver certeza de que ambas as pastas estão íntegras.

---

## 5. Resolvendo conflitos

Com a política padrão `keep_both`, quando o mesmo arquivo é alterado nos dois lados entre uma sincronização e outra, são criados arquivos `*.conflict1` e `*.conflict2` (com a extensão original preservada).

1. Selecione o perfil e clique em **Conflitos** (ou aceite a oferta exibida logo após uma execução que detectou conflitos).
2. Compare a pré-visualização de texto do Lado A e do Lado B.
3. Escolha a resolução individualmente ou em lote:
   - **Manter Lado A**
   - **Manter Lado B**
   - **Manter Ambos (renomeados)**
   - **Descartar Ambos**
4. Aplique e, se desejar, sincronize novamente em seguida.

---

## 6. Histórico, logs, importação/exportação e observação

- **Histórico e logs rotativos (`Ctrl+H`):** filtre execuções por perfil ou status (`success`, `error`, `cancelled`), leia logs completos, copie ou exporte para arquivo.
- **Importar Script Shell (`Arquivo → Importar Script Shell...`):** extrai pastas, variáveis, direção e filtros `--exclude`/`--include` de um `sync.sh` existente direto para o assistente.
- **Exportar / Importar Perfis (`JSON`):** salve ou compartilhe perfis sem nenhum token OAuth ou senha.
- **Observar com Watchdog (`Ctrl+W`):** monitora alterações em pastas locais em tempo real durante a sessão aberta, com *debounce* configurável antes de sincronizar.

---

## 7. Preferências, idiomas e atalhos

Abra **Preferências** (`Ctrl+,`) para ajustar:

- **Idioma:** troca imediata entre **Português (Brasil)** e **English**.
- **Tema:** Sistema, Claro ou Escuro.
- **Motor rclone:** escolha um binário manual do `rclone`, use detecção automática e teste a versão mínima (`>= 1.66.0`).
- **Atualizações:** ative ou desative a verificação de novas versões no GitHub Releases.

### Atalhos de teclado

| Atalho | Ação |
|---|---|
| `Ctrl+R` | Sincronizar agora |
| `Ctrl+Shift+R` | Simular (`--dry-run`) |
| `Ctrl+W` | Observar com Watchdog |
| `Ctrl+N` | Novo Perfil |
| `Ctrl+E` | Editar Perfil selecionado |
| `Ctrl+Shift+O` | Opções Avançadas |
| `Ctrl+H` | Histórico e Logs |
| `Delete` | Excluir Perfil |
| `F5` | Atualizar lista de perfis |
| `Ctrl+,` | Preferências |
| `F1` | Sobre o Pontis |
| `Ctrl+Q` | Sair |
