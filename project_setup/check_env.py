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


if __name__ == "__main__":
    main()
