#!/usr/bin/env python3
"""
DREX — Optional Dependency Installer

Installs optional dependencies for enhanced features:
  - webrtcvad: Voice Activity Detection (better silence detection)
  - pvporcupine: Wake word detection (preferred, low CPU)
  - openwakeword: Wake word detection (free fallback)
  - cerebras-cloud-sdk: Cerebras AI provider API

Usage:
    python scripts/install_optional.py          # Install all optional deps
    python scripts/install_optional.py --vad     # Only VAD
    python scripts/install_optional.py --wake    # Only wake word
    python scripts/install_optional.py --cerebras # Only Cerebras SDK
"""

import argparse
import subprocess
import sys
import importlib


# ── Optional dependency groups ───────────────────────────────

OPTIONAL_GROUPS = {
    "vad": {
        "pip_names": ["webrtcvad"],
        "import_names": ["webrtcvad"],
        "description": "Voice Activity Detection (better silence detection)",
    },
    "wake": {
        "pip_names": ["pvporcupine", "openwakeword"],
        "import_names": ["pvporcupine", "openwakeword"],
        "description": "Wake word detection (hands-free activation)",
    },
    "cerebras": {
        "pip_names": ["cerebras-cloud-sdk"],
        "import_names": ["cerebras.cloud.sdk"],
        "description": "Cerebras AI provider (ultra-fast inference)",
    },
    "ocr": {
        "pip_names": ["pytesseract", "pymupdf", "pdfplumber"],
        "import_names": ["pytesseract", "fitz", "pdfplumber"],
        "description": "Document OCR and PDF extraction",
    },
}

ALL_GROUPS = list(OPTIONAL_GROUPS.keys())

INSTALLED = {}
FAILED = []
SKIPPED = []


def check_installed(import_name: str) -> bool:
    """Check if a package is already installed without importing it."""
    # Map module names to their pip package equivalents for checking
    import_map = {
        "cerebras.cloud.sdk": "cerebras_cloud_sdk",
        "fitz": "pymupdf",
        "webrtcvad": "webrtcvad",
    }
    pkg_check = import_map.get(import_name, import_name.replace("-", "_").replace(".", "_"))
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        pass
    try:
        importlib.import_module(pkg_check)
        return True
    except ImportError:
        return False


def install_group(group_name: str) -> bool:
    """Install a group of optional dependencies."""
    group = OPTIONAL_GROUPS.get(group_name)
    if not group:
        print(f"  ⚠  Unknown group: {group_name}")
        return False

    pip_packages = group["pip_names"]
    description = group["description"]

    print(f"\n  [{group_name}] {description}")
    print(f"  {'─' * (len(group_name) + len(description) + 4)}")

    all_installed = all(
        check_installed(imp) for imp in group["import_names"]
    )

    if all_installed:
        print(f"    ✅ All already installed")
        INSTALLED[group_name] = pip_packages
        return True

    missing = [
        pkg for i, pkg in enumerate(pip_packages)
        if not check_installed(group["import_names"][i])
    ]

    if not missing:
        return True

    print(f"    Installing: {', '.join(missing)}...")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"    ✅ Successfully installed: {', '.join(missing)}")
            INSTALLED[group_name] = missing
            return True
        else:
            print(f"    ❌ Failed to install: {', '.join(missing)}")
            print(f"       {result.stderr.strip()}")
            FAILED.append(group_name)
            return False
    except subprocess.TimeoutExpired:
        print(f"    ⏱  Timeout installing {', '.join(missing)}")
        FAILED.append(group_name)
        return False
    except Exception as e:
        print(f"    ❌ Error: {e}")
        FAILED.append(group_name)
        return False


def check_installed_status():
    """Print status of all optional dependency groups."""
    print()
    print("  Current optional dependency status:")
    print("  {'─' * 40}")

    for group_name, group in OPTIONAL_GROUPS.items():
        statuses = []
        for imp in group["import_names"]:
            if check_installed(imp):
                statuses.append(f"✅ {imp}")
            else:
                statuses.append(f"❌ {imp}")
        status_str = ", ".join(statuses)
        print(f"    {group_name:<12} {status_str}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="DREX — Optional Dependency Installer"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Install all optional dependencies"
    )
    parser.add_argument(
        "--vad", action="store_true",
        help="Install VAD (webrtcvad)"
    )
    parser.add_argument(
        "--wake", action="store_true",
        help="Install wake word (pvporcupine + openwakeword)"
    )
    parser.add_argument(
        "--cerebras", action="store_true",
        help="Install Cerebras SDK"
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="Install OCR/PDF tools"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check current installation status"
    )

    args = parser.parse_args()

    if args.check:
        check_installed_status()
        return

    groups_to_install = []

    if args.all or not any([args.vad, args.wake, args.cerebras, args.ocr]):
        groups_to_install = ALL_GROUPS
    else:
        if args.vad:
            groups_to_install.append("vad")
        if args.wake:
            groups_to_install.append("wake")
        if args.cerebras:
            groups_to_install.append("cerebras")
        if args.ocr:
            groups_to_install.append("ocr")

    print()
    print("=" * 60)
    print("  DREX — Optional Dependency Installer")
    print("=" * 60)

    for group in groups_to_install:
        install_group(group)

    # Summary
    print()
    print("  {'─' * 40}")
    print(f"  Groups installed: {len(INSTALLED)}")
    print(f"  Groups failed:    {len(FAILED)}")
    print(f"  Groups skipped:   {len(SKIPPED)}")
    print()

    if FAILED:
        print("  ⚠  Some packages failed to install.")
        print("     Try installing manually with pip:")
        for group in FAILED:
            pkgs = " ".join(OPTIONAL_GROUPS[group]["pip_names"])
            print(f"       pip install {pkgs}")
        print()

    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()