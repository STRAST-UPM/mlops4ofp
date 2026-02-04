
#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

def main():
    print("=== SWITCH TO DAGSHUB PRIVATE REMOTE ===")

    print("Para obtener token visitar:")
    print("DAGsHub → Settings → Developer → Personal Access Tokens")

    user = input("Usuario DAGsHub: ").strip()
    token = input("Token DAGsHub: ").strip()
    url = "https://dagshub.com/mlops4ofp/mlops4ofp.dvc"

    subprocess.call(["dvc", "remote", "remove", "storage"], cwd=ROOT)

    run(["dvc", "remote", "add", "-f", "storage", url])
    run(["dvc", "remote", "default", "storage"])

    run(["dvc", "remote", "modify", "storage", "--local", "auth", "basic"])
    run(["dvc", "remote", "modify", "storage", "--local", "user", user])
    run(["dvc", "remote", "modify", "storage", "--local", "password", token])

    print("OK: remoto privado configurado.")

if __name__ == "__main__":
    main()
