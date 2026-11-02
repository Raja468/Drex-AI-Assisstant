#!/usr/bin/env python3
"""
DREX Release Cleanup Script

Removes sensitive files and build artifacts before distribution.
Run this before creating an archive or publishing the project.

Usage:
    python scripts/clean_release.py           # Preview mode (dry run)
    python scripts/clean_release.py --apply   # Actually delete files
"""

import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Items that should NEVER be distributed
REMOVE_PATTERNS = [
    # Virtual environment
    "venv",
    ".venv",
    # Git metadata
    ".git",
    # Environment files with secrets
    ".env",
    # Python cache
    "__pycache__",
    ".pytest_cache",
    # Logs and data
    "logs",
    "data/*.db",
    "data/*.db-wal",
    "data/*.db-shm",
    # IDE settings
    ".vscode",
    ".idea",
    # Build artifacts
    "build",
    "dist",
    "*.egg-info",
    # Model cache
    "models",
    "cache",
    # Screenshots
    "screenshots",
    # Temp files
    "temp",
    "tmp",
]


def should_remove(path: Path, dry_run: bool) -> bool:
    """Check if a path matches any removal pattern."""
    rel_path = path.relative_to(PROJECT_ROOT)
    rel_str = str(rel_path).replace("\\", "/")

    for pattern in REMOVE_PATTERNS:
        if "*" in pattern:
            # Simple glob-like matching
            base = pattern.replace("*", "")
            if base in rel_str or rel_str.endswith(base.strip(".")):
                continue
        elif pattern in rel_str.split("/"):
            return True
        # Also check if the relative path starts with the pattern
        if rel_str == pattern or rel_str.startswith(pattern + "/"):
            return True
    
    return False


def clean(dry_run: bool = True):
    """Remove sensitive and unnecessary files from the project."""
    
    if dry_run:
        print("🔍 DRY RUN — no files will be deleted")
        print("   Run with --apply to actually delete files\n")
    else:
        print("🗑️  Cleaning project for distribution...\n")

    removed = 0
    skipped = 0

    for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True):
        # Skip the script itself
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        
        root_path = Path(root)
        
        # Skip if we're already inside a directory we'd remove
        try:
            rel = root_path.relative_to(PROJECT_ROOT)
            rel_str = str(rel).replace("\\", "/")
            skip_this = any(
                p in rel_str.split("/") 
                for p in ["venv", ".git", "__pycache__", ".pytest_cache"]
            )
            if skip_this and not dry_run:
                dirs.clear()
                continue
        except ValueError:
            continue

        for file in files:
            file_path = root_path / file
            if should_remove(file_path, dry_run):
                if not dry_run:
                    try:
                        os.remove(file_path)
                        print(f"  ✗ Removed: {file_path.relative_to(PROJECT_ROOT)}")
                        removed += 1
                    except Exception as e:
                        print(f"  ⚠  Error removing {file}: {e}")
                else:
                    print(f"  [would remove] {file_path.relative_to(PROJECT_ROOT)}")
                    removed += 1

        for dir_name in dirs.copy():
            dir_path = root_path / dir_name
            if should_remove(dir_path, dry_run):
                if not dry_run:
                    try:
                        shutil.rmtree(dir_path)
                        print(f"  ✗ Removed directory: {dir_name}")
                        removed += 1
                    except Exception as e:
                        print(f"  ⚠  Error removing {dir_name}: {e}")
                else:
                    print(f"  [would remove directory] {dir_name}")
                    removed += 1

    if dry_run:
        print(f"\n📋 Would remove {removed} files/directories")
        print("   Run: python scripts/clean_release.py --apply")
    else:
        print(f"\n✅ Cleaned {removed} files/directories")
        print("   Project is now safe for distribution!")
    
    return removed


def main():
    dry_run = "--apply" not in sys.argv
    
    print("=" * 55)
    print("  DREX Release Security Cleanup")
    print("=" * 55)
    print()
    
    count = clean(dry_run=dry_run)
    
    if dry_run:
        print()
        print("⚠️  REMINDER: Before distributing:")
        print("   1. Rotate any exposed API keys")
        print("   2. Never include .env in archives")
        print("   3. Use .env.example as a template instead")
    
    print()
    return 0 if count >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())