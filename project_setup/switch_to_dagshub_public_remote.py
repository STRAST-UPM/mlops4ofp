
#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd):
    print("[CMD]", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

def main():
    print("=== SWITCH TO DAGSHUB PUBLIC REMOTE ===")

    url = "https://dagshub.com/mlops4ofp/mlops4ofp.dvc"

    subprocess.call(["dvc", "remote", "remove", "storage"], cwd=ROOT)

    run(["dvc", "remote", "add", "-f", "storage", url])
    run(["dvc", "remote", "default", "storage"])

    subprocess.call(["dvc", "remote", "modify", "storage", "--local", "auth", "none"], cwd=ROOT)
    subprocess.call(["dvc", "remote", "modify", "storage", "--local", "user", ""], cwd=ROOT)
    subprocess.call(["dvc", "remote", "modify", "storage", "--local", "password", ""], cwd=ROOT)

    print("OK: remoto público configurado.")

if __name__ == "__main__":
    main()
