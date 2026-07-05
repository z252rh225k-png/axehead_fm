import json
import shutil
import subprocess
import tempfile
import zipfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class UpdateJob:
    """Represents an update operation's state."""
    job_id: str
    status: str  # 'pending', 'running', 'completed', 'failed', 'rolled_back'
    phase: str  # 'download', 'validate', 'backup', 'deploy', 'install', 'restart', 'health_check', 'done'
    progress_percent: int  # 0-100
    created_at: str  # ISO format timestamp
    updated_at: str  # ISO format timestamp
    logs: List[str]  # Lines of execution log
    source: str  # 'github' or 'upload'
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    zip_path: Optional[str] = None
    installed_version: Optional[str] = None
    error_message: Optional[str] = None


class UpdateHandler:
    """Simple update application helper for uploads and GitHub pulls."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.base_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.base_dir / "update_settings.json"
        self.jobs_path = self.base_dir / "updates" / "jobs.json"
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        
        # Application deployment directory (where live code runs from)
        self.app_dir = self.base_dir / "app"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        
        # Staging directory for atomic updates
        self.staging_dir = self.base_dir / "staging"
        self.venv_dir = self.base_dir / "venv"
        
        self._job_lock = threading.Lock()
        self._job_queue: List[UpdateJob] = []
        self._current_job: Optional[UpdateJob] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_running = False

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

    # ===== Job Management Methods =====

    def _load_jobs(self) -> Dict[str, UpdateJob]:
        """Load all jobs from disk."""
        if self.jobs_path.exists():
            try:
                data = json.loads(self.jobs_path.read_text())
                return {
                    job_id: UpdateJob(**job_data)
                    for job_id, job_data in data.items()
                }
            except Exception:
                return {}
        return {}

    def _save_job(self, job: UpdateJob) -> None:
        """Persist a single job to disk."""
        try:
            jobs = self._load_jobs()
            jobs[job.job_id] = job
            self.jobs_path.write_text(json.dumps(
                {k: asdict(v) for k, v in jobs.items()},
                indent=2
            ))
        except Exception as e:
            print(f"Failed to save job: {e}")

    def start_worker(self) -> None:
        """Start the background job processor thread."""
        if self._worker_running:
            return
        
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop_worker(self) -> None:
        """Stop the background job processor thread."""
        self._worker_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

    def enqueue_github_update(self, repo_url: str, branch: str) -> str:
        """Enqueue a GitHub update job. Returns job_id."""
        job_id = str(uuid.uuid4())
        job = UpdateJob(
            job_id=job_id,
            status='pending',
            phase='download',
            progress_percent=0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            logs=[],
            source='github',
            repo_url=repo_url,
            branch=branch
        )
        
        with self._job_lock:
            self._job_queue.append(job)
            self._save_job(job)
        
        # Start worker only if not already running
        if not self._worker_running:
            self.start_worker()
        
        return job_id

    def enqueue_zip_update(self, zip_path: str) -> str:
        """Enqueue a ZIP update job. Returns job_id."""
        job_id = str(uuid.uuid4())
        job = UpdateJob(
            job_id=job_id,
            status='pending',
            phase='validate',
            progress_percent=0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            logs=[],
            source='upload',
            zip_path=zip_path
        )
        
        with self._job_lock:
            self._job_queue.append(job)
            self._save_job(job)
        
        if not self._worker_running:
            self.start_worker()
        
        return job_id

    def get_job(self, job_id: str) -> Optional[UpdateJob]:
        """Retrieve a job by ID."""
        with self._job_lock:
            if self._current_job and self._current_job.job_id == job_id:
                return self._current_job
            
            jobs = self._load_jobs()
            return jobs.get(job_id)

    def get_jobs_history(self, limit: int = 10) -> List[UpdateJob]:
        """Get recent completed/failed jobs."""
        with self._job_lock:
            jobs = self._load_jobs()
            completed = [
                j for j in jobs.values()
                if j.status in ('completed', 'failed', 'rolled_back')
            ]
            # Sort by created_at descending
            completed.sort(
                key=lambda j: j.created_at,
                reverse=True
            )
            return completed[:limit]

    def _update_job(self, job: UpdateJob) -> None:
        """Update job state in memory and persist."""
        job.updated_at = datetime.now().isoformat()
        with self._job_lock:
            self._current_job = job
            self._save_job(job)

    def _log_job(self, job: UpdateJob, message: str) -> None:
        """Add a log line to a job and persist."""
        job.logs.append(f"[{datetime.now().isoformat()}] {message}")
        self._update_job(job)

    def _worker_loop(self) -> None:
        """Background thread: process job queue one at a time."""
        while self._worker_running:
            job_to_process = None
            
            with self._job_lock:
                if self._job_queue:
                    job_to_process = self._job_queue.pop(0)
                    self._current_job = job_to_process
            
            if job_to_process:
                self._process_job(job_to_process)
                with self._job_lock:
                    self._current_job = None
            else:
                time.sleep(0.5)

    def _process_job(self, job: UpdateJob) -> None:
        """Execute an update job."""
        try:
            job.status = 'running'
            self._update_job(job)
            
            if job.source == 'github':
                self._process_github_job(job)
            elif job.source == 'upload':
                self._process_zip_job(job)
            else:
                raise ValueError(f"Unknown source: {job.source}")
            
            job.status = 'completed'
            job.phase = 'done'
            job.progress_percent = 100
            self._update_job(job)
            self._log_job(job, "Update completed successfully")
            
        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            self._log_job(job, f"ERROR: {str(e)}")
            self._update_job(job)

    def _process_github_job(self, job: UpdateJob) -> None:
        """Process a GitHub update job using staged deployment."""
        self._log_job(job, f"Starting GitHub update: {job.repo_url} ({job.branch})")
        
        job.phase = 'download'
        job.progress_percent = 10
        self._update_job(job)
        self._log_job(job, "Cloning from GitHub...")
        
        # Download to staging directory
        zip_path = self._download_github_to_staging(job.repo_url, job.branch)
        
        # Validate and proceed with staged deployment
        self._staged_deploy_flow(job, zip_path)

    def _process_zip_job(self, job: UpdateJob) -> None:
        """Process a ZIP upload job using staged deployment."""
        if not job.zip_path:
            raise ValueError("No zip path provided")
        
        self._log_job(job, f"Processing ZIP update: {job.zip_path}")
        
        # Proceed with staged deployment
        self._staged_deploy_flow(job, job.zip_path)

    def _staged_deploy_flow(self, job: UpdateJob, package_path: str) -> None:
        """Safe deployment flow: validate → backup → deploy → install → swap → restart → health-check."""
        package_path = Path(package_path)
        backup_snap = None
        
        try:
            # Phase 1: Validate
            job.phase = 'validate'
            job.progress_percent = 15
            self._update_job(job)
            self._log_job(job, "Validating package...")
            
            valid, msg = self._validate_package(str(package_path))
            if not valid:
                raise ValueError(f"Package validation failed: {msg}")
            self._log_job(job, "Package valid ✓")
            
            # Phase 2: Create backup of current live version
            job.phase = 'backup'
            job.progress_percent = 25
            self._update_job(job)
            self._log_job(job, "Creating version backup...")
            
            backup_snap = self._create_backup_snapshot()
            self._log_job(job, f"Backup created: {backup_snap}")
            
            # Phase 3: Prepare staging (extract, validate structure)
            job.phase = 'deploy'
            job.progress_percent = 35
            self._update_job(job)
            self._log_job(job, "Extracting to staging...")
            
            self._extract_to_staging(str(package_path))
            self._log_job(job, "Extraction complete ✓")
            
            # Phase 4: Install dependencies in staging
            job.phase = 'install'
            job.progress_percent = 60
            self._update_job(job)
            self._log_job(job, "Installing dependencies in staging...")
            
            self._install_dependencies_in_staging()
            self._log_job(job, "Dependencies installed ✓")
            
            # Phase 5: Atomic swap
            job.phase = 'swap'
            job.progress_percent = 75
            self._update_job(job)
            self._log_job(job, "Performing atomic swap...")
            
            self._atomic_swap()
            self._log_job(job, "Swap complete ✓ (live code updated)")
            
            # Phase 6: Restart service
            job.phase = 'restart'
            job.progress_percent = 85
            self._update_job(job)
            self._log_job(job, "Restarting music-player service...")
            
            try:
                self._restart_service()
                self._log_job(job, "Service restart triggered ✓")
            except Exception as e:
                self._log_job(job, f"Service restart failed: {e}, rolling back...")
                if backup_snap:
                    self._rollback_from_backup(backup_snap)
                raise Exception(f"Service restart failed: {str(e)}")
            
            # Phase 7: Health check
            job.phase = 'health_check'
            job.progress_percent = 95
            self._update_job(job)
            self._log_job(job, "Running health check...")
            
            try:
                healthy = self._run_health_check(timeout=30)
                if not healthy:
                    self._log_job(job, "Health check failed, rolling back...")
                    if backup_snap:
                        self._rollback_from_backup(backup_snap)
                        # Try to restart old version
                        try:
                            self._restart_service()
                        except Exception as restart_err:
                            self._log_job(job, f"WARNING: Could not restart rolled back version: {restart_err}")
                    raise Exception("Service health check failed")
                
                self._log_job(job, "Health check passed ✓")
            except Exception as e:
                if "health check" not in str(e).lower():
                    # Real error during health check call
                    self._log_job(job, f"Health check error: {e}")
                raise
            
            # Update job with version info
            job.installed_version = self.get_current_version()
            job.progress_percent = 100
            self._update_job(job)
            
        except Exception as e:
            # If we haven't already rolled back, do it now
            if backup_snap and job.phase not in ('done', 'rolled_back'):
                try:
                    self._log_job(job, f"Deployment failed at phase '{job.phase}', initiating rollback...")
                    self._rollback_from_backup(backup_snap)
                    self._log_job(job, "Rollback complete")
                    job.status = 'rolled_back'
                except Exception as rollback_err:
                    self._log_job(job, f"WARNING: Rollback failed: {rollback_err}")
            
            raise

    # ===== Staged Deployment Methods =====

    def _download_github_to_staging(self, repo_url: str, branch: str) -> str:
        """Clone GitHub repo to a temporary work directory and return its path."""
        try:
            # Keep the Git clone outside the deployment staging tree so later staging
            # cleanup does not delete the source directory we are about to validate.
            clone_root = self.base_dir / "staging_source"
            if clone_root.exists():
                shutil.rmtree(clone_root)
            clone_root.mkdir(parents=True, exist_ok=True)

            temp_clone = clone_root / "clone"
            
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(temp_clone)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"git clone failed: {result.stderr or result.stdout}")
            
            return str(temp_clone)
        except subprocess.TimeoutExpired:
            raise Exception("Clone timed out (>5 min)")
        except FileNotFoundError:
            raise Exception("git not installed on system")

    def _validate_package(self, zip_or_dir: str) -> Tuple[bool, str]:
        """Validate package has required structure (pyproject.toml, src/)."""
        path = Path(zip_or_dir)
        
        if zip_or_dir.endswith('.zip'):
            # Validate ZIP
            if not path.exists():
                return False, "ZIP file not found"
            if not zipfile.is_zipfile(str(path)):
                return False, "Not a valid ZIP file"
            
            try:
                with zipfile.ZipFile(str(path)) as zf:
                    files = zf.namelist()
                    
                    # Check for required files
                    has_pyproject = any(f.endswith('pyproject.toml') for f in files)
                    has_src = any('src/' in f for f in files)
                    
                    if not has_pyproject:
                        return False, "Missing pyproject.toml"
                    if not has_src:
                        return False, "Missing src/ directory"
                    
                    # Security: check for path traversal
                    for name in files:
                        if '..' in name or name.startswith('/'):
                            return False, f"Invalid path in ZIP: {name}"
                
                return True, "ZIP valid"
            except Exception as e:
                return False, f"ZIP validation error: {str(e)}"
        
        else:
            # Validate directory (git clone result)
            if not path.is_dir():
                return False, "Path is not a directory"
            
            pyproject = path / "pyproject.toml"
            src = path / "src"
            
            if not pyproject.exists():
                return False, "Missing pyproject.toml in cloned repo"
            if not src.is_dir():
                return False, "Missing src/ directory in cloned repo"
            
            return True, "Directory structure valid"

    def _create_backup_snapshot(self) -> str:
        """Create timestamped backup of current live app. Returns backup dir name."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        if self.app_dir.exists():
            shutil.copytree(self.app_dir, backup_path, dirs_exist_ok=True)
        else:
            # Create empty marker if no app yet
            backup_path.mkdir(parents=True, exist_ok=True)
        
        return backup_name

    def _extract_to_staging(self, zip_path: str) -> None:
        """Extract ZIP to staging, handling both nested and flat structures."""
        # Clean staging first
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        
        if zip_path.endswith('.zip'):
            # Extract ZIP
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(self.staging_dir)
            
            # Handle nested structure (e.g., folder-v1.0.0/src/)
            contents = list(self.staging_dir.iterdir())
            if len(contents) == 1 and contents[0].is_dir():
                # Move nested dir up to staging root
                nested = contents[0]
                temp_move = self.staging_dir / "__temp__"
                nested.rename(temp_move)
                
                # Copy contents to staging root
                for item in temp_move.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, self.staging_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, self.staging_dir / item.name)
                
                shutil.rmtree(temp_move)
        else:
            # Source is a directory (git clone)
            src = Path(zip_path)
            if not src.exists():
                raise Exception(f"Source directory not found: {zip_path}")

            if self.staging_dir.exists():
                for item in list(self.staging_dir.iterdir()):
                    if item.resolve() == src.resolve():
                        continue
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            else:
                self.staging_dir.mkdir(parents=True, exist_ok=True)

            for item in src.iterdir():
                if item.name.startswith('.'):
                    continue  # Skip .git, .gitignore, etc.
                
                if item.is_dir():
                    shutil.copytree(item, self.staging_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, self.staging_dir / item.name)

    def _install_dependencies_in_staging(self) -> None:
        """Run pip install -e . in staging directory."""
        staging_venv = self.staging_dir / "venv"
        staging_venv.mkdir(parents=True, exist_ok=True)
        
        # Create venv in staging if it doesn't exist
        result = subprocess.run(
            ["python3", "-m", "venv", str(staging_venv), "--system-site-packages"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise Exception(f"venv creation failed: {result.stderr}")
        
        # Run pip install -e . in staging
        pip_path = staging_venv / "bin" / "pip"
        result = subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(self.staging_dir)
        )
        
        if result.returncode != 0:
            raise Exception(f"pip upgrade failed: {result.stderr}")
        
        # Install package in development mode
        result = subprocess.run(
            [str(pip_path), "install", "-e", "."],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(self.staging_dir)
        )
        
        if result.returncode != 0:
            raise Exception(f"pip install -e . failed: {result.stderr}")

    def _atomic_swap(self) -> None:
        """Atomically swap staging to live (staging → app_dir)."""
        # This is as atomic as we can get with filesystem ops:
        # 1. Remove old app
        # 2. Rename staging to app
        
        if self.app_dir.exists():
            shutil.rmtree(self.app_dir)
        
        self.staging_dir.rename(self.app_dir)

    def _rollback_from_backup(self, backup_name: str) -> None:
        """Restore app from timestamped backup."""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            raise Exception(f"Backup {backup_name} not found")
        
        # Remove current app and restore from backup
        if self.app_dir.exists():
            shutil.rmtree(self.app_dir)
        
        shutil.copytree(backup_path, self.app_dir, dirs_exist_ok=True)

    def _restart_service(self) -> None:
        """Restart the music-player service via privileged helper."""
        try:
            result = subprocess.run(
                ['sudo', '/opt/music-player/scripts/music-player-restart.sh', 'restart'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                raise Exception(f"Restart failed: {result.stderr or result.stdout}")
        
        except FileNotFoundError:
            raise Exception("Restart helper script not found at /opt/music-player/scripts/music-player-restart.sh")
        except subprocess.TimeoutExpired:
            raise Exception("Service restart timed out (>15s)")
        except Exception as e:
            raise Exception(f"Service restart error: {str(e)}")

    def _run_health_check(self, timeout: int = 30) -> bool:
        """Run health check to verify service is responding. Returns True if healthy."""
        import requests
        
        try:
            health_url = "http://localhost:5000/api/health"
            response = requests.get(health_url, timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.RequestException:
            return False
        except Exception:
            return False

    def get_current_version(self) -> str:
        """Get currently installed version from pyproject.toml or metadata."""
        try:
            pyproject = self.base_dir / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                # Simple regex to extract version
                import re
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            
            # Fallback: try to import and check
            try:
                import music_player
                if hasattr(music_player, '__version__'):
                    return music_player.__version__
            except ImportError:
                pass
            
            return "unknown"
        except Exception:
            return "unknown"
