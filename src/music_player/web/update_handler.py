import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple


class UpdateHandler:
    """Simple update application helper for uploads and GitHub pulls."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.base_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.base_dir / "update_settings.json"

    def _load_settings(self) -> dict:
        if self.settings_path.exists():
            try:
                return json.loads(self.settings_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_settings(self, repo: str, branch: str) -> None:
        self.settings_path.write_text(json.dumps({"repo": repo, "branch": branch}, indent=2))

    def get_settings(self) -> dict:
        return self._load_settings()

    def apply_update(self, package_path: Path) -> Tuple[bool, str]:
        if not package_path.exists():
            return False, "Package file not found"
        if package_path.suffix.lower() != ".zip":
            return False, "Only .zip update packages are supported"

        backup_path = self.backup_dir / f"{package_path.stem}_backup"
        shutil.copytree(self.base_dir, backup_path, dirs_exist_ok=True)

        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                archive.extractall(self.base_dir)
            return True, f"Update applied from {package_path.name}"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Update failed: {exc}"

    def apply_update_from_github(self, repo_url: str, branch: str) -> Tuple[bool, str]:
        if not repo_url or not branch:
            return False, "Repository URL and branch are required"

        self._save_settings(repo_url, branch)

        backup_path = self.backup_dir / f"github_{branch.replace('/', '_')}_backup"
        shutil.copytree(self.base_dir, backup_path, dirs_exist_ok=True, ignore=self._ignore_patterns)

        temp_dir = Path(tempfile.mkdtemp(prefix="axehead-update-", dir=str(self.base_dir.parent)))
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(temp_dir / "source")],
                check=True,
                capture_output=True,
                text=True,
            )
            src_dir = temp_dir / "source"
            self._sync_repo_contents(src_dir, self.base_dir)
            return True, f"Updated from {repo_url} ({branch})"
        except FileNotFoundError:
            return False, "git is not installed on the Pi"
        except subprocess.CalledProcessError as exc:
            return False, f"GitHub pull failed: {exc.stderr or exc.stdout or str(exc)}"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Update failed: {exc}"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _ignore_patterns(directory: Path, contents: list[str]) -> list[str]:
        ignored = {".git", "venv", "media", "logs", "__pycache__", ".pytest_cache", ".DS_Store"}
        return [item for item in contents if item in ignored]

    @staticmethod
    def _sync_repo_contents(src_dir: Path, dst_dir: Path) -> None:
        for item in src_dir.iterdir():
            if item.name in {".git", "venv", "media", "logs", "__pycache__", ".pytest_cache", ".DS_Store"}:
                continue
            destination = dst_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
