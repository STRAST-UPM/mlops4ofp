# ============================================================
# MLOps4OFP — Guía de configuraciones de setup
# ============================================================

## Requisito obligatorio: versión de Python

⚠️ **Este proyecto requiere una versión concreta de Python.**  
El setup **no funcionará** con versiones no soportadas.

### Versiones soportadas
- ✅ **Python 3.10**
- ✅ **Python 3.11**

### Versiones NO soportadas
- ❌ Python 3.12
- ❌ Python 3.13 o superior

**Motivo:**  
El pipeline utiliza TensorFlow y librerías científicas que **no son estables** en Python ≥3.12 a día de hoy.  
Usar versiones no soportadas puede provocar:
- cuelgues silenciosos
- bloqueos durante el entrenamiento
- comportamiento no determinista

El script `setup.py` **verifica automáticamente** la versión de Python y aborta con un mensaje claro si no es compatible.

---

### Cómo comprobar tu versión de Python

```bash
python --version
```

Debe mostrar algo como
Python 3.10.x
o
Python 3.11.x

### Cómo instalar Python 3.11 si no lo tienes

**macox (homebrew)
```bash
brew install python@3.11
```

Ejecuta el setup con:
```bash
python3.11 setup.py -c setup/local.yaml
```

**Ubuntu / Debian
```
sudo apt update
sudo apt install python3.11 python3.11-venv
```

Ejecuta el setup con:
```
python3.11 setup.py -c setup/local.yaml
```

**Windows

Descarga Python 3.11 desde: https://www.python.org/downloads/

Marca la opción “Add Python to PATH” durante la instalación

Ejecuta:
```
python setup.py -c setup\local.yaml
```

**Nota importante sobre entornos virtuales

El entorno virtual (.venv) no elige la versión de Python.

La versión de Python se decide antes de crear el entorno virtual.

Por eso, es fundamental ejecutar setup.py con una versión compatible desde el inicio.

Ejemplo correcto:
```
python3.11 setup.py -c setup/local.yaml
```


## Flujos disponibles

### 1. LOCAL (Recomendado para desarrollo local)
**Perfecto para: desarrolladores, testing, sin depender de servicios cloud**

```bash
make setup SETUP_CFG=setup/local.yaml
make check-setup
```

**Características:**
- DVC remote: `~/.dvc_storage` (carpeta local)
- Git: sin remote (commits locales) o puedes añadir `origin` manualmente
- Sin autenticación requerida
- Rápido, offline-first

**Cuándo usar:**
- Desarrollo local individual
- Testing del pipeline
- Cuando no hay acceso a internet o servicios cloud

---

### 2. REMOTE (GitHub + Google Drive)
**Perfecto para: equipos, colaboración, producción**

```bash
make setup SETUP_CFG=setup/remote.yaml
make check-setup
```

**Características:**
- Git remote: GitHub (`publish` remote)
- DVC remote: Google Drive (autenticación interactiva)
- Ideal para colaboración en equipo
- Requiere acceso a Google Drive

**Cuándo usar:**
- Trabajar en equipo
- Compartir datasets grandes
- Producción / reproducibilidad garantizada

**⚠️ Limitación actual:**
- La autenticación de Google Drive requiere interacción manual (OAuth browser)
- Alternativa: usar `setup/gdrive-remote.yaml` + service account JSON (en desarrollo)

---

### 3. GDRIVE-REMOTE (Google Drive + Service Account)
**Perfecto para: CI/CD no-interactivo, automatización**

```bash
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/setup/gdrive-credentials.json
make setup SETUP_CFG=setup/gdrive-remote.yaml
make check-setup
```

**Características:**
- Igual a REMOTE pero diseñado para service account JSON
- Autenticación completamente no-interactiva
- **Nota: Currently under testing** — pydrive2 en DVC puede no honrar automáticamente la variable de entorno

**Requisitos:**
- Descargar JSON de Google Cloud Console (Service Account)
- Compartir Google Drive folder con el email de la service account
- Configurar `GOOGLE_APPLICATION_CREDENTIALS`

**Estado:** ⏳ En pruebas — si `dvc push` intenta OAuth, usar `setup/local.yaml` mientras se resuelve

---

## Comandos comunes

```bash
# Setup inicial (local)
make setup SETUP_CFG=setup/local.yaml
make check-setup

# Crear variante
make variant1 VARIANT=v001 RAW=data/01-raw/01_explore_raw_raw.csv

# Ejecutar pipeline
make nb1-run VARIANT=v001
make script1-run VARIANT=v001

# Publicar (DVC + git)
make publish1 VARIANT=v001

# Eliminar variante
make remove1 VARIANT=v001

# Ver estado
make script1-check-dvc
make script1-check-results VARIANT=v001

# Limpiar
make clean-setup
```

---

## Recomendaciones

| Escenario | Configuración | Ventajas |
|-----------|---------------|----------|
| **Desarrollo individual** | `setup/local.yaml` | Rápido, offline, sin dependencias |
| **Equipo pequeño** | `setup/remote.yaml` | Colaboración, datasets compartidos |
| **CI/CD / Automatización** | `setup/gdrive-remote.yaml` | No-interactivo (una vez configurado) |
| **Testing** | `setup/local.yaml` | Simple, reproducible |

---

## Solución de problemas

### "dvc push se bloquea esperando OAuth"

**Causa:** Autenticación interactiva de Google Drive activada

**Soluciones:**
1. Usar `setup/local.yaml` (recomendado para desarrollo)
2. Usar service account + `setup/gdrive-remote.yaml` (para producción)
3. Permitir que se complete OAuth (abre browser, selecciona cuenta Google)

### "Remote 'publish' no configurado"

**Causa:** Setup en modo local (sin git remote)

**Solución:** 
- Si quieres GitHub: usa `setup/remote.yaml`
- Si solo quieres DVC local: nada que hacer, es normal

### "Permiso denegado en Google Drive"

**Causa:** Service account no tiene acceso a la carpeta

**Solución:**
1. Obtén el email de la service account: `cat setup/gdrive-credentials.json | grep client_email`
2. Comparte la carpeta de Google Drive con ese email
3. Intenta nuevamente: `make publish1 VARIANT=vXXX`

