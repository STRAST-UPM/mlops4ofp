
# DAGsHub: Cuenta y Tokens

## 1. Crear cuenta en DAGsHub
1. Ir a https://dagshub.com
2. Click en **Sign Up**
3. Crear cuenta con email o GitHub

## 2. Crear Tokens
1. Login en DAGsHub
2. Ir a: **Settings → Developer → Personal Access Tokens**
3. Crear un token con permisos:
   - DVC/Data Storage
   - MLflow (opcional)
4. Copiar el token (solo se muestra una vez)

## 3. Uso en scripts del proyecto
- Para remoto privado usar: `switch_to_dagshub_private_remote.py`
- Para uso público no se necesita token
