# Perguntas Frequentes (FAQ)

> 🌐 **Idioma:** [English](FAQ.md) | **Português (Brasil)**

### Por que o Pontis usa `rclone` em vez de `rsync`?
O `rsync` é excelente para discos locais e SSH/SFTP, mas não fala nativamente com APIs de nuvem como Google Drive, OneDrive ou Dropbox e é focado em sincronização unidirecional. O `rclone` suporta mais de 70 provedores de nuvem e oferece o `bisync` com controle de estado bidirecional.

### Por que o `--dry-run` é obrigatório na primeira execução de um perfil?
Na primeira execução, o `rclone bisync` ainda não possui arquivos de estado (*listings*). Exigir uma simulação `--dry-run` primeiro permite conferir pastas, filtros e arquivos previstos antes de qualquer modificação real.

### Por que o Pontis não roda `--resync` automaticamente após um erro?
Se o `bisync` falhar porque uma pasta foi desmontada ou houve queda de conexão, repetir `--resync` automaticamente pode duplicar ou apagar arquivos indevidamente. Por segurança, o Pontis interrompe a execução, registra o erro no histórico e exige sua confirmação manual para rodar `--resync`.

### Como funciona o limite padrão de 25 exclusões?
Cada perfil tem `max_delete_files = 25` por padrão. Pequenas operações normais do dia a dia (como renomear alguns arquivos) acontecem normalmente sem travar com alarmes falsos. Se uma sincronização tentar apagar mais arquivos do que esse limite, o Pontis aciona a **Proteção de Segurança** e pede sua revisão explícita antes de continuar. Você pode alterar esse valor por perfil em **Opções Avançadas**.

### Por que documentos nativos do Google Docs / Sheets / Slides são ignorados?
Arquivos nativos do Google Workspace (`.gdoc`, `.gsheet`, `.gslides`) não têm tamanho fixo nem hash tradicional no Drive, o que causa erros frequentes no `rclone bisync`. Por padrão, o Pontis ativa `--drive-skip-gdocs` em perfis do Google Drive para evitar falhas na sincronização.

### Onde o Pontis guarda o banco de dados, configurações e logs?
O Pontis segue os diretórios padrão XDG via `platformdirs`:
- **Configurações** (`rclone.conf`, `settings.json`): `~/.config/pontis/`
- **Dados e banco SQLite** (`pontis.db`, `bisync/<id>/`, `locks/`): `~/.local/share/pontis/`
- **Logs rotativos** (`runs/run_<id>.log`): `~/.local/state/pontis/log/`

O seu arquivo pessoal `~/.config/rclone/rclone.conf` nunca é modificado.

### Por que a v1 não tem agendamento automático na interface?
Agendamento em segundo plano exige integração com serviços do sistema (`systemd --user`, bandeja, políticas de bateria e rede). A v1 prioriza sincronização manual confiável, mas já deixa o esquema do banco (`schedule`), a interface `SchedulerBackend` e o comando `pontis run <perfil>` prontos. Se precisar agendar hoje no Linux, você já pode chamar `pontis run <perfil>` via `cron` ou `systemd --user` timer.

### O Pontis terá suporte para Windows ou macOS?
A v1 é focada em Linux, mas o código usa `pathlib`, `platformdirs`, `PySide6` e `keyring`, facilitando suporte futuro a Windows e macOS sem reescrever o núcleo.

### O Pontis coleta telemetria ou envia meus dados?
Não. O Pontis não tem anúncios, rastreamento nem telemetria. Além das conexões do `rclone` com as suas nuvens, a única requisição de rede opcional é a verificação somente leitura de novas versões no GitHub Releases (que pode ser desativada em **Preferências**).

### Como posso apoiar o projeto?
O Pontis é software livre (`GPL-3.0-or-later`). Relatos de bugs, sugestões, traduções e Pull Requests são muito bem-vindos. Se desejar contribuir financeiramente de forma opcional, há links discretos no app e no README para [GitHub Sponsors](https://github.com/sponsors/lcazevedo), [Ko-fi](https://ko-fi.com/lcazevedo) e [Buy Me a Coffee](https://buymeacoffee.com/lcazevedo).
