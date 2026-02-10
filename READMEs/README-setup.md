# ============================================================
# MLOps4OFP — Guía de configuraciones de setup
# ============================================================

Esta guía describe **cómo inicializar y validar el entorno de trabajo del proyecto MLOps4OFP** de forma reproducible, multiplataforma y sin pasos manuales ocultos.

El setup está diseñado para:
- desarrollo local
- docencia
- trabajo en equipo
- CI/CD

El proceso de setup **se ejecuta una sola vez por copia del repositorio**.

---

## Requisito obligatorio: versión de Python

⚠️ **Este proyecto requiere una versión concreta de Python.**  
El setup **no funcionará** con versiones no soportadas.

### Versiones soportadas
- ✅ **Python 3.10**
- ✅ **Python 3.11**

### Versiones NO soportadas
- ❌ Python 3.12
- ❌ Python 3.13 o superior
- ❌ Python 3.9 o inferior

**Motivo**  
El pipeline utiliza TensorFlow y librerías científicas que **no son estables** en Python ≥3.12 a día de hoy.  
Usar versiones no soportadas puede provocar:
- cuelgues silenciosos
- bloqueos durante el entrenamiento
- comportamiento no determinista

El script `setup.py` **verifica automáticamente** la versión de Python y aborta con un mensaje claro si no es compatible.

### Comprobar tu versión de Python

```bash
python --version
```

Debe mostrar algo como:

```
Python 3.10.x
```
o
```
Python 3.11.x
```

### Instalar Python 3.11 (si no lo tienes)

#### macOS (Homebrew)
```bash
brew install python@3.11
```

Ejecuta el setup con:
```bash
python3.11 setup.py -c setup/local.yaml
```

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
```

Ejecuta el setup con:
```bash
python3.11 setup.py -c setup/local.yaml
```

#### Windows
1. Descarga Python 3.11 desde: https://www.python.org/downloads/
2. Marca la opción **“Add Python to PATH”** durante la instalación
3. Ejecuta:
```bat
python setup.py -c setup\local.yaml
```

---

## Nota importante sobre el entorno virtual

- El entorno virtual `.venv` **se crea automáticamente** durante `make setup`.
- El usuario **NO debe crear ni activar** el entorno virtual manualmente.
- El Makefile está preparado para usar `.venv` internamente.
- La versión de Python **se decide antes** de crear el entorno virtual.

Ejemplo correcto:
```bash
make setup PYTHON=python3.11 SETUP_CFG=setup/local.yaml
```

---

## Flujos de setup disponibles

### 1. LOCAL (recomendado para desarrollo y docencia)
**Perfecto para:** desarrollo individual, testing, docencia, trabajo offline

```bash
make setup SETUP_CFG=setup/local.yaml
make check-setup
```

**Características:**
- DVC remote: carpeta local (`~/.dvc_storage`)
- Git: sin remote obligatorio
- Sin autenticación
- Rápido y reproducible

---

## Nota final

Este proyecto **no intenta “arreglar” el entorno automáticamente**.  
Prefiere:
- validaciones explícitas
- fallos tempranos
- contratos claros
