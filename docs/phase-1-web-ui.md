# Phase 1: Web UI Scaffold + Media Management

## Overview

Build a functional Flask web application that runs alongside the main player to:

### Current implementation status (2026-07-04)
- Implemented a Flask dashboard at `/api/dashboard` with upload, catalog listing, and catalog deletion.
- Implemented media-file upload handling and catalog persistence through `/api/upload` and `/api/catalog`.
- Remaining polish: richer catalog editing and NFC-tag association management.
- Display the current media catalog
- Upload new audio/video/image files
- Edit catalog entries
- Delete media files
- Manage NFC tag associations

**Time Estimate**: 3-4 days
**Token Budget**: ~2-3k tokens per module

---

## Architecture

### Directory Structure

```
src/music_player/web/
├── __init__.py              (Flask app factory)
├── app.py                   (Main Flask config)
├── routes.py                (Blueprint endpoints)
├── models.py                (Pydantic schemas for validation)
├── utils.py                 (File handling, validation)
├── templates/
│   ├── base.html            (Base template with nav)
│   └── dashboard.html       (Main UI - upload, catalog list)
└── static/
    ├── css/
    │   └── dashboard.css
    └── js/
        └── dashboard.js     (Upload handling, AJAX)
```

### Startup Options

**Option A**: Integrated (recommended for Phase 1)
```python
# In player.py main()
from threading import Thread
from music_player.web.app import create_app

app = create_app()
web_thread = Thread(target=lambda: app.run(
    host='0.0.0.0', port=5000, debug=False
), daemon=True)
web_thread.start()

# Continue with normal player loop
main_player_loop()
```

**Option B**: Separate systemd service (for later)
```ini
# /etc/systemd/system/music-web.service
[Unit]
Description=Axehead FM Web Interface
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/music-player
ExecStart=/usr/bin/python3 -c "from music_player.web.app import create_app; create_app().run(host='0.0.0.0', port=5000)"
Restart=on-failure
StandardOutput=journal

[Install]
WantedBy=multi-user.target
```

---

## Implementation: Step by Step

### Step 1: Create Flask App Factory (`app.py`)

```python
# src/music_player/web/app.py

from flask import Flask
from pathlib import Path
import json

def create_app(config_path=None):
    """Flask application factory."""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='../static',
                static_url_path='/static')
    
    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
    app.config['UPLOAD_TEMP'] = Path('/tmp/music-upload')
    app.config['MEDIA_BASE'] = Path('/opt/music-player/media')
    app.config['CATALOG_PATH'] = Path('/opt/music-player/catalog.json')
    
    # Create required directories
    app.config['UPLOAD_TEMP'].mkdir(exist_ok=True)
    for subdir in ['audio', 'images', 'video', 'thumbnails']:
        (app.config['MEDIA_BASE'] / subdir).mkdir(parents=True, exist_ok=True)
    
    # Register blueprints
    from music_player.web.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': str(error.description)}, 400
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### Step 2: Define Data Models (`models.py`)

```python
# src/music_player/web/models.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum

class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    SLIDESHOW = "slideshow"
    RADIO = "radio"
    GAME = "game"

class CatalogEntry(BaseModel):
    """Schema for a catalog entry."""
    type: MediaType
    title: str
    audio: Optional[str] = None
    video: Optional[str] = None
    folder: Optional[str] = None
    stream_url: Optional[str] = None
    image: Optional[str] = None
    station_freq: Optional[str] = None
    interval: Optional[float] = 5.0
    
    class Config:
        use_enum_values = True

class MediaUpload(BaseModel):
    """Schema for file upload metadata."""
    type: str  # 'audio', 'video', 'image'
    title: Optional[str] = None
    
    @validator('type')
    def validate_type(cls, v):
        if v not in ['audio', 'video', 'image']:
            raise ValueError('Must be audio, video, or image')
        return v

class CatalogUpdate(BaseModel):
    """Schema for updating catalog entries."""
    title: Optional[str] = None
    image: Optional[str] = None
    audio: Optional[str] = None
    video: Optional[str] = None
```

### Step 3: Utility Functions (`utils.py`)

```python
# src/music_player/web/utils.py

from pathlib import Path
from werkzeug.utils import secure_filename
from PIL import Image
import mimetypes
from datetime import datetime
import uuid

ALLOWED_AUDIO = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}
ALLOWED_VIDEO = {'mp4', 'mkv', 'avi', 'bin'}  # bin for preprocessed videos
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

def get_file_extension(filename: str) -> str:
    """Get file extension (lowercase, no dot)."""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def is_valid_audio(filename: str, size: int) -> tuple[bool, str]:
    """Validate audio file."""
    ext = get_file_extension(filename)
    if ext not in ALLOWED_AUDIO:
        return False, f'Audio must be: {", ".join(ALLOWED_AUDIO)}'
    if size > MAX_FILE_SIZE:
        return False, f'File too large (max {MAX_FILE_SIZE/1024/1024:.0f}MB)'
    return True, ''

def is_valid_video(filename: str, size: int) -> tuple[bool, str]:
    """Validate video file."""
    ext = get_file_extension(filename)
    if ext not in ALLOWED_VIDEO:
        return False, f'Video must be: {", ".join(ALLOWED_VIDEO)}'
    if size > MAX_FILE_SIZE:
        return False, f'File too large (max {MAX_FILE_SIZE/1024/1024:.0f}MB)'
    return True, ''

def is_valid_image(filename: str, size: int) -> tuple[bool, str]:
    """Validate image file."""
    ext = get_file_extension(filename)
    if ext not in ALLOWED_IMAGE:
        return False, f'Image must be: {", ".join(ALLOWED_IMAGE)}'
    if size > 50 * 1024 * 1024:  # 50MB for images
        return False, 'Image too large (max 50MB)'
    return True, ''

def sanitize_filename(filename: str) -> str:
    """Sanitize filename while preserving extension."""
    secure = secure_filename(filename)
    if not secure:
        secure = f"file_{uuid.uuid4().hex[:8]}"
    return secure

def generate_thumbnail(image_path: Path, thumb_dir: Path) -> Path:
    """Generate 128x64 thumbnail for display."""
    try:
        img = Image.open(image_path)
        img.thumbnail((128, 64), Image.Resampling.LANCZOS)
        thumb_path = thumb_dir / f"{image_path.stem}_thumb.png"
        img.save(thumb_path)
        return thumb_path
    except Exception as e:
        print(f"Thumbnail generation failed: {e}")
        return None

def get_relative_path(full_path: Path, base: Path) -> str:
    """Convert full path to relative path for catalog."""
    try:
        return str(full_path.relative_to(base))
    except ValueError:
        return str(full_path)

def get_file_size_display(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"
```

### Step 4: API Routes (`routes.py`)

```python
# src/music_player/web/routes.py

from flask import Blueprint, request, jsonify, render_template, current_app
from pathlib import Path
import json
from datetime import datetime
from music_player.web.utils import (
    is_valid_audio, is_valid_video, is_valid_image,
    sanitize_filename, generate_thumbnail, get_file_size_display
)
from music_player.web.models import CatalogEntry, MediaUpload

api_bp = Blueprint('api', __name__)

def load_catalog() -> dict:
    """Load catalog from JSON."""
    path = current_app.config['CATALOG_PATH']
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def save_catalog(catalog: dict) -> bool:
    """Save catalog to JSON."""
    try:
        path = current_app.config['CATALOG_PATH']
        with open(path, 'w') as f:
            json.dump(catalog, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save catalog: {e}")
        return False

# ============ UI ROUTES ============

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Serve dashboard HTML."""
    return render_template('dashboard.html')

# ============ CATALOG ENDPOINTS ============

@api_bp.route('/catalog', methods=['GET'])
def get_catalog():
    """Get full catalog."""
    catalog = load_catalog()
    return jsonify(catalog)

@api_bp.route('/catalog/<entry_id>', methods=['GET'])
def get_catalog_entry(entry_id):
    """Get single catalog entry."""
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
    return jsonify({entry_id: catalog[entry_id]})

@api_bp.route('/catalog/<entry_id>', methods=['PUT'])
def update_catalog_entry(entry_id):
    """Update catalog entry."""
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
    
    data = request.json
    catalog[entry_id].update(data)
    
    if save_catalog(catalog):
        return jsonify({'status': 'updated', 'entry': catalog[entry_id]})
    return jsonify({'error': 'Failed to save'}), 500

@api_bp.route('/catalog/<entry_id>', methods=['DELETE'])
def delete_catalog_entry(entry_id):
    """Delete catalog entry."""
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
    
    # Delete associated files
    entry = catalog[entry_id]
    for key in ['audio', 'video', 'image']:
        if key in entry and entry[key]:
            try:
                Path(entry[key]).unlink()
            except Exception as e:
                print(f"Failed to delete {entry[key]}: {e}")
    
    del catalog[entry_id]
    if save_catalog(catalog):
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Failed to delete'}), 500

# ============ UPLOAD ENDPOINTS ============

@api_bp.route('/upload', methods=['POST'])
def upload_media():
    """Upload a media file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    media_type = request.form.get('type', '').lower()
    title = request.form.get('title', file.filename)
    
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400
    
    # Validate based on type
    file_size = len(file.read())
    file.seek(0)  # Reset for reading
    
    if media_type == 'audio':
        valid, msg = is_valid_audio(file.filename, file_size)
        subdir = 'audio'
    elif media_type == 'video':
        valid, msg = is_valid_video(file.filename, file_size)
        subdir = 'video'
    elif media_type == 'image':
        valid, msg = is_valid_image(file.filename, file_size)
        subdir = 'images'
    else:
        return jsonify({'error': 'Unknown media type'}), 400
    
    if not valid:
        return jsonify({'error': msg}), 400
    
    # Save file
    safe_name = sanitize_filename(file.filename)
    dest_dir = current_app.config['MEDIA_BASE'] / subdir
    dest_path = dest_dir / safe_name
    
    try:
        file.save(dest_path)
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    
    # Generate thumbnail for images
    thumb_url = None
    if media_type == 'image':
        thumb_dir = current_app.config['MEDIA_BASE'] / 'thumbnails'
        thumb_path = generate_thumbnail(dest_path, thumb_dir)
        if thumb_path:
            thumb_url = f'/opt/music-player/media/thumbnails/{thumb_path.name}'
    
    # Generate catalog entry ID
    timestamp = datetime.now().strftime('%s')
    entry_id = f"{media_type}_{timestamp}"
    
    # Add to catalog
    catalog = load_catalog()
    catalog[entry_id] = {
        'type': media_type,
        'title': title,
        media_type: str(dest_path)
    }
    if media_type == 'image' and thumb_url:
        catalog[entry_id]['image'] = str(dest_path)
    
    if save_catalog(catalog):
        return jsonify({
            'status': 'ok',
            'entry_id': entry_id,
            'path': str(dest_path),
            'size': get_file_size_display(file_size),
            'thumbnail': thumb_url
        }), 201
    
    return jsonify({'error': 'Failed to save catalog'}), 500

@api_bp.route('/media-list', methods=['GET'])
def list_media():
    """List all media files by type."""
    media_base = current_app.config['MEDIA_BASE']
    result = {
        'audio': [],
        'video': [],
        'images': []
    }
    
    for media_type in result.keys():
        subdir = 'images' if media_type == 'images' else media_type
        dir_path = media_base / subdir
        if dir_path.exists():
            for file in dir_path.glob('*'):
                if file.is_file():
                    result[media_type].append({
                        'name': file.name,
                        'path': str(file),
                        'size': get_file_size_display(file.stat().st_size),
                        'modified': datetime.fromtimestamp(
                            file.stat().st_mtime
                        ).isoformat()
                    })
    
    return jsonify(result)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'media_base': str(current_app.config['MEDIA_BASE'])
    })
```

### Step 5: HTML Templates

```html
<!-- src/music_player/web/templates/base.html -->

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Axehead FM{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: #1a1a1a; color: white; padding: 20px 0; margin-bottom: 30px; }
        header h1 { font-size: 24px; margin-bottom: 10px; }
        header .status { font-size: 12px; color: #aaa; }
        nav { margin-top: 15px; }
        nav a { color: white; margin-right: 20px; text-decoration: none; font-size: 14px; }
        nav a:hover { text-decoration: underline; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h2 { font-size: 20px; margin-bottom: 15px; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 500; }
        input[type="text"], input[type="file"], select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        button:hover { background: #0056b3; }
        button.danger { background: #dc3545; }
        button.danger:hover { background: #c82333; }
        .success { color: #28a745; padding: 10px; background: #d4edda; border-radius: 4px; margin-bottom: 15px; }
        .error { color: #dc3545; padding: 10px; background: #f8d7da; border-radius: 4px; margin-bottom: 15px; }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .media-item { background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; padding: 15px; }
        .media-item h4 { font-size: 14px; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .media-item p { font-size: 12px; color: #666; margin-bottom: 10px; }
        .media-item-actions { display: flex; gap: 5px; }
        .media-item-actions button { padding: 5px 10px; font-size: 12px; flex: 1; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f5f5f5; font-weight: 600; }
        tr:hover { background: #f9f9f9; }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>🎵 Axehead FM Control Panel</h1>
            <p class="status">Web Interface for Media Management</p>
            <nav>
                <a href="#upload">Upload</a>
                <a href="#catalog">Catalog</a>
                <a href="#media-list">Files</a>
            </nav>
        </div>
    </header>

    <main class="container">
        {% block content %}{% endblock %}
    </main>

    <script src="{{ url_for('static', filename='js/dashboard.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

```html
<!-- src/music_player/web/templates/dashboard.html -->

{% extends "base.html" %}

{% block content %}

<!-- Upload Section -->
<div class="card" id="upload">
    <h2>📤 Upload Media</h2>
    
    <div id="uploadMessage"></div>
    
    <form id="uploadForm">
        <div class="form-group">
            <label for="uploadType">Media Type:</label>
            <select id="uploadType" name="type" required>
                <option value="">-- Select Type --</option>
                <option value="audio">Audio (MP3, WAV, FLAC, M4A)</option>
                <option value="video">Video (MP4, MKV, AVI, BIN)</option>
                <option value="image">Image (PNG, JPG, GIF)</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="uploadFile">Choose File:</label>
            <input type="file" id="uploadFile" name="file" required>
            <small style="color: #666; margin-top: 5px; display: block;">Max 500MB</small>
        </div>
        
        <div class="form-group">
            <label for="uploadTitle">Title (optional):</label>
            <input type="text" id="uploadTitle" name="title" placeholder="e.g., My Awesome Song">
        </div>
        
        <button type="submit">Upload</button>
        <div id="uploadProgress" style="margin-top: 10px;"></div>
    </form>
</div>

<!-- Media List Section -->
<div class="card" id="media-list">
    <h2>📁 Media Files</h2>
    
    <div id="mediaListContent">
        <div class="loading"></div> Loading...
    </div>
</div>

<!-- Catalog Section -->
<div class="card" id="catalog">
    <h2>📑 Media Catalog</h2>
    
    <div id="catalogMessage"></div>
    <div id="catalogContent">
        <div class="loading"></div> Loading catalog...
    </div>
</div>

<script>
// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    loadCatalog();
    loadMediaList();
    setupUploadHandler();
});

function setupUploadHandler() {
    const form = document.getElementById('uploadForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('uploadFile');
        const typeSelect = document.getElementById('uploadType');
        const titleInput = document.getElementById('uploadTitle');
        const messageDiv = document.getElementById('uploadMessage');
        
        if (!fileInput.files.length) {
            showMessage(messageDiv, 'Please select a file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('type', typeSelect.value);
        if (titleInput.value) {
            formData.append('title', titleInput.value);
        }
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showMessage(messageDiv, `✅ Uploaded: ${data.entry_id}`, 'success');
                form.reset();
                loadCatalog();
                loadMediaList();
            } else {
                showMessage(messageDiv, `❌ ${data.error}`, 'error');
            }
        } catch (error) {
            showMessage(messageDiv, `Error: ${error.message}`, 'error');
        }
    });
}

async function loadCatalog() {
    try {
        const response = await fetch('/api/catalog');
        const catalog = await response.json();
        
        const content = document.getElementById('catalogContent');
        
        if (Object.keys(catalog).length === 0) {
            content.innerHTML = '<p style="color: #999;">No entries in catalog</p>';
            return;
        }
        
        let html = '<table><thead><tr><th>ID</th><th>Type</th><th>Title</th><th>Actions</th></tr></thead><tbody>';
        
        for (const [id, entry] of Object.entries(catalog)) {
            html += `
                <tr>
                    <td><code>${id}</code></td>
                    <td>${entry.type}</td>
                    <td>${entry.title || 'Untitled'}</td>
                    <td>
                        <button onclick="editEntry('${id}')" style="background: #17a2b8;">Edit</button>
                        <button onclick="deleteEntry('${id}')" class="danger" style="width: 70px;">Delete</button>
                    </td>
                </tr>
            `;
        }
        
        html += '</tbody></table>';
        content.innerHTML = html;
    } catch (error) {
        document.getElementById('catalogContent').innerHTML = `<p style="color: #dc3545;">Error loading catalog: ${error.message}</p>`;
    }
}

async function loadMediaList() {
    try {
        const response = await fetch('/api/media-list');
        const media = await response.json();
        
        const content = document.getElementById('mediaListContent');
        let html = '';
        
        for (const [type, files] of Object.entries(media)) {
            if (files.length === 0) continue;
            
            html += `<h3>${type.toUpperCase()} (${files.length})</h3><div class="grid">`;
            
            for (const file of files) {
                html += `
                    <div class="media-item">
                        <h4>${file.name}</h4>
                        <p>${file.size}</p>
                        <p style="font-size: 11px; color: #999;">${new Date(file.modified).toLocaleDateString()}</p>
                    </div>
                `;
            }
            
            html += '</div>';
        }
        
        if (!html) {
            html = '<p style="color: #999;">No files uploaded yet</p>';
        }
        
        content.innerHTML = html;
    } catch (error) {
        document.getElementById('mediaListContent').innerHTML = `<p style="color: #dc3545;">Error: ${error.message}</p>`;
    }
}

async function deleteEntry(entryId) {
    if (!confirm(`Delete "${entryId}" and associated files?`)) return;
    
    try {
        const response = await fetch(`/api/catalog/${entryId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage(document.getElementById('catalogMessage'), '✅ Deleted', 'success');
            loadCatalog();
            loadMediaList();
        } else {
            showMessage(document.getElementById('catalogMessage'), `❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showMessage(document.getElementById('catalogMessage'), `Error: ${error.message}`, 'error');
    }
}

function editEntry(entryId) {
    alert('Edit functionality coming in Phase 2');
}

function showMessage(element, text, type) {
    element.className = type;
    element.textContent = text;
    element.style.display = 'block';
    if (type === 'success') {
        setTimeout(() => { element.style.display = 'none'; }, 4000);
    }
}
</script>

{% endblock %}
```

### Step 6: Basic CSS

```css
/* src/music_player/static/css/dashboard.css */

/* Additional responsive styles */
@media (max-width: 768px) {
    .container { padding: 10px; }
    header h1 { font-size: 18px; }
    .card { padding: 15px; }
    h2 { font-size: 16px; }
    nav a { margin-right: 10px; font-size: 12px; }
    .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
    table { font-size: 12px; }
    th, td { padding: 8px; }
}

@media (max-width: 480px) {
    .grid { grid-template-columns: 1fr; }
    button { width: 100%; }
    .media-item-actions { flex-direction: column; }
}

/* Drag and drop styling (for future enhancement) */
.upload-area.drag-over {
    border: 2px dashed #007bff;
    background: #f0f7ff;
}
```

---

## Testing Checklist

### Local Development
- [ ] `pip install Flask werkzeug`
- [ ] Run `python src/music_player/web/app.py` on port 5000
- [ ] Navigate to `http://localhost:5000/api/dashboard`
- [ ] Upload test audio file (MP3)
- [ ] Verify file in `/opt/music-player/media/audio/`
- [ ] Verify catalog.json updated
- [ ] Delete entry and verify file deleted

### Error Cases
- [ ] Upload file > 500MB (should reject)
- [ ] Upload wrong file type (should reject)
- [ ] Empty filename (should handle gracefully)
- [ ] Catalog file missing (should create)

### Integration with Player
- [ ] Start main player
- [ ] Web server runs in background thread
- [ ] Player still responds to NFC tags
- [ ] Upload new audio via web
- [ ] Scan NFC tag for newly uploaded audio
- [ ] Audio plays correctly

---

## File Structure Summary

```
src/music_player/
├── web/
│   ├── __init__.py
│   ├── app.py                  (400 lines)
│   ├── routes.py               (350 lines)
│   ├── models.py               (50 lines)
│   ├── utils.py                (100 lines)
│   └── templates/
│       ├── base.html           (100 lines)
│       └── dashboard.html      (200 lines)
└── static/
    ├── css/
    │   └── dashboard.css       (50 lines)
    └── js/
        └── dashboard.js        (in dashboard.html)
```

---

## What's Next?

After Phase 1 is complete:
- **Phase 2**: Add WiFi NFC provisioning
- **Phase 3**: Add GitHub update functionality to web interface
- **Phase 4**: Add web terminal (optional)

Each phase integrates cleanly with Phase 1 without major refactoring.

---

## Quick Deploy to Raspberry Pi

```bash
# From development machine
scp -r src/music_player/web pi@raspberrypi:/opt/music-player/src/music_player/
scp -r src/music_player/static pi@raspberrypi:/opt/music-player/src/music_player/

# On Raspberry Pi
cd /opt/music-player
pip install Flask
python -m music_player.web.app &  # or integrate with player.py
```

Then access: `http://raspberrypi.local:5000/api/dashboard`
