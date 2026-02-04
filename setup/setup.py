#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / "bin" / "python"
CONFIG_DIR = ROOT / ".mlops4ofp"
CONFIG_FILE = CONFIG_DIR / "setup.yaml"


# --------------------------------------------------
# Utilidades básicas (solo stdlib)
# --------------------------------------------------

def run(cmd, cwd=ROOT, check=True):
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=check)


def abort(msg):
    print(f"\n[ERROR] {msg}")
    sys.exit(1)


# --------------------------------------------------
# Bootstrap del entorno Python
# --------------------------------------------------

def ensure_venv():
    if VENV.exists():
        print("[INFO] .venv ya existe")
        return

    print("[INFO] Creando entorno virtual .venv")
    run([sys.executable, "-m", "venv", ".venv"])

    pip = VENV / "bin" / "pip"
    req = ROOT / "requirements.txt"

    if not req.exists():
        abort("requirements.txt no encontrado")

    print("[INFO] Instalando dependencias")
    run([str(pip), "install", "-r", str(req)])


# --------------------------------------------------
# Asegurar ejecución dentro del venv
# --------------------------------------------------

def ensure_running_in_venv(argv):
    if sys.executable == str(VENV_PYTHON):
        return

    print("[INFO] Reejecutando setup dentro de .venv")
    cmd = [str(VENV_PYTHON), __file__] + argv
    run(cmd)
    sys.exit(0)


# --------------------------------------------------
# Creación de env.sh (solo variables de entorno)
# --------------------------------------------------

def create_env_sh(cfg):
    ml = cfg.get("mlflow", {})
    if not ml.get("enabled", False):
        return False

    tracking_uri = ml.get("tracking_uri")
    if not tracking_uri:
        abort("MLflow habilitado pero falta mlflow.tracking_uri")

    CONFIG_DIR.mkdir(exist_ok=True)
    env_file = CONFIG_DIR / "env.sh"

    content = [
        "#!/usr/bin/env sh",
        "# Archivo generado por setup.py — NO editar a mano",
        "",
        f"export MLFLOW_TRACKING_URI={tracking_uri}",
        "",
    ]

    env_file.write_text("\n".join(content))
    env_file.chmod(0o755)

    print("[INFO] Creado .mlops4ofp/env.sh (MLflow)")
    return True


# --------------------------------------------------
# Configuración de DVC remoto
# --------------------------------------------------

def setup_dvc_remote(cfg):
    """Configura el remoto DVC según la configuración."""
    dvc_cfg = cfg.get("dvc", {})
    backend = dvc_cfg.get("backend")
    
    if not backend:
        return
    
    if backend == "local":
        path = dvc_cfg.get("path")
        if not path:
            abort("dvc.path no definido para backend local")
        
        storage_path = Path(path)
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configurar remoto DVC
        try:
            # Primero intenta agregar el remoto; si ya existe, lo modifica
            subprocess.run(
                ["dvc", "remote", "add", "-d", "storage", str(storage_path)],
                cwd=ROOT,
                capture_output=True
            )
        except:
            pass
        
        # Asegurar que está configurado con la ruta correcta
        subprocess.run(
            ["dvc", "remote", "modify", "storage", "url", str(storage_path)],
            cwd=ROOT,
            check=False
        )
        
        print(f"[INFO] DVC remoto 'storage' configurado: {path}")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MLOps4OFP — Setup del proyecto (una sola vez)"
    )
    parser.add_argument(
        "-c", "--config",
        help="Fichero YAML de configuración (modo no interactivo)",
        default=str(ROOT / "setup" / "example_setup.yaml")
    )

    args = parser.parse_args()

    print("====================================")
    print(" MLOps4OFP — Setup del proyecto")
    print("====================================")

    # 1️⃣ Bootstrap Python
    ensure_venv()

    # 2️⃣ Reejecutar dentro del venv
    ensure_running_in_venv(sys.argv[1:])

    # --------------------------------------------------
    # A partir de aquí YA estamos en el venv
    # --------------------------------------------------

    import yaml

    if CONFIG_FILE.exists():
        print("[INFO] El setup ya fue realizado previamente.")
        print(f"[INFO] Configuración existente en {CONFIG_FILE}")
        print("Siguientes pasos:")
        print("  make check-setup")
        return

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        abort(f"No existe el fichero de configuración: {cfg_path}")

    cfg = yaml.safe_load(cfg_path.read_text())
    if not isinstance(cfg, dict):
        abort("Fichero de configuración inválido")

    CONFIG_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(yaml.dump(cfg))

    has_env = create_env_sh(cfg)
    setup_dvc_remote(cfg)

    print("\n✔ Setup completado correctamente")
    print("Siguientes pasos:")
    print("  make check-setup")


if __name__ == "__main__":
    main()
