
#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

def main():
    print("=== SWITCH TO LOCAL REMOTE ===")

    subprocess.call(["dvc", "remote", "remove", "storage"], cwd=ROOT)
    run(["dvc", "remote", "add", "-f", "storage", "./local_dvc_store"])
    run(["dvc", "remote", "default", "storage"])

    print("OK: remoto DVC configurado a almacenamiento LOCAL.")

if __name__ == "__main__":
    main()
