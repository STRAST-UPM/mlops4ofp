#!/usr/bin/env python3
"""Comprobar modo de publicación.

Salida:
 - 'publish' si existe remote git 'publish'
 - 'none' si .mlops4ofp/setup.yaml existe y git.mode=='none'
 - 'missing' en otro caso
"""
import subprocess
from pathlib import Path
import sys
try:
    import yaml
except Exception:
    print("missing")
    sys.exit(0)


def has_publish_remote():
    try:
        out = subprocess.check_output(["git", "remote"], text=True)
        return any(line.strip() == "publish" for line in out.splitlines())
    except Exception:
        return False


def setup_mode_none():
    f = Path('.mlops4ofp/setup.yaml')
    if not f.exists():
        return False
    try:
        cfg = yaml.safe_load(f.read_text()) or {}
        return cfg.get('git', {}).get('mode') == 'none'
    except Exception:
        return False


if __name__ == '__main__':
    if has_publish_remote():
        print('publish')
    elif setup_mode_none():
        print('none')
    else:
        print('missing')
