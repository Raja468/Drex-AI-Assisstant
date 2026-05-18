# ============================================================
#  DREX - AI Desktop Assistant
#  automation/file_manager.py  —  File System Operations
#
#  WHAT IT DOES:
#  - Find files and folders on your PC
#  - Open files with their default application
#  - List directory contents
#  - Get file/folder information
# ============================================================

import os
import subprocess
from pathlib import Path
from typing import Optional
from utils.logger import logger


# Common places to search for files
SEARCH_ROOTS = [
    Path.home(),                          # C:\Users\YourName
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Music",
    Path.home() / "Pictures",
    Path.home() / "Videos",
]


class FileManager:
    """Handles file system operations for Drex."""

    def __init__(self):
        logger.info("✅ FileManager initialized")

    def find_file(
        self,
        filename: str,
        search_dir: Optional[str] = None,
        max_results: int = 5
    ) -> list[Path]:
        """
        Search for a file by name across common user directories.

        Args:
            filename:    Name or partial name to search for
            search_dir:  Specific directory to search (optional)
            max_results: Max number of results to return

        Returns:
            List of matching file paths
        """
        search_roots = [Path(search_dir)] if search_dir else SEARCH_ROOTS
        results = []
        filename_lower = filename.lower()

        for root in search_roots:
            if not root.exists():
                continue
            try:
                for path in root.rglob("*"):
                    if filename_lower in path.name.lower():
                        results.append(path)
                        if len(results) >= max_results:
                            return results
            except PermissionError:
                pass

        return results

    def open_file(self, file_path: str) -> tuple[bool, str]:
        """
        Open a file with its default Windows application.

        Args:
            file_path: Full path to the file

        Returns:
            (success, message)
        """
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        try:
            os.startfile(str(path))
            logger.info(f"📂 Opened file: {path}")
            return True, f"Opening {path.name}."
        except Exception as e:
            logger.error(f"Failed to open file '{file_path}': {e}")
            return False, f"Couldn't open {path.name}."

    def open_folder(self, folder_path: str) -> tuple[bool, str]:
        """Open a folder in Windows Explorer."""
        path = Path(folder_path)
        if not path.exists():
            return False, f"Folder not found: {folder_path}"

        try:
            subprocess.Popen(
                f'explorer "{path}"',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, f"Opening {path.name}."
        except Exception as e:
            return False, f"Couldn't open folder."

    def open_downloads(self) -> tuple[bool, str]:
        """Open the Downloads folder."""
        return self.open_folder(str(Path.home() / "Downloads"))

    def open_desktop(self) -> tuple[bool, str]:
        """Open the Desktop folder."""
        return self.open_folder(str(Path.home() / "Desktop"))

    def open_documents(self) -> tuple[bool, str]:
        """Open the Documents folder."""
        return self.open_folder(str(Path.home() / "Documents"))

    def list_directory(self, folder_path: str, max_items: int = 10) -> list[str]:
        """List files in a directory."""
        path = Path(folder_path)
        if not path.exists():
            return []
        try:
            items = list(path.iterdir())[:max_items]
            return [item.name for item in items]
        except Exception as e:
            logger.error(f"list_directory failed: {e}")
            return []

    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get information about a file."""
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            stat = path.stat()
            return {
                "name": path.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "extension": path.suffix,
                "parent": str(path.parent),
            }
        except Exception as e:
            logger.error(f"get_file_info failed: {e}")
            return None


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    fm = FileManager()
    print("Searching for 'readme' files...")
    results = fm.find_file("readme")
    for r in results:
        print(f"  Found: {r}")
