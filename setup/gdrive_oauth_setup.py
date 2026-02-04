#!/usr/bin/env python3
"""
Script para setup inicial de Google Drive auth con OAuth manual
y almacenamiento de credenciales en pickle para uso no-interactivo futuro.

PyDrive2 + DVC requieren esto para evitar bloqueos OAuth indefinidos.

Uso (una sola vez):
  python3 setup/gdrive_oauth_setup.py
  
Después, dvc push funcionará sin bloqueos:
  dvc push -r storage
"""

import os
import sys
import pickle
from pathlib import Path

try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
except ImportError:
    print("[ERROR] pydrive2 not installed. Install with: pip install pydrive2")
    sys.exit(1)

def setup_oauth():
    """
    Ejecuta OAuth interactivo UNA SOLA VEZ y guarda credenciales.
    """
    
    auth_dir = Path.home() / '.config' / 'pydrive2'
    auth_dir.mkdir(parents=True, exist_ok=True)
    
    settings_file = auth_dir / 'settings.yaml'
    creds_pickle = auth_dir / 'credentials.pickle'
    
    print("[INFO] Google Drive OAuth Setup")
    print(f"[INFO] Credentials will be saved to: {creds_pickle}")
    print()
    
    # Crear settings.yaml si no existe
    if not settings_file.exists():
        settings_content = """client_config_backend: settings
client_config:
  client_id: 710796635688-iivsgbgsb6uv1fap6635dhvuei09o66c.apps.googleusercontent.com
  client_secret: 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
  redirect_uri: http://localhost:8080/
  auth_uri: https://accounts.google.com/o/oauth2/auth
  token_uri: https://accounts.google.com/o/oauth2/token
  auth_provider_x509_cert_url: https://www.googleapis.com/oauth2/v1/certs
  refresh_on_start: true

save_credentials: true
save_credentials_backend: file
save_credentials_file: .credentials
get_refresh_token: true
oauth_scope:
  - https://www.googleapis.com/auth/drive
  - https://www.googleapis.com/auth/drive.appdata
"""
        settings_file.write_text(settings_content)
        print(f"[OK] Created settings.yaml: {settings_file}")
    
    # Crear GoogleAuth y ejecutar OAuth
    print("[INFO] Opening browser for OAuth consent...")
    gauth = GoogleAuth(str(settings_file))
    gauth.LocalWebserverAuth()
    
    print(f"[OK] OAuth successful for: {gauth.user_email}")
    
    # Guardar credenciales en pickle
    with open(creds_pickle, 'wb') as f:
        pickle.dump(gauth.credentials, f)
    print(f"[OK] Credentials saved to pickle: {creds_pickle}")
    
    # Establecer GOOGLE_APPLICATION_CREDENTIALS si es necesario
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(auth_dir / '.credentials')
    
    print()
    print("[OK] Setup complete!")
    print("[INFO] You can now run: dvc push -r storage")
    print()
    return True

if __name__ == '__main__':
    try:
        setup_oauth()
    except KeyboardInterrupt:
        print("\n[CANCELLED] OAuth setup cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] OAuth setup failed: {e}")
        sys.exit(1)
