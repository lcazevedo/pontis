#!/bin/bash
# Script de sincronização bidirecional - SENAI (Local <-> Google Drive)

# Caminhos
LOCAL_DIR="/home/lcazevedo/Documents/SENAI"
REMOTE_NAME="gdrive" # <--- SUBSTITUA PELO NOME DO SEU REMOTE (ex: gdrive, drive, etc)
REMOTE_DIR="$REMOTE_NAME:SENAI"

# Verifica se é a primeira execução (que exige o parâmetro --resync)
RESYNC_FLAG=""
if [ "$1" == "--primeira-vez" ]; then
    RESYNC_FLAG="--resync"
    echo "=================================================="
    echo "Executando sincronização inicial (--resync ativado)"
    echo "=================================================="
else
    echo "Iniciando sincronização bidirecional..."
fi

# Executa o rclone bisync
# --conflict-resolve newer : Mantém o arquivo mais recente em caso de edição nos dois locais
# --exclude "sync.sh"      : Impede que este script seja enviado para o Google Drive
# --verbose                : Exibe no terminal os detalhes do que está sendo modificado

rclone bisync "$LOCAL_DIR" "$REMOTE_DIR" \
  --conflict-resolve newer \
  --exclude "sync.sh" \
  --exclude ".opencode/**" \
  --exclude "**/node_modules/**" \
  --verbose \
  $RESYNC_FLAG

echo ""
echo "Sincronização finalizada!"
