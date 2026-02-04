#!/bin/bash
# ============================================================
# Helper script para ejecutar dvc push a Google Drive
# usando service account (no-interactivo)
# ============================================================
#
# Uso:
#   ./setup/gdrive-push.sh [opciones de dvc push]
#
# Ejemplos:
#   ./setup/gdrive-push.sh -r storage
#   ./setup/gdrive-push.sh -r storage --verbose
#
# ============================================================

set -e

CREDENTIALS_JSON="${CREDENTIALS_JSON:-setup/gdrive-credentials.json}"

if [ ! -f "$CREDENTIALS_JSON" ]; then
    echo "[ERROR] Service account JSON no encontrado: $CREDENTIALS_JSON"
    exit 1
fi

echo "[INFO] Usando service account: $CREDENTIALS_JSON"

# Para pydrive2, necesitamos que el JSON esté en la ruta estándar
# o usar GOOGLE_APPLICATION_CREDENTIALS
export GOOGLE_APPLICATION_CREDENTIALS="$CREDENTIALS_JSON"

# Intentar dvc push con timeout
echo "[INFO] Ejecutando: .venv/bin/dvc push $@"
timeout 60 .venv/bin/dvc push "$@" || {
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "[ERROR] dvc push timeout (60s). Posible bloqueo en OAuth interactivo."
        echo "[HINT] Intenta usar remoto local en su lugar:"
        echo "      make setup SETUP_CFG=setup/local.yaml"
        exit 1
    else
        exit $EXIT_CODE
    fi
}

echo "[OK] dvc push completado"
