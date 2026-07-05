import subprocess
import tempfile
from pathlib import Path
import importlib.util


spec = importlib.util.spec_from_file_location(
    "update_handler",
    Path(__file__).resolve().parents[1] / "src/music_player/web/update_handler.py",
)
update_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_handler_module)
UpdateHandler = update_handler_module.UpdateHandler


def test_github_clone_source_is_preserved_during_staging_extract():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        handler = UpdateHandler(base_dir)

        repo_dir = base_dir / "source_repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
        (repo_dir / "pyproject.toml").write_text("[project]\nname='demo'\nversion='1.0.0'\n")
        (repo_dir / "src").mkdir(exist_ok=True)
        (repo_dir / "src" / "__init__.py").write_text("")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, check=True, capture_output=True, text=True)

        clone_path = handler._download_github_to_staging(str(repo_dir), "main")
        assert Path(clone_path).exists(), "Clone directory should exist after download"

        handler._extract_to_staging(clone_path)

        assert (handler.staging_dir / "pyproject.toml").exists(), "pyproject.toml should be staged"
        assert (handler.staging_dir / "src" / "__init__.py").exists(), "src/__init__.py should be staged"


if __name__ == "__main__":
    test_github_clone_source_is_preserved_during_staging_extract()
