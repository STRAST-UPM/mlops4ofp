#!/usr/bin/env python3
import subprocess
import sys
import shutil

MIN_PYTHON = (3, 10)

def run(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return True, out.decode().strip()
    except Exception as e:
        return False, str(e)

def check_python():
    ok, out = run(["python3", "--version"])
    if not ok:
        print("❌ Python 3 no encontrado (python3)")
        return False

    version = out.split()[-1]
    major, minor, *_ = map(int, version.split("."))

    if (major, minor) < MIN_PYTHON:
        print(f"❌ Python {version} encontrado, se requiere >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")
        return False

    print(f"✔ Python {version}")
    return True

def check_tool(name, mandatory=True):
    if shutil.which(name) is None:
        if mandatory:
            print(f"❌ {name} no encontrado en PATH")
            return False
        else:
            print(f"⚠ {name} no encontrado (opcional)")
            return True

    ok, out = run([name, "--version"])
    if ok:
        print(f"✔ {name}: {out}")
    else:
        print(f"⚠ {name} encontrado pero no responde correctamente")
    return True

def main():
    print("===================================")
    print(" CHECK ENTORNO — MLOps4OFP")
    print("===================================")

    ok = True

    ok &= check_python()
    ok &= check_tool("git", mandatory=True)
    check_tool("dvc", mandatory=False)

    if not ok:
        print("\n❌ Entorno NO válido para continuar con el setup")
        sys.exit(1)

    print("\n✔ Entorno básico correcto")

if __name__ == "__main__":
    main()
