#!/usr/bin/env python3
"""
Script para configurar Google Drive auth con service account
y hacer dvc push sin bloqueo de OAuth interactivo.

El problema: pydrive2 intenta OAuth interactivo aunque GOOGLE_APPLICATION_CREDENTIALS esté configurada.

Solución: 
1. Usar google-auth para obtener un token con service account
2. Configurar variables de entorno para que pydrive2/DVC lo usen
3. Ejecutar dvc push

Uso:
  python3 setup/gdrive_push_with_serviceaccount.py [--verbose]
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def get_service_account_creds():
    """Obtener ruta de credentials JSON."""
    creds_path = Path('setup/gdrive-credentials.json').resolve()
    
    if not creds_path.exists():
        # Intentar GOOGLE_APPLICATION_CREDENTIALS
        creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not creds_path:
            print("[ERROR] No se encontró setup/gdrive-credentials.json ni GOOGLE_APPLICATION_CREDENTIALS")
            return None
        creds_path = Path(creds_path).resolve()
    
    if not creds_path.exists():
        print(f"[ERROR] Credentials file not found: {creds_path}")
        return None
    
    try:
        with open(creds_path) as f:
            creds = json.load(f)
        print(f"[OK] Service account: {creds.get('client_email', 'unknown')}")
        return str(creds_path)
    except Exception as e:
        print(f"[ERROR] Failed to parse credentials: {e}")
        return None

def setup_pydrive_env(creds_path):
    """
    Configura variables de entorno para pydrive2.
    
    pydrive2/google-auth buscan credenciales en:
    1. GOOGLE_APPLICATION_CREDENTIALS (primera opción)
    2. ~/.config/pydrive2/ (configuración manual)
    3. OAuth interactivo (fallback - queremos evitar esto)
    """
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
    
    # Opcional: desactivar OAuth interactivo en pydrive2
    # (algunas versiones respetan esto)
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'
    
    print(f"[OK] GOOGLE_APPLICATION_CREDENTIALS={creds_path}")
    return True

def run_dvc_push(verbose=False):
    """Ejecutar dvc push -r storage."""
    cmd = ['.venv/bin/dvc', 'push', '-r', 'storage']
    
    if verbose:
        cmd.append('--verbose')
        print(f"[DEBUG] Ejecutando: {' '.join(cmd)}")
    
    try:
        # Timeout de 120 segundos para evitar bloqueos indefinidos
        result = subprocess.run(
            cmd,
            timeout=120,
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("[ERROR] dvc push timeout (120s). OAuth interactivo aún está siendo intentado.")
        print("[HINT] Intenta con setup/local.yaml en su lugar")
        return False
    except Exception as e:
        print(f"[ERROR] dvc push failed: {e}")
        return False

def main():
    verbose = '--verbose' in sys.argv
    
    # 1. Obtener ruta de credenciales
    creds_path = get_service_account_creds()
    if not creds_path:
        print("[ERROR] Cannot proceed without valid credentials")
        return 1
    
    # 2. Configurar variables de entorno
    setup_pydrive_env(creds_path)
    
    # 3. Ejecutar dvc push
    print("[INFO] Ejecutando dvc push con service account...")
    success = run_dvc_push(verbose)
    
    if success:
        print("[OK] dvc push completado exitosamente")
        return 0
    else:
        print("[ERROR] dvc push falló")
        return 1

if __name__ == '__main__':
    sys.exit(main())
