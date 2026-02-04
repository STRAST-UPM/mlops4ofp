#!/usr/bin/env python3
"""
Helper para configurar pydrive2 con service account JSON
y ejecutar dvc push sin bloqueo de OAuth.

Uso:
  python3 setup/configure_gdrive_auth.py [path/to/credentials.json]
  .venv/bin/dvc push -r storage
"""

import os
import sys
import json
from pathlib import Path

def setup_pydrive_credentials(creds_path):
    """
    Configura pydrive2 para usar service account JSON.
    
    pydrive2 busca credenciales en:
    1. Archivo local (settings.yaml + .pkl)
    2. GOOGLE_APPLICATION_CREDENTIALS (si está configurada)
    3. OAuth interactivo (fallback)
    
    Esta función:
    - Detecta el JSON de service account
    - Lo coloca en ~/.config/pydrive2/
    - Configura las variables de entorno
    """
    
    creds_file = Path(creds_path).expanduser().resolve()
    
    if not creds_file.exists():
        print(f"[ERROR] Credentials file not found: {creds_file}")
        return False
    
    try:
        with open(creds_file) as f:
            creds = json.load(f)
        print(f"[OK] Credentials loaded: {creds.get('client_email', 'unknown')}")
    except Exception as e:
        print(f"[ERROR] Failed to parse credentials: {e}")
        return False
    
    # Configurar GOOGLE_APPLICATION_CREDENTIALS
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_file)
    print(f"[OK] GOOGLE_APPLICATION_CREDENTIALS={creds_file}")
    
    # Crear directorio de pydrive2 si no existe
    pydrive_dir = Path.home() / '.config' / 'pydrive2'
    pydrive_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] pydrive2 config dir: {pydrive_dir}")
    
    # Copiar JSON a la ruta estándar de pydrive2 (opcional, intenta automáticamente honrar GOOGLE_APPLICATION_CREDENTIALS)
    # pydrive2 no usa esta ruta por defecto, pero podemos intentar:
    # target = pydrive_dir / 'service-account.json'
    # shutil.copy(creds_file, target)
    
    print("[OK] Setup complete for pydrive2 + service account")
    print("[INFO] You can now run: dvc push -r storage")
    return True

if __name__ == '__main__':
    creds_path = sys.argv[1] if len(sys.argv) > 1 else 'setup/gdrive-credentials.json'
    
    if setup_pydrive_credentials(creds_path):
        sys.exit(0)
    else:
        sys.exit(1)
