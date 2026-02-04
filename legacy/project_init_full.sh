#!/bin/bash
set -e

echo "[INIT] Creando estructura base del proyecto mlops4ofp…"

mkdir -p project_setup
mkdir -p mlops4ofp/tools
mkdir -p mlops4ofp/configs
mkdir -p mlops4ofp/schemas
mkdir -p mlops4ofp/pipelines

mkdir -p scripts/01_explore
mkdir -p notebooks
#mkdir -p params

mkdir -p data/01-raw
mkdir -p data/02-interim
mkdir -p data/03-curated

mkdir -p outputs/interim
mkdir -p outputs/params_generated
mkdir -p outputs/metadata
mkdir -p outputs/reports

# .gitignore
if [ ! -f ".gitignore" ]; then
cat > .gitignore <<EOF
__pycache__/
*.pyc
*.pyo
.ipynb_checkpoints/

.venv/
.env/

data/01-raw/*
data/02-interim/*
data/03-curated/*

outputs/interim/*
outputs/params_generated/*
outputs/metadata/*
outputs/reports/*
EOF
echo "[INIT] .gitignore creado."
fi

# params/01_explore.json
#if [ ! -f "params/01_explore.json" ]; then
#cat > params/01_explore.json <<EOF
#{
#  "user_params": {},
#  "system_params": {}
#}
#EOF
#echo "[INIT] params/01_explore.json creado."
#fi

# requirements.txt
if [ ! -f "requirements.txt" ]; then
cat > requirements.txt <<EOF
pandas
numpy
pyyaml
jupyter
dvc
EOF
echo "[INIT] requirements.txt creado."
fi

############################################
# mlops4ofp/configs/user_config.yaml
############################################
if [ ! -f "mlops4ofp/configs/user_config.yaml" ]; then
cat > mlops4ofp/configs/user_config.yaml <<'EOF'
# Configuración de usuario para mlops4ofp

mode: "developer"   # "developer" o "student"

# URL remota de DVC (DAGsHub, GDrive, S3, etc.)
dvc_remote_url: ""

# MLflow (por ejemplo DAGsHub)
mlflow_tracking_uri: ""

# Credenciales DAGsHub (opcionales)
dagshub_username: ""
dagshub_token: ""
EOF
echo "[INIT] user_config.yaml creado."
fi

############################################
# mlops4ofp/schemas/traceability_schema.yaml
############################################
if [ ! -f "mlops4ofp/schemas/traceability_schema.yaml" ]; then
cat > mlops4ofp/schemas/traceability_schema.yaml <<'EOF'
# Esquema conceptual de trazabilidad para mlops4ofp

assets:
  dataset:
    attributes:
      - name: path
        description: Ruta al fichero en el repositorio
      - name: stage
        description: Fase del pipeline que lo genera
      - name: created_at
        description: Fecha/hora de creación
  params:
    attributes:
      - name: source_stage
        description: Fase que generó estos parámetros
      - name: values
        description: Diccionario de parámetros

metadata:
  fields:
    - name: stage
      description: Nombre de la fase (ej. '01_explore')
    - name: timestamp
      description: Fecha/hora UTC de ejecución
    - name: inputs
      description: Lista de rutas de entrada
    - name: outputs
      description: Lista de rutas de salida
    - name: params
      description: Parámetros usados
    - name: git
      description: Información de commit/branch/cleanliness
EOF
echo "[INIT] traceability_schema.yaml creado."
fi

############################################
# mlops4ofp/tools/params.py
############################################
#if [ ! -f "mlops4ofp/tools/params.py" ]; then
#cat > mlops4ofp/tools/params.py <<'EOF'
cat > /dev/null <<'EOF'
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    """Carga un JSON si existe, si no devuelve dict vacío."""
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_params(
    user_param_path: str,
    inherited_param_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Carga parámetros de usuario, sistema y heredados.

    - user_param_path: ruta al JSON de parámetros de la fase (user_params, system_params).
    - inherited_param_paths: lista de rutas a JSON generados por fases anteriores.

    Devuelve un diccionario con:
      - user_params
      - system_params
      - inherited_params
    """
    cfg = _load_json(Path(user_param_path))
    user_params = cfg.get("user_params", {})
    system_params = cfg.get("system_params", {})

    inherited_params: Dict[str, Any] = {}
    if inherited_param_paths:
        for p in inherited_param_paths:
            inherited_params.update(_load_json(Path(p)))

    return {
        "user_params": user_params,
        "system_params": system_params,
        "inherited_params": inherited_params,
    }


def save_generated_params(output_path: str, params_dict: Dict[str, Any]) -> None:
    """Guarda parámetros generados por una fase (p.ej. Tu) en un JSON."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(params_dict, indent=2))
EOF
#echo "[INIT] mlops4ofp/tools/params.py creado."
#fi

############################################
# mlops4ofp/tools/traceability.py
############################################
if [ ! -f "mlops4ofp/tools/traceability.py" ]; then
cat > mlops4ofp/tools/traceability.py <<'EOF'
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def _git_info() -> Dict[str, Any]:
    """Recupera información básica de git (commit, branch, limpieza)."""

    def run(cmd):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            return out.decode().strip()
        except Exception:
            return None

    status = run(["git", "status", "--porcelain"])
    return {
        "commit": run(["git", "rev-parse", "HEAD"]),
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "status_clean": (status == ""),
    }


def write_metadata(
    stage: str,
    inputs: List[str],
    outputs: List[str],
    params: Dict[str, Any],
    metadata_path: str,
) -> None:
    """Escribe un JSON con trazabilidad básica de una fase.

    - stage: nombre de la fase (p.ej. '01_explore')
    - inputs: lista de rutas de activos de entrada
    - outputs: lista de rutas de activos de salida
    - params: parámetros usados (user/system/inherited)
    - metadata_path: ruta del JSON de salida
    """
    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "stage": stage,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "git": _git_info(),
    }
    metadata_path.write_text(json.dumps(data, indent=2))
EOF
echo "[INIT] mlops4ofp/tools/traceability.py creado."
fi


############################################
# dvc.yaml (solo Fase 01)
############################################
if [ ! -f "dvc.yaml" ]; then
cat > dvc.yaml <<'EOF'
stages:
  explore:
    cmd: python scripts/01_explore/01_run_explore.py
    deps:
      - data/01-raw
      - scripts/01_explore/01_run_explore.py
      - params/01_explore.json
    outs:
      - data/02-interim/01_dataset_explored.parquet
      - outputs/params_generated/01_explore.json
      - outputs/metadata/01_explore.json
EOF
echo "[INIT] dvc.yaml creado."
fi

############################################
# Makefile
############################################
if [ ! -f "Makefile" ]; then
cat > Makefile <<'EOF'
############################################
# MLOps4OFP — Makefile FASE 01 (explore)
############################################

NOTEBOOK=notebooks/01_explore.ipynb

INTERIM_DATA=data/02-interim/01_dataset_explored.parquet
NB_PARAMS=outputs/params_generated/01_explore_notebook.json
NB_META=outputs/metadata/01_explore_notebook.json
NB_REPORT=outputs/reports/01_explore_notebook_report.html

SCRIPT=scripts/01_explore/01_run_explore.py

############################################
# 1. DESARROLLO NOTEBOOK (pre-script)
############################################

nb-run:
\tjupyter nbconvert --to notebook --execute $(NOTEBOOK) --output $(NOTEBOOK)

nb-save:
\tdvc add $(INTERIM_DATA)
\tdvc add $(NB_PARAMS)
\tdvc add $(NB_META)
\tdvc add $(NB_REPORT)
\tgit add *.dvc .gitignore
\tgit commit -m "dev: notebook outputs saved (01_explore)"

nb-push:
\tdvc push

nb-git:
\tgit add $(NOTEBOOK)
\tgit commit -m "dev: update notebook 01_explore"
\tgit push

nb-dev: nb-run nb-save nb-push nb-git

############################################
# 2. VERSIONADO
############################################

tag-stage-ready:
\tgit tag stage-ready-fase01
\tgit push origin stage-ready-fase01

tag-script-ready:
\tgit tag script-ready-fase01
\tgit push origin script-ready-fase01

tag-stable:
\tgit tag stable-fase01
\tgit push origin stable-fase01

############################################
# 3. SCRIPT DE FASE
############################################

script-run:
\tpython $(SCRIPT)

script-repro:
\tdvc repro
\tdvc push

############################################
# 4. CHECKS
############################################

check:
\tpython scripts/01_explore/01_check_artifact.py \\
\t\tdata/02-interim/01_dataset_explored.parquet \\
\t\toutputs/interim/01_dataset_explored.parquet

############################################
# 5. LIMPIEZA
############################################

clean-outputs:
\trm -rf outputs/interim/* outputs/metadata/* outputs/params_generated/*
\trm -rf data/02-interim/* data/03-curated/*

############################################
# 6. AYUDA
############################################

help:
\t@echo "make nb-dev           Ejecuta notebook + guarda outputs en DVC + sube"
\t@echo "make nb-run           Ejecuta notebook"
\t@echo "make nb-save          Añade outputs notebook a DVC"
\t@echo "make nb-push          Sube outputs al remoto DVC"
\t@echo "make nb-git           Commit + push del notebook"
\t@echo "make script-run       Ejecuta script 01_explore"
\t@echo "make script-repro     Ejecuta dvc repro + push"
\t@echo "make tag-stage-ready  Marca notebook listo"
\t@echo "make tag-script-ready Marca script lista"
\t@echo "make tag-stable       Marca fase estable"
\t@echo "make check            Compara artifacts"
\t@echo "make clean-outputs    Limpia outputs"
EOF
echo "[INIT] Makefile creado."
fi




############################################
# README.md
############################################

if [ ! -f "README.md" ]; then
cat > README.md <<EOF
# mlops4ofp — Proyecto base (Fase 01)

Este repositorio contiene la estructura base del proyecto mlops4ofp
con la Fase 01 (explore) preparada para desarrollo y uso docente.

- Fase 01 (explore):
  - Notebook: notebooks/01_explore.ipynb
  - Script:   scripts/01_explore/01_run_explore.py
  - Parámetros: params/01_explore.json

Para más detalles ver:
- README_DEV.md
- README_STUDENTS.md
EOF
echo "[INIT] README.md creado."
fi

############################################
# Inicializar Git y DVC si no existen
############################################
if [ ! -d ".git" ]; then
echo "[INIT] Inicializando repositorio Git…"
git init
git add .
git commit -m "Initial project structure"
fi

if [ ! -d ".dvc" ]; then
echo "[INIT] Inicializando DVC…"
dvc init
fi

echo "[INIT] ✔ Proyecto mlops4ofp preparado correctamente."


############################################
# add_raw_dataset.py
############################################
cat > project_setup/add_raw_dataset.py <<'EOF'
#!/usr/bin/env python3
import shutil
import sys
import subprocess
from pathlib import Path

ROOT = Path(file).resolve().parents[1]
RAW_DIR = ROOT / "data" / "01-raw"

def main():
if len(sys.argv) != 2:
print("Uso: add_raw_dataset.py <ruta_dataset.csv>")
sys.exit(1)
src = Path(sys.argv[1]).resolve()
if not src.exists():
    print(f"[ERROR] No existe el fichero: {src}")
    sys.exit(1)

RAW_DIR.mkdir(parents=True, exist_ok=True)
dst = RAW_DIR / src.name
shutil.copy2(src, dst)
print(f"[ADD_RAW] Copiado dataset a {dst}")

try:
    subprocess.check_call(["dvc", "add", str(dst)], cwd=ROOT)
    print("[ADD_RAW] Dataset registrado en DVC.")
except subprocess.CalledProcessError:
    print("[ADD_RAW] WARNING: no se pudo registrar el dataset en DVC (¿DVC inicializado?).")
if name == "main":
main()
EOF

chmod +x project_setup/add_raw_dataset.py

############################################
#check_env.py
############################################
cat > project_setup/check_env.py <<'EOF'
#!/usr/bin/env python3
import subprocess

def check(cmd):
try:
out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
print(f"OK: {' '.join(cmd)} → {out.decode().strip()}")
except Exception as e:
print(f"ERROR: {' '.join(cmd)} → {e}")

def main():
print("=== CHECK ENTORNO ===")
check(["python", "--version"])
check(["git", "--version"])
check(["dvc", "--version"])

if name == "main":
main()
EOF
chmod +x project_setup/check_env.py

############################################
#repro_explore.py
############################################
cat > project_setup/repro_explore.py <<'EOF'
#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(file).resolve().parents[1]

if name == "main":
print("[REPRO] Ejecutando dvc repro explore…")
subprocess.check_call(["dvc", "repro", "explore"], cwd=ROOT)
EOF
chmod +x project_setup/repro_explore.py

############################################
# setup_dev.py
############################################
cat > project_setup/setup_dev.py <<'EOF'
#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(file).resolve().parents[1]

def main():
print("[SETUP_DEV] Instalando dependencias…")
req = ROOT / "requirements.txt"
if req.exists():
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
if not (ROOT / ".git").exists():
    print("[SETUP_DEV] Inicializando Git…")
    subprocess.check_call(["git", "init"], cwd=ROOT)

print("[SETUP_DEV] Listo.")
if name == "main":
main()
EOF
chmod +x project_setup/setup_dev.py

############################################
# setup_user.py
############################################
cat > project_setup/setup_user.py <<'EOF'
#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(file).resolve().parents[1]

def main():
print("[SETUP_USER] Instalando dependencias…")
req = ROOT / "requirements.txt"
if req.exists():
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
print("[SETUP_USER] Listo.")

if name == "main":
main()
EOF
chmod +x project_setup/setup_user.py

############################################
# setup_remotes.py
############################################
cat > project_setup/setup_remotes.py <<'EOF'
#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(file).resolve().parents[1]

def run(cmd):
print("[CMD]", " ".join(cmd))
subprocess.check_call(cmd, cwd=ROOT)

def main():
print("=== CONFIGURACIÓN DE REMOTOS ===")
git_url = input("URL remoto Git (ENTER para omitir): ").strip()
if git_url:
    subprocess.call(["git", "remote", "remove", "origin"], cwd=ROOT)
    run(["git", "remote", "add", "origin", git_url])

dvc_url = input("URL remoto DVC (ENTER para omitir): ").strip()
if dvc_url:
    subprocess.call(["dvc", "remote", "remove", "storage"], cwd=ROOT)
    run(["dvc", "remote", "add", "-f", "storage", dvc_url])
    run(["dvc", "remote", "default", "storage"])

print("[SETUP_REMOTES] Listo.")
if name == "main":
main()
EOF
chmod +x project_setup/setup_remotes.py

############################################
# 01_run_explore.py (completo)
############################################
cat > scripts/01_explore/01_run_explore.py <<'EOF'
#!/usr/bin/env python3
"""
Fase 01 — EXPLORE

Lee el primer CSV en data/01-raw/

Genera data/02-interim/01_dataset_explored.parquet

Extrae Tu = percentil 90 de la columna 'valor'

Guarda Tu en outputs/params_generated/01_explore.json

Escribe metadata con trazabilidad en outputs/metadata/01_explore.json
"""

from pathlib import Path
import pandas as pd

from mlops4ofp.tools.params import load_params, save_generated_params
from mlops4ofp.tools.traceability import write_metadata

ROOT = Path(file).resolve().parents[2]

RAW_DIR = ROOT / "data" / "01-raw"
OUT_DATA = ROOT / "data" / "02-interim" / "01_dataset_explored.parquet"
OUT_PARAMS = ROOT / "outputs" / "params_generated" / "01_explore.json"
OUT_META = ROOT / "outputs" / "metadata" / "01_explore.json"
PARAMS_PATH = ROOT / "params" / "01_explore.json"

def compute_tu(df: pd.DataFrame) -> float:
if "valor" not in df.columns:
raise ValueError("El dataset no contiene la columna 'valor'.")
return float(df["valor"].quantile(0.90))

def main():
raw_files = list(RAW_DIR.glob("*.csv"))
if not raw_files:
raise RuntimeError("No hay datos RAW en data/01-raw/")
raw = raw_files[0]
print(f"[EXPLORE] RAW seleccionado: {raw}")

df = pd.read_csv(raw)
OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUT_DATA)
print(f"[EXPLORE] Dataset explorado → {OUT_DATA}")

Tu = compute_tu(df)
save_generated_params(OUT_PARAMS, {"Tu": Tu})
print(f"[EXPLORE] Tu={Tu} guardado en {OUT_PARAMS}")

params = load_params(PARAMS_PATH, None)
write_metadata(
    stage="01_explore",
    inputs=[str(raw), str(PARAMS_PATH)],
    outputs=[str(OUT_DATA), str(OUT_PARAMS)],
    params=params,
    metadata_path=str(OUT_META),
)
print(f"[EXPLORE] Metadata generada en {OUT_META}")


if name == "main":
main()
EOF
chmod +x scripts/01_explore/01_run_explore.py

############################################
# 01_check_artifact.py
############################################
cat > scripts/01_explore/01_check_artifact.py <<'EOF'
#!/usr/bin/env python3
"""
Compara dos ficheros Parquet:

hash MD5

shape

columnas

igualdad exacta de contenido
"""
import sys
import hashlib
import pandas as pd
from pathlib import Path

def file_hash(path):
with open(path, "rb") as f:
return hashlib.md5(f.read()).hexdigest()

def main(a, b):
pa = Path(a); pb = Path(b)
if not pa.exists():
print(f"❌ No existe {pa}"); return
if not pb.exists():
print(f"❌ No existe {pb}"); return

print(f"Comparando:\n A: {pa}\n B: {pb}")

print("MD5 A:", file_hash(pa))
print("MD5 B:", file_hash(pb))
print("Hashes iguales:", file_hash(pa) == file_hash(pb))

df_a = pd.read_parquet(pa)
df_b = pd.read_parquet(pb)

print("Shape A:", df_a.shape)
print("Shape B:", df_b.shape)
print("Shapes iguales:", df_a.shape == df_b.shape)

print("Columnas iguales:", list(df_a.columns) == list(df_b.columns))

print("Contenido exactamente igual:", df_a.equals(df_b))


if name == "main":
if len(sys.argv) != 3:
print("Uso: 01_check_artifact.py <file_A.parquet> <file_B.parquet>")
sys.exit(1)
main(sys.argv[1], sys.argv[2])
EOF
chmod +x scripts/01_explore/01_check_artifact.py

############################################
# README_DEV.md
############################################
cat > README_DEV.md <<'EOF'
# README_DEV — Guía de Desarrollo (Fase 01)

Esta guía describe el ciclo profesional de trabajo en la fase 01 (explore).

## 1. Primeros pasos

Clonar y configurar entorno:
```bash
git clone URL
cd mlops4ofp
python project_setup/setup_dev.py
python project_setup/setup_remotes.py
```

Añadir dataset RAW (solo cuando hay uno nuevo):
```bash
python project_setup/add_raw_dataset.py ruta/dataset.csv
```
Esto copia el dataset a data/01-raw/ y lo registra con DVC.

## 2. Desarrollo del notebook
Editar:
```notebooks/01_explore.ipynb```
Guardar outputs bajo DVC:
```make nb-dev```

Este comando:
- Ejecuta el notebook
- Genera artifacts
- Los registra en DVC
- Hace commit + push del notebook

Puedes iterar tantas veces como sea necesario.

## 3. Congelar el notebook (stage-ready)
```make tag-stage-ready```
Esto marca en Git que la versión del notebook está lista para ser
portada a script.

## 4. Desarrollo de la script reproducible
Implementar la lógica final en:
```scripts/01_explore/01_run_explore.py```

Probar la script:
```make script-run```

## 5. Validación notebook ↔ script
Para comprobar que la script reproduce el comportamiento del notebook:

```make check```

(Es necesario que ```scripts/01_explore/01_check_artifact.py``` esté
implementado correctamente.)

## 6. Reproducibilidad con DVC

Cuando la script está validada:
```make script-repro```

Esto ejecuta el pipeline DVC y sube artefactos al remoto (si está
configurado).

## 7. Congelar y cerrar fase
Marcar la script como lista:
```make tag-script-ready```

Marcar la fase completa (script+DVC) como estable:
```make tag-stable```

## 8. Limpieza
Si quieres regenerar outputs desde cero:
```make clean-outputs```

EOF