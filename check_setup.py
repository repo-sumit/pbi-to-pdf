#!/usr/bin/env python3
"""
pbi-to-pdf — environment check.

Verifies Python and the runtime dependencies needed to run the report
pipeline. Optional flags can auto-install anything missing.

  python check_setup.py                  # report status only
  python check_setup.py --auto-install   # install missing deps
"""

from __future__ import annotations

import argparse
import subprocess
import sys


# (pip-name, import-name) pairs for everything in requirements.txt
REQUIRED = [
    ("python-pptx", "pptx"),
    ("Pillow", "PIL"),
    ("PyMuPDF", "fitz"),
    ("markitdown", "markitdown"),
    ("matplotlib", "matplotlib"),
    ("reportlab", "reportlab"),
]


def _check_python() -> bool:
    v = sys.version_info
    if v < (3, 8):
        print(f"[X] Python 3.8+ required (found {v.major}.{v.minor}.{v.micro})")
        return False
    print(f"[OK] Python {v.major}.{v.minor}.{v.micro}")
    return True


def _check_packages() -> list[str]:
    missing: list[str] = []
    for pip_name, import_name in REQUIRED:
        try:
            __import__(import_name)
            print(f"[OK] {pip_name}")
        except ImportError:
            print(f"[X]  {pip_name} not installed")
            missing.append(pip_name)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="pbi-to-pdf — environment check.")
    ap.add_argument("--auto-install", action="store_true",
                    help="Install missing dependencies via pip")
    args = ap.parse_args()

    print("=" * 60)
    print("pbi-to-pdf — environment check")
    print("=" * 60)

    py_ok = _check_python()
    print()
    missing = _check_packages()

    print()
    if py_ok and not missing:
        print("All dependencies installed. You're ready to go.")
        print()
        print("Next:  python run_report.py \"path/to/dashboard.pbix\"")
        return 0

    if missing and args.auto_install:
        print("Auto-installing missing packages...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
            ])
        except subprocess.CalledProcessError as exc:
            print(f"[X] pip install failed (exit {exc.returncode})")
            return exc.returncode
        # Re-check
        print()
        missing = _check_packages()
        if not missing:
            print("\nAll dependencies installed.")
            return 0
        print(f"\n[X] Still missing: {', '.join(missing)}")
        return 1

    if missing:
        print("Run:  pip install -r requirements.txt")
        print("Or:   python check_setup.py --auto-install")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
