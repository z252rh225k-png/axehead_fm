# Phase 3: GitHub OTA Updates

## Overview

Deploy new versions of Axehead FM directly from GitHub releases via web interface. Includes rollback capability, version history tracking, and automatic service restart.

### Current implementation status (2026-07-04)
- Added a configurable GitHub update path that accepts a repository URL and branch.
- Added ZIP-upload fallback support for manual package deployment.
- Remaining work: stronger rollback/history tracking and more explicit release validation.

**Time Estimate**: 2-3 days
**Dependencies**: Flask (Phase 1), GitHub CLI (optional), requests library
**Prerequisites**: Phase 1 complete, WiFi connectivity (Phase 2)

---

## Architecture

### Update Flow

```
┌─────────────────────────────────────────────┐
│  GitHub Release (axehead_fm-v1.2.3.zip)    │
│  Contains: src/, pyproject.toml, etc        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
          ┌────────────────────┐
          │  Web Interface     │
          │  POST /api/update  │
          └────────┬───────────┘
                   │
                   ▼
      ┌─────────────────────────────┐
      │ Download + Extract to /tmp  │
      └─────────┬───────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │ Backup current → app.backup │
      └─────────┬───────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │ Deploy → /opt/music-player  │
      │ pip install -e .            │
      └─────────┬───────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │ systemctl restart service   │
      │ Log version + status        │
      └─────────────────────────────┘
```

### Directory Structure

```
/opt/music-player/
├── app/                     (current running code)
│   ├── src/
│   ├── pyproject.toml
│   └── ...
├── app.backup/              (previous version - for rollback)
├── staging/                 (temp extraction area)
├── updates/
│   └── update_log.json      (version history)
└── releases.json            (cached GitHub release list)

src/music_player/web/
├── update_handler.py        (NEW)
│   ├── download_release()
│   ├── validate_package()
│   ├── apply_update()
│   └── rollback_update()
├── routes.py                (EXTEND with update endpoints)
└── templates/
    └── updates.html         (NEW - update UI)
```

---

## Implementation: Step by Step

### Step 1: Update Handler Module

```python
# src/music_player/web/update_handler.py

import zipfile
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
import requests

class UpdateManager:
    """Manage application updates from GitHub."""
    
    def __init__(self, app_dir: Path = None):
        self.app_dir = app_dir or Path('/opt/music-player/app')
        self.backup_dir = self.app_dir.parent / 'app.backup'
        self.staging_dir = self.app_dir.parent / 'staging'
        self.updates_dir = self.app_dir.parent / 'updates'
        self.log_file = self.updates_dir / 'update_log.json'
        
        # Create required directories
        self.staging_dir.mkdir(exist_ok=True)
        self.updates_dir.mkdir(exist_ok=True)
    
    def check_github_releases(self, owner: str, repo: str, 
                             current_version: str = None) -> dict:
        """Check for available releases on GitHub.
        
        Args:
            owner: GitHub username/org
            repo: Repository name
            current_version: Current version string (e.g., "v1.0.0")
        
        Returns:
            {'available': bool, 'latest': str, 'download_url': str, 'release': dict}
        """
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/releases"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            releases = response.json()
            if not releases:
                return {'available': False, 'message': 'No releases found'}
            
            latest = releases[0]  # GitHub returns newest first
            version = latest['tag_name']
            
            # Find .zip asset
            zip_asset = None
            for asset in latest.get('assets', []):
                if asset['name'].endswith('.zip'):
                    zip_asset = asset
                    break
            
            if not zip_asset:
                return {'available': False, 'message': 'No .zip asset found'}
            
            # Check if newer than current
            is_newer = current_version is None or version > current_version
            
            return {
                'available': is_newer,
                'latest_version': version,
                'download_url': zip_asset['browser_download_url'],
                'release': {
                    'version': version,
                    'body': latest.get('body', ''),
                    'date': latest.get('published_at'),
                    'size_mb': zip_asset['size'] / (1024 * 1024)
                }
            }
        
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def download_release(self, download_url: str) -> Tuple[bool, str]:
        """Download release zip to staging directory.
        
        Returns:
            (success, zip_path_or_error)
        """
        try:
            # Clean staging
            if self.staging_dir.exists():
                shutil.rmtree(self.staging_dir)
            self.staging_dir.mkdir()
            
            zip_path = self.staging_dir / 'release.zip'
            
            print(f"Downloading from: {download_url}")
            response = requests.get(download_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            with open(zip_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            pct = (downloaded / total_size) * 100
                            print(f"Download: {pct:.1f}%")
            
            return True, str(zip_path)
        
        except Exception as e:
            return False, f"Download failed: {str(e)}"
    
    def validate_package(self, zip_path: str) -> Tuple[bool, str]:
        """Validate that zip contains valid package.
        
        Checks for:
        - pyproject.toml
        - src/ directory with __init__.py
        - No path traversal attacks
        
        Returns:
            (is_valid, message)
        """
        try:
            zip_path = Path(zip_path)
            
            if not zip_path.exists():
                return False, "Zip file not found"
            
            if not zipfile.is_zipfile(zip_path):
                return False, "Not a valid zip file"
            
            with zipfile.ZipFile(zip_path) as zf:
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
                        return False, f"Invalid path in zip: {name}"
            
            return True, "Package valid"
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def apply_update(self, zip_path: str) -> Tuple[bool, str]:
        """Extract and apply update.
        
        Process:
        1. Backup current app
        2. Extract new version
        3. Install dependencies
        4. Restart service
        
        Returns:
            (success, message)
        """
        try:
            zip_path = Path(zip_path)
            
            # Validate before proceeding
            valid, msg = self.validate_package(str(zip_path))
            if not valid:
                return False, msg
            
            print("Creating backup...")
            # Backup current version
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            shutil.copytree(self.app_dir, self.backup_dir)
            
            print("Extracting new version...")
            # Extract to staging first
            extract_dir = self.staging_dir / 'extracted'
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
            
            # Find root directory (might be nested in zip)
            contents = list(extract_dir.iterdir())
            if len(contents) == 1 and contents[0].is_dir():
                root = contents[0]
            else:
                root = extract_dir
            
            print("Deploying new version...")
            # Remove old app and deploy new
            shutil.rmtree(self.app_dir)
            shutil.copytree(root, self.app_dir)
            
            print("Installing dependencies...")
            # Reinstall package
            result = subprocess.run([
                'pip', 'install', '-e', str(self.app_dir)
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                # Rollback on pip failure
                shutil.rmtree(self.app_dir)
                shutil.copytree(self.backup_dir, self.app_dir)
                return False, f"pip install failed: {result.stderr}"
            
            print("Restarting service...")
            # Restart service
            subprocess.run([
                'systemctl', 'restart', 'music-player'
            ], check=False, capture_output=True, timeout=15)
            
            # Log successful update
            self._log_update('success', zip_path.name)
            
            return True, "Update applied successfully"
        
        except subprocess.TimeoutExpired:
            return False, "Operation timeout"
        except Exception as e:
            # Attempt rollback on any error
            try:
                if self.backup_dir.exists():
                    shutil.rmtree(self.app_dir)
                    shutil.copytree(self.backup_dir, self.app_dir)
                    subprocess.run(['systemctl', 'restart', 'music-player'],
                                 check=False, capture_output=True)
            except:
                pass
            
            return False, f"Update failed: {str(e)}"
    
    def rollback_update(self) -> Tuple[bool, str]:
        """Rollback to previous version."""
        try:
            if not self.backup_dir.exists():
                return False, "No backup available"
            
            print("Rolling back...")
            shutil.rmtree(self.app_dir)
            shutil.copytree(self.backup_dir, self.app_dir)
            
            # Reinstall
            subprocess.run([
                'pip', 'install', '-e', str(self.app_dir)
            ], check=True, capture_output=True, timeout=120)
            
            # Restart service
            subprocess.run([
                'systemctl', 'restart', 'music-player'
            ], check=False, capture_output=True, timeout=15)
            
            self._log_update('rollback', 'manual')
            return True, "Rolled back successfully"
        
        except Exception as e:
            return False, f"Rollback failed: {str(e)}"
    
    def get_current_version(self) -> str:
        """Get currently running version."""
        try:
            import music_player
            if hasattr(music_player, '__version__'):
                return music_player.__version__
            return "unknown"
        except:
            return "unknown"
    
    def get_update_log(self) -> list:
        """Get update history."""
        try:
            if self.log_file.exists():
                with open(self.log_file) as f:
                    return json.load(f)
        except:
            pass
        return []
    
    def _log_update(self, status: str, release_name: str) -> None:
        """Log update event."""
        try:
            log = self.get_update_log()
            log.append({
                'timestamp': datetime.now().isoformat(),
                'status': status,
                'release': release_name,
                'version': self.get_current_version()
            })
            
            with open(self.log_file, 'w') as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            print(f"Failed to log update: {e}")


# Global instance
_update_manager = None

def get_update_manager(app_dir: Path = None) -> UpdateManager:
    """Singleton accessor."""
    global _update_manager
    if _update_manager is None:
        _update_manager = UpdateManager(app_dir)
    return _update_manager
```

### Step 2: Extend Routes with Update Endpoints

Add to `src/music_player/web/routes.py`:

```python
# Add to routes.py

from flask import render_template, send_file
from music_player.web.update_handler import get_update_manager

@api_bp.route('/updates/check', methods=['GET'])
def check_updates():
    """Check for available updates on GitHub."""
    manager = get_update_manager()
    
    # You should store these in config
    github_owner = 'robert'  # CHANGE ME
    github_repo = 'axehead_fm'  # CHANGE ME
    
    current_version = manager.get_current_version()
    result = manager.check_github_releases(github_owner, github_repo, current_version)
    
    return jsonify(result)

@api_bp.route('/updates/status', methods=['GET'])
def update_status():
    """Get update system status."""
    manager = get_update_manager()
    
    return jsonify({
        'current_version': manager.get_current_version(),
        'backup_available': manager.backup_dir.exists(),
        'update_log': manager.get_update_log()[-5:]  # Last 5 updates
    })

@api_bp.route('/updates/download', methods=['POST'])
def download_update():
    """Download release from GitHub URL."""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    manager = get_update_manager()
    success, result = manager.download_release(url)
    
    if success:
        return jsonify({
            'status': 'downloaded',
            'zip_path': result,
            'ready_to_install': True
        })
    else:
        return jsonify({'error': result}), 500

@api_bp.route('/updates/apply', methods=['POST'])
def apply_update():
    """Apply downloaded update."""
    data = request.json or {}
    zip_path = data.get('zip_path')
    
    if not zip_path:
        return jsonify({'error': 'No zip path provided'}), 400
    
    manager = get_update_manager()
    success, msg = manager.apply_update(zip_path)
    
    if success:
        return jsonify({
            'status': 'applied',
            'message': msg,
            'version': manager.get_current_version()
        })
    else:
        return jsonify({'error': msg}), 500

@api_bp.route('/updates/rollback', methods=['POST'])
def rollback_update():
    """Rollback to previous version."""
    manager = get_update_manager()
    success, msg = manager.rollback_update()
    
    if success:
        return jsonify({'status': 'rolled_back', 'message': msg})
    else:
        return jsonify({'error': msg}), 500
```

### Step 3: Update UI Template

```html
<!-- src/music_player/web/templates/updates.html -->

{% extends "base.html" %}

{% block content %}

<div class="card" id="updates">
    <h2>🔄 System Updates</h2>
    
    <div id="updateMessage"></div>
    
    <!-- Current Status -->
    <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
        <h3 style="margin-top: 0;">Current Version</h3>
        <p>
            <strong>Version:</strong> <span id="currentVersion">Loading...</span>
        </p>
        <p style="font-size: 12px; color: #666; margin-bottom: 0;">
            Last Updated: <span id="lastUpdate">Never</span>
        </p>
    </div>
    
    <!-- Check for Updates -->
    <div style="margin-bottom: 20px;">
        <button onclick="checkForUpdates()" style="width: 100%; padding: 12px;">
            🔍 Check for Updates
        </button>
        <div id="checkStatus" style="margin-top: 10px; font-size: 13px;"></div>
    </div>
    
    <!-- Available Update (shown if update exists) -->
    <div id="availableUpdate" style="display: none; background: #d4edda; padding: 15px; border-radius: 4px; margin-bottom: 20px; border: 1px solid #28a745;">
        <h3 style="margin-top: 0; color: #155724;">Update Available</h3>
        <p>
            <strong id="updateVersionName">v1.0.0</strong> 
            <span style="color: #666; font-size: 12px;">(≈<span id="updateSize">0</span>MB)</span>
        </p>
        <p id="updateNotes" style="font-size: 13px; color: #333; max-height: 100px; overflow-y: auto; margin-bottom: 10px;"></p>
        <button onclick="installUpdate()" style="width: 100%; padding: 10px; background: #28a745;">
            ⬇️ Download & Install
        </button>
        <div id="installProgress" style="margin-top: 10px; display: none;">
            <div style="background: white; padding: 10px; border-radius: 4px;">
                <div style="background: #e9e9e9; height: 20px; border-radius: 3px; overflow: hidden;">
                    <div id="progressBar" style="background: #28a745; height: 100%; width: 0%; transition: width 0.3s;"></div>
                </div>
                <p id="progressText" style="font-size: 12px; margin: 5px 0 0 0; color: #666;">Preparing...</p>
            </div>
        </div>
    </div>
    
    <!-- Rollback -->
    <div id="rollbackSection" style="display: none;">
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
        <h3>Troubleshooting</h3>
        <p style="color: #666; font-size: 13px;">If the latest version has issues, you can rollback to the previous version:</p>
        <button onclick="rollbackToPrevious()" class="danger" style="width: 100%; padding: 10px;">
            ⏮️ Rollback to Previous Version
        </button>
    </div>
    
    <!-- Update History -->
    <div style="margin-top: 20px;">
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
        <h3>Update History</h3>
        <div id="updateHistory" style="font-size: 12px;">
            <p style="color: #999;">Loading...</p>
        </div>
    </div>
</div>

<script>
let currentUpdateUrl = null;
let currentUpdatePath = null;

document.addEventListener('DOMContentLoaded', () => {
    loadUpdateStatus();
    loadUpdateHistory();
});

async function loadUpdateStatus() {
    try {
        const response = await fetch('/api/updates/status');
        const data = await response.json();
        
        document.getElementById('currentVersion').textContent = data.current_version;
        
        if (data.update_log.length > 0) {
            const last = data.update_log[data.update_log.length - 1];
            const date = new Date(last.timestamp);
            document.getElementById('lastUpdate').textContent = date.toLocaleDateString();
        }
        
        // Show rollback button if backup exists
        if (data.backup_available) {
            document.getElementById('rollbackSection').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading status:', error);
    }
}

async function loadUpdateHistory() {
    try {
        const response = await fetch('/api/updates/status');
        const data = await response.json();
        
        const history = data.update_log || [];
        if (history.length === 0) {
            document.getElementById('updateHistory').innerHTML = '<p style="color: #999;">No updates yet</p>';
            return;
        }
        
        let html = '<table style="width: 100%; font-size: 12px;"><tbody>';
        for (const entry of history.reverse()) {
            const date = new Date(entry.timestamp);
            html += `
                <tr>
                    <td>${date.toLocaleDateString()} ${date.toLocaleTimeString()}</td>
                    <td>${entry.status}</td>
                    <td>${entry.version}</td>
                </tr>
            `;
        }
        html += '</tbody></table>';
        document.getElementById('updateHistory').innerHTML = html;
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

async function checkForUpdates() {
    const checkDiv = document.getElementById('checkStatus');
    checkDiv.textContent = '⏳ Checking for updates...';
    
    try {
        const response = await fetch('/api/updates/check');
        const data = await response.json();
        
        if (data.available) {
            currentUpdateUrl = data.download_url;
            
            document.getElementById('updateVersionName').textContent = data.latest_version;
            document.getElementById('updateSize').textContent = Math.round(data.release.size_mb);
            document.getElementById('updateNotes').textContent = data.release.body || 'No release notes available';
            document.getElementById('availableUpdate').style.display = 'block';
            
            checkDiv.innerHTML = '✅ Update available: ' + data.latest_version;
        } else {
            checkDiv.innerHTML = '✅ You are running the latest version';
            document.getElementById('availableUpdate').style.display = 'none';
        }
    } catch (error) {
        checkDiv.innerHTML = '❌ Error checking for updates: ' + error.message;
    }
}

async function installUpdate() {
    if (!currentUpdateUrl) {
        alert('No update selected');
        return;
    }
    
    if (!confirm('Download and install update? The service will restart.')) {
        return;
    }
    
    const msgDiv = document.getElementById('updateMessage');
    const progressDiv = document.getElementById('installProgress');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    progressDiv.style.display = 'block';
    
    try {
        // Step 1: Download
        progressText.textContent = 'Downloading (0%)...';
        progressBar.style.width = '0%';
        
        const downloadResp = await fetch('/api/updates/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: currentUpdateUrl })
        });
        
        const downloadData = await downloadResp.json();
        if (!downloadResp.ok) {
            throw new Error(downloadData.error || 'Download failed');
        }
        
        currentUpdatePath = downloadData.zip_path;
        progressBar.style.width = '50%';
        progressText.textContent = 'Downloaded. Installing...';
        
        // Step 2: Apply
        const applyResp = await fetch('/api/updates/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ zip_path: currentUpdatePath })
        });
        
        const applyData = await applyResp.json();
        
        if (!applyResp.ok) {
            throw new Error(applyData.error || 'Installation failed');
        }
        
        progressBar.style.width = '100%';
        progressText.textContent = '✅ Update installed. Service restarting...';
        
        msgDiv.className = 'success';
        msgDiv.textContent = '✅ Update completed! Service is restarting.';
        
        // Reload after delay
        setTimeout(() => location.reload(), 5000);
    
    } catch (error) {
        progressDiv.style.display = 'none';
        msgDiv.className = 'error';
        msgDiv.textContent = '❌ Error: ' + error.message;
    }
}

async function rollbackToPrevious() {
    if (!confirm('Rollback to previous version? Service will restart.')) {
        return;
    }
    
    const msgDiv = document.getElementById('updateMessage');
    msgDiv.textContent = '⏳ Rolling back...';
    msgDiv.className = '';
    
    try {
        const response = await fetch('/api/updates/rollback', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            msgDiv.className = 'success';
            msgDiv.textContent = '✅ Rolled back successfully. Service restarting...';
            setTimeout(() => location.reload(), 3000);
        } else {
            msgDiv.className = 'error';
            msgDiv.textContent = '❌ Rollback failed: ' + data.error;
        }
    } catch (error) {
        msgDiv.className = 'error';
        msgDiv.textContent = '❌ Error: ' + error.message;
    }
}
</script>

{% endblock %}
```

### Step 4: Add pyproject.toml Version

In [pyproject.toml](../pyproject.toml), ensure version is set:

```toml
[project]
name = "music-player"
version = "1.0.0"  # <-- Increment this with each release
```

Then in your module:

```python
# src/music_player/__init__.py
__version__ = "1.0.0"
```

---

## GitHub Release Workflow

### Create Release Locally

```bash
# 1. Create release directory
mkdir axehead_fm-v1.0.0
cp -r src/ axehead_fm-v1.0.0/
cp pyproject.toml README.md LICENSE axehead_fm-v1.0.0/
cd axehead_fm-v1.0.0

# 2. Create zip
zip -r ../axehead_fm-v1.0.0.zip .

# 3. Create GitHub release
gh release create v1.0.0 ../axehead_fm-v1.0.0.zip \
    --title "Version 1.0.0" \
    --notes "Bug fixes and new features"
```

### Automated GitHub Actions (Optional)

Create `.github/workflows/release.yml`:

```yaml
name: Create Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Create ZIP
        run: |
          mkdir axehead_fm-${{ github.ref_name }}
          cp -r src pyproject.toml README.md LICENSE axehead_fm-${{ github.ref_name }}/
          zip -r axehead_fm-${{ github.ref_name }}.zip axehead_fm-${{ github.ref_name }}
      
      - name: Create Release
        uses: actions/create-release@v1
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref_name }}
          draft: false
          prerelease: false
          files: axehead_fm-${{ github.ref_name }}.zip
```

---

## Configuration (Add to config.py)

```python
# src/music_player/state/config.py

GITHUB_OWNER = 'your-github-username'
GITHUB_REPO = 'axehead_fm'
UPDATE_CHECK_INTERVAL = 86400  # 24 hours

# Optionally require admin PIN for updates
UPDATE_ADMIN_PIN = '1234'  # Change this!
```

---

## Testing Checklist

### Local Testing
- [ ] Create test zip with valid package structure
- [ ] Test validate_package() with invalid files
- [ ] Test download_release() with mock URL
- [ ] Test apply_update() with backup/restore
- [ ] Test rollback_update()

### Integration
- [ ] Access web interface at /api/updates/status
- [ ] Check for updates (mock GitHub)
- [ ] Download and install test release
- [ ] Verify service restarts
- [ ] Test rollback
- [ ] Check update log written

### Security
- [ ] Verify path traversal check in validation
- [ ] Ensure backup exists before overwriting
- [ ] Test with corrupted zip file
- [ ] Verify admin PIN check (if implemented)

---

## Troubleshooting

### Service Won't Restart
```bash
# Check service status
systemctl status music-player
journalctl -u music-player -n 50

# Manual restart
systemctl restart music-player
```

### Pip Install Fails
```bash
# Check pip output
pip install -e /opt/music-player/app

# Manually restore backup
cp -r /opt/music-player/app.backup /opt/music-player/app
```

### Update Stuck
```bash
# Kill hung process
pkill -f "music.player.web"

# Restore from backup
systemctl stop music-player
rm -rf /opt/music-player/app
cp -r /opt/music-player/app.backup /opt/music-player/app
systemctl start music-player
```

---

## What's Next

Phase 3 makes your player deployable via GitHub releases. Consider:
- Adding digital signatures for updates
- Automated testing before deploying
- Auto-update checks on boot
- Notifications when updates available
