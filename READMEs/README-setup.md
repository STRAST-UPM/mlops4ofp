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
  # Setup del proyecto

  Este documento explica cómo configurar y comprobar el proyecto en dos modos distintos:

  - Modo 1 — Todo local: usar [setup/local.yaml](setup/local.yaml). Recomendado para desarrollo y pruebas sin depender de servicios externos.
  - Modo 2 — Remoto (Dagshub / GitHub): usar [setup/remote.yaml](setup/remote.yaml). Recomendado para integración o publicación a remotos compartidos.

  En ambos casos la entrada principal es el script de setup y los targets del Makefile. Para detalles de implementación ver [setup/setup.py](setup/setup.py) y [Makefile](Makefile).

  **Resumen rápido:**

  - **Local:** `make setup SETUP_CFG=setup/local.yaml` → `make check-setup` → ejecutar variantes y publicar localmente.
  - **Remoto (Dagshub):** exportar credenciales `DAGSHUB_USER` y `DAGSHUB_TOKEN`, luego `make setup SETUP_CFG=setup/remote.yaml` → `make check-setup` → publicar a remotos.

  **Sugerencia:** siempre preferir ejecutar targets `make` del proyecto (ej.: `make nb1-run VARIANT=v001`) ya que el `Makefile` está preparado para usar el entorno virtual del proyecto y las rutas correctas.

  **Tabla de contenidos:**

  - **Requisitos (instalación por OS)**
  - **Modo Local**
  - **Modo Remoto (Dagshub / GitHub)**
  - **Comprobaciones: `check_env.py` y `check_setup.py`**
  - **Flujo típico de uso**
  - **Solución de problemas comunes**

  ## Requisitos (instalación por OS)

  Instale las herramientas básicas: Python 3.8+, Git, Make, y DVC. También se usa un entorno virtual `.venv` para aislar dependencias.

  - macOS (con Homebrew):

  ```bash
  brew update
  brew install python git make
  python3 -m pip install --user virtualenv
  # instalar dvc en el venv (ver pasos más abajo)
  ```

  - Ubuntu / Debian:

  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip git make
  ```

  - Windows (PowerShell / con Chocolatey):

  ```powershell
  choco install python git make
  # o instalar manualmente Python desde https://python.org
  ```

  Instalación del entorno Python y dependencias del proyecto (válido en cualquier OS):

  ```bash
  # desde la raíz del repositorio
  python3 -m venv .venv
  source .venv/bin/activate   # macOS / Linux
  # .venv\Scripts\Activate.ps1  # Windows PowerShell
  pip install -U pip
  pip install -r requirements.txt
  ```

  Nota: el `Makefile` está configurado para preferir `.venv/bin/python3` y `.venv/bin/dvc` si existen. Use `make setup` para que el `setup` automatice partes de estas tareas.

  ## Modo Local (setup/local.yaml)

  1. Editar `setup/local.yaml` si desea ajustar la ruta de almacenamiento DVC local (por defecto suele apuntar a `./.dvc_storage` o similar).
  2. Ejecutar:

  ```bash
  make setup SETUP_CFG=setup/local.yaml
  make check-setup
  ```

  3. Flujo típico de trabajo local (ejemplo fase 01):

  ```bash
  make variant1 VARIANT=v001 RAW=data/01-raw/01_explore_raw_raw.csv
  make nb1-run VARIANT=v001
  make script1-run VARIANT=v001
  make publish1 VARIANT=v001   # publica artefactos a storage local configurado
  ```

  El modo local no requiere tokens remotos; es útil para desarrollo y CI que no dependa de servicios externos.

  Qué cambiar en `setup/local.yaml`:

  - `storage.url`: ajustar la ruta local a donde desea que DVC almacene objetos (p. ej. `file://./.dvc_storage`).
  - `git.publish_remote` no es necesaria en el modo local, aunque puede configurarse si lo desea.

  ## Modo Remoto (Dagshub / GitHub) — setup/remote.yaml

  Este flujo está pensado para publicar a remotos gestionados (GitHub para el código y Dagshub para los artefactos DVC). No se usa Google Drive.

  Requisitos previos:

  - Cuenta en Dagshub con un repositorio DVC remoto configurado.
  - Variables de entorno en su máquina (o CI):

    - `DAGSHUB_USER` — su usuario Dagshub (o usuario de la organización).
    - `DAGSHUB_TOKEN` — token personal (crear desde su perfil en Dagshub).

  Cómo configurar:

  1. Exporte las variables (Unix/macOS):

  ```bash
  export DAGSHUB_USER="<tu_usuario>"
  export DAGSHUB_TOKEN="<tu_token>"
  ```

  En Windows PowerShell:

  ```powershell
  $env:DAGSHUB_USER = "<tu_usuario>"
  $env:DAGSHUB_TOKEN = "<tu_token>"
  ```

  2. Ejecutar el setup remoto:

  ```bash
  make setup SETUP_CFG=setup/remote.yaml
  make check-setup
  ```

  3. Verificaciones rápidas:

  - Compruebe que el remote git `publish` existe y apunta a Dagshub/GitHub:

  ```bash
  git remote -v
  ```

  - Compruebe los remotos DVC:

  ```bash
  .venv/bin/dvc remote list
  # o simplemente dvc remote list si su PATH apunta al venv
  ```

  4. Flujo típico remoto (ejemplo fase 01):

  ```bash
  make variant1 VARIANT=v001 RAW=data/01-raw/01_explore_raw_raw.csv
  make nb1-run VARIANT=v001
  make script1-run VARIANT=v001
  make publish1 VARIANT=v001   # hará dvc add + dvc push -r storage y git push al remote publish
  ```

  Notas de seguridad:

  - Guarde `DAGSHUB_TOKEN` en el gestor de secretos de su CI (GitHub Actions secrets, GitLab CI, etc.).
  - El `Makefile` y `setup/setup.py` están preparados para crear/actualizar un remote `publish` distinto de `origin`, de modo que las publicaciones no sobrescriban el remoto de desarrollo.

  ## Comprobaciones: `check_env.py` y `check_setup.py`

  El proyecto incluye comprobaciones automatizadas para validar el entorno y la configuración:

  - `setup/check_env.py`: valida herramientas instaladas (Python, pip, DVC, git) y la presencia de un entorno virtual.
  - `setup/check_setup.py`: valida el fichero de configuración `SETUP_CFG` (por ejemplo `setup/remote.yaml` o `setup/local.yaml`), remotos DVC/git y credenciales.

  Uso recomendado:

  ```bash
  # Ejecutar las comprobaciones a través del Makefile
  make check-setup

  # O ejecutarlas manualmente (dentro del venv):
  source .venv/bin/activate
  python setup/check_env.py
  python setup/check_setup.py --config setup/remote.yaml
  ```

  El objetivo de `make check-setup` es agrupar ambas comprobaciones; si falla, revise los mensajes y corrija las dependencias o variables de entorno necesarias.

  ## Flujo típico (resumen)

  1. Crear y activar entorno virtual
  2. `make setup SETUP_CFG=setup/local.yaml` (o `setup/remote.yaml`)
  3. `make check-setup`
  4. Crear variante: `make variant1 VARIANT=v001 RAW=...`
  5. Ejecutar notebook/script: `make nb1-run VARIANT=v001` y `make script1-run VARIANT=v001`
  6. Publicar: `make publish1 VARIANT=v001`

  ## Solución de problemas comunes

  - Si `make` usa el intérprete global en lugar del `.venv`, active el venv o use `python3 -m venv .venv` y reinstale dependencias.
  - Si `dvc push` falla con errores de autenticación en el modo remoto, compruebe `DAGSHUB_USER` y `DAGSHUB_TOKEN` y que el remote `storage` en `setup/remote.yaml` apunta a su repositorio Dagshub.
  - Para comprobar que `publish` no es `origin`, use `git remote -v` y asegúrese que `publish` está configurado según lo esperado.

  ## Referencias

  - Implementación: [setup/setup.py](setup/setup.py)
  - Orquestador: [Makefile](Makefile)
  - Flujos y guías específicas: [setup/README-SETUP-FLOWS.md](setup/README-SETUP-FLOWS.md)

  Si desea, puedo añadir ejemplos concretos de `setup/remote.yaml`, fragmentos de configuración para CI (GitHub Actions) o guías paso a paso para equipos. Indique qué prefiere.
