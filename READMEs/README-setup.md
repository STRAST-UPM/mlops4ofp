# ============================================================
# MLOps4OFP - Guia de configuraciones de setup
# ============================================================

Esta guia describe como inicializar y validar el entorno de trabajo del proyecto
MLOps4OFP de forma reproducible y sin pasos manuales ocultos.

El setup esta pensado para:
- desarrollo local
- docencia
- trabajo en equipo
- CI/CD

El proceso de setup se ejecuta una sola vez por copia del repositorio.

---

## Requisito obligatorio: version de Python

Este proyecto requiere una version concreta de Python.
El setup no funciona con versiones no soportadas.

Version soportada:
- Python 3.11.x (exactamente 3.11)

Versiones NO soportadas:
- Python 3.12 o superior
- Python 3.10 o inferior

Este proyecto requiere exactamente Python 3.11.
El setup aborta si se ejecuta con cualquier otra version.

### Comprobar tu version
python --version

### Instalar Python 3.11 (si no lo tienes)

macOS (Homebrew):
brew install python@3.11

Ubuntu / Debian:
sudo apt update
sudo apt install python3.11 python3.11-venv

Windows:
- Descarga Python 3.11 desde https://www.python.org/downloads/
- Activa "Add Python to PATH" en la instalacion

---

## Entorno virtual (.venv)

- .venv se crea automaticamente durante make setup.
- No hay que crear ni activar .venv manualmente.
- El Makefile usa .venv/bin/python3 si existe.
- La version de Python se decide antes de crear .venv.

---

## Herramientas requeridas

| Herramienta | Estado |
|-------------|--------|
| git | Obligatorio |
| Python 3.11 | Obligatorio |
| make | Obligatorio |
| dvc | Obligatorio |

**Verificar instalación:**
```bash
git --version
python --version
make --version
dvc --version
```

Instalar en macOS (homebrew)
```bash
brew install make
brew install dvc
```

Instalar en Ubuntu / Debian
```bash
sudo apt update
sudo apt install make
sudo apt install dvc
```

Instalar en Windows
- Make: instala Chocolatey y ejecuta choco install make
- DVC: instala con pip en el Python del sistema:
```bash
pip install dvc
```


---

## Flujos de setup disponibles

El setup se ejecuta con:
make setup SETUP_CFG=setup/local.yaml

Siempre termina con:
make check-setup

### 1) LOCAL (recomendado para desarrollo y docencia)

make setup SETUP_CFG=setup/local.yaml
make check-setup

Caracteristicas:
- DVC remote: local en ./.dvc_storage
- MLflow: local en file:./mlruns
- Git: modo none (no configura remotos)
- Sin autenticacion

### 2) REMOTE (DAGsHub + Git remoto)

export DAGSHUB_USER=tu_usuario
export DAGSHUB_TOKEN=tu_token

make setup SETUP_CFG=setup/remote.yaml
make check-setup

Caracteristicas:
- DVC: DAGsHub (remote "storage")
- MLflow: DAGsHub (tracking remoto)
- Git: configura remote "publish" con git.remote_url

Requisitos:
- Cuenta y repo en DAGsHub
- DAGSHUB_USER y DAGSHUB_TOKEN en el entorno

---

## Que genera el setup

- `.venv/` con dependencias instaladas
- `.mlops4ofp/setup.yaml` (configuración activa)
- `.mlops4ofp/env.sh` (si MLflow está habilitado; importado automáticamente por Makefile)

---

## Comandos útiles

```bash
make check-setup        # Validar setup actual
make clean-setup        # Limpiar completamente (.venv, .mlops4ofp, DVC local)
```

`make clean-setup` devuelve el proyecto al estado post-clone. Úsalo antes de reintentar `make setup` si hay errores.

---

## Recomendaciones importantes

- **Windows:** Ejecuta en Git Bash o Git CMD
- **Errores en setup:** Ejecuta `make clean-setup` antes de reintentar
- El proyecto valida explícitamente en lugar de "arreglar" automáticamente
