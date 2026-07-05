#!/usr/bin/env python3
"""
Milestone B Tests: Staged Deployment Engine with Atomic Swap and Rollback
Tests safe deployment flow: validate → backup → extract → install → swap → rollback
"""
import sys
from pathlib import Path
import tempfile
import shutil
import json
import zipfile
import importlib.util

# Import directly to avoid Flask dependency
spec = importlib.util.spec_from_file_location(
    "update_handler",
    Path(__file__).parent / "src/music_player/web/update_handler.py"
)
update_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_handler_module)
UpdateHandler = update_handler_module.UpdateHandler
UpdateJob = update_handler_module.UpdateJob


def create_test_zip(zip_path: Path, with_src=True) -> None:
    """Create a minimal test ZIP package."""
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('pyproject.toml', '[tool.poetry]\nname = "test-app"\nversion = "1.0.0"\n')
        if with_src:
            zf.writestr('src/__init__.py', '# Test module\n')
            zf.writestr('src/test.py', 'print("hello")\n')


def create_live_app(app_dir: Path) -> None:
    """Create a mock live app directory."""
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / 'pyproject.toml').write_text('[tool.poetry]\nname = "live-app"\nversion = "0.1.0"\n')
    (app_dir / 'src').mkdir(exist_ok=True)
    (app_dir / 'src' / '__init__.py').write_text('# Live version\n')


def test_milestone_b():
    print("Testing Milestone B: Staged Deployment Engine\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        handler = UpdateHandler(base_dir)
        
        print("=" * 60)
        print("TEST 1: Package Validation")
        print("=" * 60)
        
        # Test 1a: Valid ZIP
        valid_zip = base_dir / "valid.zip"
        create_test_zip(valid_zip, with_src=True)
        
        valid, msg = handler._validate_package(str(valid_zip))
        assert valid, f"Valid ZIP should pass: {msg}"
        print("✅ Valid ZIP accepted")
        
        # Test 1b: Invalid ZIP (missing pyproject.toml)
        invalid_zip = base_dir / "invalid.zip"
        with zipfile.ZipFile(invalid_zip, 'w') as zf:
            zf.writestr('src/__init__.py', '')
        
        valid, msg = handler._validate_package(str(invalid_zip))
        assert not valid, "ZIP without pyproject.toml should fail"
        assert "pyproject.toml" in msg
        print("✅ Invalid ZIP (missing pyproject.toml) rejected")
        
        # Test 1c: Directory validation
        test_dir = base_dir / "test_repo"
        test_dir.mkdir()
        (test_dir / 'pyproject.toml').write_text('[tool]\n')
        (test_dir / 'src').mkdir()
        
        valid, msg = handler._validate_package(str(test_dir))
        assert valid, f"Valid directory should pass: {msg}"
        print("✅ Valid directory structure accepted")
        
        print("\n" + "=" * 60)
        print("TEST 2: Backup Snapshot Creation")
        print("=" * 60)
        
        # Create a mock live app
        create_live_app(handler.app_dir)
        assert handler.app_dir.exists(), "App dir should exist"
        
        backup_name = handler._create_backup_snapshot()
        assert backup_name.startswith('backup_'), f"Backup name format wrong: {backup_name}"
        
        backup_path = handler.backup_dir / backup_name
        assert backup_path.exists(), "Backup dir should be created"
        assert (backup_path / 'pyproject.toml').exists(), "Backup should contain pyproject.toml"
        
        print(f"✅ Backup created: {backup_name}")
        print(f"   Location: {backup_path}")
        
        print("\n" + "=" * 60)
        print("TEST 3: Extract to Staging")
        print("=" * 60)
        
        # Extract valid ZIP to staging
        handler._extract_to_staging(str(valid_zip))
        
        assert handler.staging_dir.exists(), "Staging dir should exist"
        assert (handler.staging_dir / 'pyproject.toml').exists(), "Staging should have pyproject.toml"
        assert (handler.staging_dir / 'src' / '__init__.py').exists(), "Staging should have src"
        
        print("✅ ZIP extracted to staging successfully")
        print(f"   Contents: {list(handler.staging_dir.iterdir())}")
        
        print("\n" + "=" * 60)
        print("TEST 4: Atomic Swap")
        print("=" * 60)
        
        # Record original app state
        original_version = (handler.app_dir / 'pyproject.toml').read_text()
        print(f"   Original app version line 2: {original_version.splitlines()[1]}")
        
        # Perform atomic swap
        handler._atomic_swap()
        
        assert handler.staging_dir.exists() == False, "Staging should be removed after swap"
        assert (handler.app_dir / 'pyproject.toml').exists(), "App should have new pyproject.toml"
        
        new_version = (handler.app_dir / 'pyproject.toml').read_text()
        assert 'test-app' in new_version, "App should now have new version"
        
        print("✅ Atomic swap successful")
        print(f"   New app version line 1: {new_version.splitlines()[0]}")
        print(f"   Staging directory removed: {not handler.staging_dir.exists()}")
        
        print("\n" + "=" * 60)
        print("TEST 5: Rollback from Backup")
        print("=" * 60)
        
        # Verify rollback works
        handler._rollback_from_backup(backup_name)
        
        assert (handler.app_dir / 'pyproject.toml').exists(), "App should exist after rollback"
        
        rolled_back = (handler.app_dir / 'pyproject.toml').read_text()
        assert 'live-app' in rolled_back, "App should be restored to original version"
        
        print("✅ Rollback successful")
        print(f"   Restored app version: {rolled_back.splitlines()[1]}")
        
        print("\n" + "=" * 60)
        print("TEST 6: Job Flow Integration")
        print("=" * 60)
        
        # Create a fresh handler for clean slate
        handler2 = UpdateHandler(base_dir / "test2")
        create_live_app(handler2.app_dir)
        
        # Create a ZIP package
        test_zip = base_dir / "deploy.zip"
        create_test_zip(test_zip, with_src=True)
        
        # Enqueue job
        job_id = handler2.enqueue_zip_update(str(test_zip))
        print(f"✅ Job enqueued: {job_id}")
        
        # Stop worker to prevent auto-processing
        handler2.stop_worker()
        time.sleep(0.5)
        
        # Get job state
        job = handler2.get_job(job_id)
        assert job is not None, "Job should be retrievable"
        assert job.source == 'upload', f"Job source should be 'upload', got {job.source}"
        
        print(f"✅ Job tracked: status={job.status}, phase={job.phase}")
        
        print("\n" + "=" * 60)
        print("✅ ALL MILESTONE B TESTS PASSED!")
        print("=" * 60)
        print("\nCapabilities verified:")
        print("  • Package validation (ZIP + directory)")
        print("  • Versioned backup snapshots")
        print("  • Safe extraction to staging")
        print("  • Atomic swap operation")
        print("  • Rollback to any backup")
        print("  • Job tracking through deployment flow")


if __name__ == '__main__':
    import time
    try:
        test_milestone_b()
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
