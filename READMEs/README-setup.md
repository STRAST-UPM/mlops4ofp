# MLOps4OFP — Guía Completa de Setup

Este documento es la **guía única, completa y autocontenida** para realizar el **setup desde cero** del proyecto **MLOps4OFP**.

Si sigues este documento **en orden**, el setup funciona.

---

## 0. Qué es el setup

### Qué ES el setup
- Se ejecuta **una sola vez por copia de trabajo**
- Define decisiones **estructurales** del proyecto
- Configura: Git, DVC, MLflow, entorno Python
- Prepara el proyecto para ejecutar las fases posteriores

### Qué NO ES el setup
- NO ejecuta fases (F01, F02, F03)
- NO crea variantes ni experimentos
- NO borra datasets existentes

> **Regla básica**: si el setup falla, **NO continúes**.

---

## 1. Requisitos previos — Herramientas locales

### 1.1 Git
```bash
git --version
```
- **macOS**: `brew install git`
- **Windows**: `winget install --id Git.Git`
- **Linux**: `sudo apt install git`

### 1.2 Python 3.10 o superior
```bash
python3 --version
```
- **macOS**: `brew install python`
- **Windows**: `winget install --id Python.Python.3.11`
- **Linux**: `sudo apt install python3 python3-venv python3-pip`

### 1.3 GNU Make
```bash
make --version
```
- **macOS**: `brew install make`
- **Windows**: `choco install make`
- **Linux**: `sudo apt install make`

### 1.4 DVC
```bash
pip install dvc
dvc --version
```

---

## 2. Setup LOCAL (sin remotes)

**RECOMENDADO para empezar.** Ideal para:
- Primera vez en el proyecto
- Desarrollo local
- Laboratorios docentes

### 2.1 Requisitos previos

Solo necesitas las **herramientas locales** de la Sección 1. **No requiere cuentas externas.**

### 2.2 Pasos del setup local

#### Paso 1: Clonar el repositorio base

```bash
git clone https://github.com/STRAST-UPM/mlops4ofp.git
cd mlops4ofp
```

#### Paso 2: Ejecutar el setup

```bash
make setup SETUP_CFG=setup/local.yaml
```

Este comando:
- Crea `.venv` (entorno virtual Python)
- Instala dependencias
- Configura Git local (sin remoto)
- Crea `.dvc_storage/` (almacenamiento DVC local)
- Configura MLflow en `./mlruns` (local)
- Genera `.mlops4ofp/setup.yaml`

#### Paso 3: Verificar

```bash
make check-setup
```

Debería ver:
```
✔ Python 3.13.3
✔ git version 2.52.0
✔ dvc 3.64.0
[OK] Git: no requerido por el setup
[OK] DVC: remoto 'storage' definido
[OK] DVC local: ruta accesible y escribible
[OK] MLflow: configuración válida
✔ Setup verificado correctamente
```

### 2.3 ¿Qué se ha creado?

```
.mlops4ofp/
  ├── setup.yaml          # Configuración
  └── env.sh              # Variables de entorno

.dvc_storage/             # Almacenamiento DVC local

.venv/                    # Entorno Python
```

Nota: si en la configuración (`setup/remote.yaml`) se especifica `git.remote_url`, el `make setup` creará o actualizará un remote git local llamado `publish` apuntando a esa URL. El objetivo `make publish*` usa ese remote `publish` para empujar los commits destinados a los usuarios.


### 2.4 Continuar con el pipeline

```bash
make help1                # Ver opciones Fase 01

# Crear variante
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic

# Ejecutar
make script1-run VARIANT=v001

# Publicar
make publish1 VARIANT=v001
```

---

**Roles y responsabilidades**

- **Usuarios (consumidores del proyecto)**: Solo deben ejecutar `make` targets documentados (por ejemplo `make publish1`, `make remove1`, `make clean-setup`). No deben interactuar directamente con Git, DVC, Google Drive ni DAGsHub.

- **Administrador del proyecto**: Ejecuta `make setup SETUP_CFG=setup/remote.yaml` una sola vez y se encarga de que los remotos y credenciales estén operativos (SSH keys, `DAGSHUB_TOKEN`, o credenciales de DVC/Google Drive). El setup creará un remote git local `publish` y configurará el remoto DVC `storage`.

- **Desarrolladores**: Trabajan en el repo de desarrollo (`origin` → `mlops4ofp`) y hacen `git push`/`pull` manualmente como de costumbre. Las publicaciones para usuarios se realizan desde la rama de publicación y el remote `publish`.

**Flujo para Usuarios (sin tocar cuentas)**

1. Asegurarse de que el administrador ya ejecutó `make setup` con `setup/remote.yaml` y que los remotos funcionan.
2. Crear o cambiar a la rama de publicación si aplica:
```bash
git checkout -b stable-for-users
```
3. Generar variante y publicar (todo gestionado por `make`):
```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic
make script1-run VARIANT=v001
make publish1 VARIANT=v001
```

`make publish1` realizará:
- Validaciones internas
- `dvc add` de artefactos
- `git commit` de cambios en `executions/` (si corresponde)
- `git push` hacia el remote `publish` (configurado por el setup)
- `dvc push -r storage` hacia el remote DVC configurado (local o gdrive)

Si alguna comprobación falla, `make` mostrará instrucciones claras para contactar con el administrador.

**Flujo para Desarrolladores**

- Seguir trabajando en el repo `mlops4ofp` (remoto `origin`) y hacer `git add/commit/push` manualmente.
- Si se desea publicar un snapshot para usuarios, crear la rama `stable-for-users` y seguir el flujo de usuario para ejecutar `make publish*`.


## 3. Setup REMOTO (GitHub + Google Drive + DAGsHub)

**Para equipos coordinados.** Ideal para:
- Trabajo en grupo
- Compartir datasets y experimentos
- Proyectos profesionales

### 3.1 Paso 1: Preparar cuentas externas (una sola vez por equipo)

Un miembro del equipo (el "admin") realiza esto:

#### 3.1.1 GitHub

1. Ir a https://github.com
2. **Crear repositorio PRIVADO** (vacío, sin README)
   - Nombre: `mlops4ofp-grupoXX`
3. **Elegir método de autenticación**:

   **Opción A: SSH (recomendado, más seguro)**
   ```bash
   ssh-keygen -t ed25519 -C "tu@email.com"
   cat ~/.ssh/id_ed25519.pub  # Copiar
   ```
   Agregar a GitHub → Settings → SSH and GPG keys
   
   Guardar URL: `git@github.com:grupoXX/mlops4ofp-grupoXX.git`

   **Opción B: HTTPS (más simple, requiere contraseña)**
   
   Guardar URL: `https://github.com/grupoXX/mlops4ofp-grupoXX.git`

#### 3.1.2 Google Drive (para DVC)

1. Ir a https://drive.google.com
2. **Crear carpeta**: `MLOps4OFP-grupoXX`
3. **Copiar el ID de la carpeta**:
   - Abre la carpeta
   - En la URL: `https://drive.google.com/drive/folders/[ESTE_ID]`
   - Ejemplo: `1MixQx_Z9Y2kJ8pQrXs3uVwXyZ1234567890`

#### 3.1.3 DAGsHub (para MLflow)

1. Crear cuenta en https://dagshub.com
2. **Crear repositorio privado**: `mlops4ofp-grupoXX`
3. **Generar Access Token**:
   - Settings → Tokens → New Token
   - Copiar token (no se mostrará nuevamente)
4. **Exportar en tu máquina** (nunca subir a GitHub):
   ```bash
   export DAGSHUB_TOKEN=xxxxxxxxxxxxxxxx
   ```
   Hacerlo permanente en `~/.bashrc` o `~/.zshrc`:
   ```bash
   echo 'export DAGSHUB_TOKEN=xxxxxxxxxxxxxxxx' >> ~/.zshrc
   source ~/.zshrc
   ```

### 3.2 Paso 2: Clonar y configurar el repositorio

Cada miembro del equipo:

```bash
git clone https://github.com/STRAST-UPM/mlops4ofp.git
cd mlops4ofp

# Cambiar remoto de STRAST-UPM a vuestro grupo
git remote remove origin

# Opción A: Con HTTPS
git remote add origin https://github.com/grupoXX/mlops4ofp-grupoXX.git

# O Opción B: Con SSH
# git remote add origin git@github.com:grupoXX/mlops4ofp-grupoXX.git

# Verificar
git remote -v
```

### 3.3 Paso 3: Editar setup/remote.yaml

Reemplaza `grupoXX` con vuestro nombre de usuario/grupo:

```yaml
git:
  remote_url: git@github.com:grupoXX/mlops4ofp-grupoXX.git
```

O si prefieres HTTPS:

```yaml
git:
  remote_url: https://github.com/grupoXX/mlops4ofp-grupoXX.git
```

También necesitas:

```yaml
dvc:
  path: "1MixQx_Z9Y2kJ8pQrXs3uVwXyZ1234567890"

mlflow:
  tracking_uri: https://dagshub.com/grupoXX/mlops4ofp-grupoXX.mlflow
```

### 3.4 Paso 4: Ejecutar el setup

```bash
echo $DAGSHUB_TOKEN
make setup SETUP_CFG=setup/remote.yaml
```

### 3.5 Paso 5: Verificar

```bash
make check-setup
```

### 3.6 Paso 6: Primer push a GitHub

```bash
git add -A
git commit -m "Initial commit: MLOps4OFP setup"
git push -u origin main
```

### 3.7 Continuar con el pipeline

```bash
make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic
make script1-run VARIANT=v001
make publish1 VARIANT=v001
```

---

## 4. Comparación: LOCAL vs REMOTO

| Aspecto | LOCAL | REMOTO |
|---------|-------|--------|
| **Git** | Sin remoto | GitHub |
| **DVC** | .dvc_storage local | Google Drive |
| **MLflow** | ./mlruns local | DAGsHub |
| **Cuentas** | Ninguna | 3 (GitHub, Google, DAGsHub) |
| **Para equipos** | No | Si |
| **Facilidad** | Muy simple | Intermedia |
| **Tiempo** | 2 min | 5 min |

---

## 5. Solución de problemas

### SSH vs HTTPS — ¿Cuál usar?

| Aspecto | SSH | HTTPS |
|---------|-----|-------|
| **URL** | `git@github.com:grupoXX/...` | `https://github.com/grupoXX/...` |
| **Seguridad** | Muy alta (clave pública/privada) | Alta (contraseña/token) |
| **Setup** | Requiere generar SSH key | Sin setup adicional |
| **Recomendación** | Para equipos/producción | Para simplificar |
| **macOS/Linux** | Funciona directamente | Funciona directamente |
| **Windows** | Funciona (con Git Bash) | Más simple |

**Si no sabes cuál usar**: Empieza con HTTPS. Si te pide contraseña, usa un "Personal Access Token" desde GitHub:
- Settings → Developer settings → Personal access tokens
- Selecciona permisos `repo` (acceso completo a repos privados)
- Usa el token como contraseña en Git

### Error: "Git remoto no coincide"

```bash
git remote remove origin
git remote add origin <URL_CORRECTA>
make check-setup
```

### Error: "DVC local: ruta no existe"

```bash
# Editar setup/remote.yaml con ID correcto
make setup SETUP_CFG=setup/remote.yaml
```

### Error: "DAGSHUB_TOKEN no definido"

```bash
echo $DAGSHUB_TOKEN

# Si no aparece:
export DAGSHUB_TOKEN=xxxxx
echo 'export DAGSHUB_TOKEN=xxxxx' >> ~/.zshrc
source ~/.zshrc
```

---

## 6. Rehacer el setup

```bash
make clean-setup
make setup SETUP_CFG=setup/local.yaml
```

---

## 7. Flujo correcto final

```bash
make setup SETUP_CFG=setup/local.yaml
make check-setup
make help
```

**FIN DEL README DE SETUP**
