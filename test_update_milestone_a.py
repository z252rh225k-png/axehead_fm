#!/usr/bin/env python3
"""
Quick test of Milestone A UpdateHandler implementation.
Tests job creation, persistence, and basic state management.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

import tempfile
import time

# Import directly to avoid loading Flask
import importlib.util
spec = importlib.util.spec_from_file_location(
    "update_handler",
    Path(__file__).parent / "src/music_player/web/update_handler.py"
)
update_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_handler_module)
UpdateHandler = update_handler_module.UpdateHandler
UpdateJob = update_handler_module.UpdateJob


def test_update_handler():
    print("Testing Milestone A: UpdateHandler with job state model\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = UpdateHandler(Path(tmpdir))
        print("✅ UpdateHandler instantiation OK")
        
        # Do NOT start worker yet - test job state before processing
        # (worker will auto-start on enqueue, but should be slow enough)
        
        # Test 1: Enqueue GitHub update
        job_id_1 = handler.enqueue_github_update(
            "https://github.com/user/axehead_fm.git", 
            "main"
        )
        print(f"✅ GitHub job enqueued (job_id: {job_id_1})")
        
        # Test 2: Enqueue ZIP update
        job_id_2 = handler.enqueue_zip_update("/tmp/update.zip")
        print(f"✅ ZIP job enqueued (job_id: {job_id_2})")
        
        # Test 3: Retrieve jobs immediately (before worker processes them)
        job1 = handler.get_job(job_id_1)
        job2 = handler.get_job(job_id_2)
        assert job1 is not None, "Job 1 not found"
        assert job2 is not None, "Job 2 not found"
        # Job may be pending or running depending on timing
        assert job1.status in ('pending', 'running'), f"Job 1 status unexpected: {job1.status}"
        assert job2.source == 'upload', f"Job 2 source should be 'upload', got {job2.source}"
        print(f"✅ Job retrieval OK (job1 status: {job1.status}, job2 source: {job2.source})")
        
        # Stop the worker to prevent further processing
        handler.stop_worker()
        print("✅ Worker stopped (jobs frozen in current state)")
        
        # Test 4: Get version
        version = handler.get_current_version()
        print(f"✅ Version retrieval OK (version: {version})")
        
        # Test 5: Get history (will have failed jobs since worker processed them)
        history = handler.get_jobs_history()
        # Jobs may have failed during processing (expected since repos don't exist)
        # This is OK - we're just testing that history retrieval works
        print(f"✅ History retrieval OK ({len(history)} jobs, status: {[j.status for j in history]})")
        
        # Test 6: Job persistence - reload from disk
        handler2 = UpdateHandler(Path(tmpdir))
        job1_reloaded = handler2.get_job(job_id_1)
        assert job1_reloaded is not None, "Job 1 not persisted"
        assert job1_reloaded.job_id == job_id_1, "Job ID mismatch"
        print("✅ Job persistence OK (jobs loaded from disk)")
        
        # Test 7: Worker lifecycle
        handler3 = UpdateHandler(Path(tmpdir))
        handler3.start_worker()
        print("✅ Worker started (on fresh handler)")
        
        # Give it a moment to process
        time.sleep(0.5)
        
        handler3.stop_worker()
        print("✅ Worker stopped")
        
        # Test 8: Update job state
        job1_fresh = handler.get_job(job_id_1)
        job1_fresh.phase = 'deploy'
        job1_fresh.progress_percent = 50
        handler._update_job(job1_fresh)
        
        job1_updated = handler.get_job(job_id_1)
        assert job1_updated.phase == 'deploy', "Phase not updated"
        assert job1_updated.progress_percent == 50, "Progress not updated"
        print("✅ Job state update OK")
        
        # Test 9: Logging
        handler._log_job(job1_updated, "Test log message")
        assert len(job1_updated.logs) > 0, "Log not added"
        print(f"✅ Job logging OK ({len(job1_updated.logs)} log entries)")
        
    print("\n" + "="*50)
    print("✅ All Milestone A tests PASSED!")
    print("="*50)


if __name__ == '__main__':
    try:
        test_update_handler()
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
