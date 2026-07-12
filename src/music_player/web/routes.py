from flask import Blueprint, request, jsonify, render_template, current_app
from pathlib import Path
import json
import subprocess
from datetime import datetime
from music_player.web.update_handler import UpdateHandler
from music_player.web.system_handler import SystemHandler
from music_player.web.terminal_handler import TerminalSession
from music_player.hardware.network_manager import get_network_manager
from music_player.web.utils import (
    is_valid_audio, is_valid_video, is_valid_image,
    sanitize_filename, generate_thumbnail, get_file_size_display
)
from music_player.catalog.loader import (
    load_catalog, load_catalog_split, is_builtin_entry, is_user_entry
)

api_bp = Blueprint('api', __name__)


def get_update_handler() -> UpdateHandler:
    return UpdateHandler(current_app.config['UPDATE_ROOT'])

def get_system_handler() -> SystemHandler:
    return SystemHandler()

def get_user_catalog_path() -> Path:
    """Get the user catalog path from config or use default."""
    if 'USER_CATALOG_PATH' in current_app.config:
        return current_app.config['USER_CATALOG_PATH']
    return Path('/opt/music-player/user_catalog.json')

def save_user_catalog(catalog: dict) -> bool:
    """Save catalog to user catalog file only (not built-in)."""
    try:
        path = get_user_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(catalog, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save user catalog: {e}")
        return False

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    return render_template('dashboard.html')


@api_bp.route('/user', methods=['GET'])
def get_user_tool():
    """User-facing web interface for Axehead FM."""
    return render_template('user.html')


@api_bp.route('/terminal', methods=['GET'])
def get_terminal_page():
    return render_template('terminal.html')


@api_bp.route('/terminal/execute', methods=['POST'])
def execute_terminal_command():
    payload = request.get_json(silent=True) or {}
    command = (payload.get('command') or '').strip()
    if not command:
        return jsonify({'error': 'No command provided'}), 400

    session = TerminalSession(session_id='default')
    result = session.execute(command)
    if result.get('ok'):
        return jsonify(result)
    return jsonify(result), 400

@api_bp.route('/wifi/connections', methods=['GET'])
def get_wifi_connections():
    manager = get_network_manager()
    success, connections = manager.list_saved_connections()
    if success:
        return jsonify({'connections': connections})
    return jsonify({'error': 'Unable to read saved Wi-Fi connections'}), 500


@api_bp.route('/wifi/connections/<connection_name>/connect', methods=['POST'])
def connect_wifi_connection(connection_name):
    manager = get_network_manager()
    success, message = manager.connect_saved_connection(connection_name)
    if success:
        return jsonify({'status': 'ok', 'message': message})
    return jsonify({'error': message}), 500


@api_bp.route('/wifi/connections/<connection_name>', methods=['DELETE'])
def forget_wifi_connection(connection_name):
    manager = get_network_manager()
    success, message = manager.forget_connection(connection_name)
    if success:
        return jsonify({'status': 'ok', 'message': message})
    return jsonify({'error': message}), 500


# --- System Management Routes ---

@api_bp.route('/system/services', methods=['GET'])
def get_services_status():
    handler = get_system_handler()
    return jsonify(handler.get_all_statuses())


@api_bp.route('/system/info', methods=['GET'])
def get_system_info():
    handler = get_system_handler()
    return jsonify(handler.get_system_info())


@api_bp.route('/system/services/<service_name>/<action>', methods=['POST'])
def control_service(service_name, action):
    handler = get_system_handler()
    result = handler.control_service(service_name, action)
    if result.get('ok'):
        return jsonify(result)
    return jsonify(result), 400


@api_bp.route('/system/services/<service_name>/logs', methods=['GET'])
def get_service_logs(service_name):
    lines = request.args.get('lines', 50, type=int)
    handler = get_system_handler()
    
    # Check if a custom log file exists for this service
    log_file = None
    if service_name == "music-player":
        log_file = "/opt/music-player/logs/music-player.log"
    elif service_name == "music-web":
        log_file = "/opt/music-player/logs/web.log"
        
    return jsonify(handler.get_logs(service_name, lines, log_file))


@api_bp.route('/catalog', methods=['GET'])
def get_catalog():
    """Get merged catalog (built-in + user entries)."""
    catalog = load_catalog()
    return jsonify(catalog)

@api_bp.route('/catalog/metadata', methods=['GET'])
def get_catalog_metadata():
    """Get catalog with metadata showing source (built-in/user) and edit permissions."""
    catalogs = load_catalog_split()
    result = {}
    
    # Add built-in entries as read-only
    for entry_id, entry in catalogs['builtin'].items():
        result[entry_id] = {
            **entry,
            '_source': 'builtin',
            '_readonly': True
        }
    
    # Add user entries, potentially overriding built-in
    for entry_id, entry in catalogs['user'].items():
        result[entry_id] = {
            **entry,
            '_source': 'user',
            '_readonly': False
        }
    
    return jsonify(result)

@api_bp.route('/catalog/<entry_id>', methods=['GET'])
def get_catalog_entry(entry_id):
    """Get a single catalog entry with metadata."""
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
    
    source = 'user' if is_user_entry(entry_id) else 'builtin'
    entry_data = catalog[entry_id].copy()
    entry_data['_source'] = source
    entry_data['_readonly'] = source == 'builtin'
    
    return jsonify({entry_id: entry_data})

@api_bp.route('/catalog/<entry_id>', methods=['PUT'])
def update_catalog_entry(entry_id):
    """Update a catalog entry (only allowed for user entries)."""
    # Check if entry is built-in (read-only)
    if is_builtin_entry(entry_id):
        return jsonify({'error': 'Cannot modify built-in catalog entries. They are read-only.'}), 403
    
    # Get the user catalog
    catalogs = load_catalog_split()
    user_catalog = catalogs['user']
    
    # Entry might be from user catalog or doesn't exist yet (new user entry)
    if entry_id not in user_catalog and entry_id not in catalogs['builtin']:
        return jsonify({'error': 'Entry not found'}), 404
    
    # If it's from built-in, we already rejected it above
    # Otherwise update the user catalog
    data = request.json
    if entry_id not in user_catalog:
        # Creating a new user entry (or overriding a built-in one)
        user_catalog[entry_id] = {}
    
    user_catalog[entry_id].update(data)
    
    if save_user_catalog(user_catalog):
        # Return merged view
        merged = load_catalog()
        entry_data = merged[entry_id].copy()
        entry_data['_source'] = 'user'
        entry_data['_readonly'] = False
        return jsonify({'status': 'updated', 'entry': entry_data})
    return jsonify({'error': 'Failed to save'}), 500

@api_bp.route('/catalog/<entry_id>', methods=['DELETE'])
def delete_catalog_entry(entry_id):
    """Delete a catalog entry (only allowed for user entries)."""
    # Check if entry is built-in (cannot delete)
    if is_builtin_entry(entry_id):
        return jsonify({'error': 'Cannot delete built-in catalog entries. They are read-only.'}), 403
    
    # Get the catalog entries
    catalogs = load_catalog_split()
    user_catalog = catalogs['user']
    
    if entry_id not in user_catalog:
        return jsonify({'error': 'Entry not found in user catalog'}), 404
    
    entry = user_catalog[entry_id]
    
    # Clean up associated files
    for key in ['audio', 'video', 'image']:
        if key in entry and entry[key]:
            try:
                Path(entry[key]).unlink()
            except Exception as e:
                print(f"Failed to delete {entry[key]}: {e}")
    
    del user_catalog[entry_id]
    
    if save_user_catalog(user_catalog):
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Failed to delete'}), 500

@api_bp.route('/catalog/raw', methods=['PUT'])
def update_catalog_raw():
    """Replace entire user catalog with raw JSON. Built-in entries cannot be modified."""
    try:
        data = request.json
        if not isinstance(data, dict):
            return jsonify({'error': 'Catalog must be a JSON object'}), 400
        
        # Validate that each entry has required fields
        for entry_id, entry in data.items():
            if not isinstance(entry, dict):
                return jsonify({'error': f'Entry {entry_id} must be an object'}), 400
            if 'type' not in entry:
                return jsonify({'error': f'Entry {entry_id} missing required field: type'}), 400
            if 'title' not in entry:
                return jsonify({'error': f'Entry {entry_id} missing required field: title'}), 400
        
        if save_user_catalog(data):
            return jsonify({'status': 'updated', 'entries': len(data)})
        return jsonify({'error': 'Failed to save catalog'}), 500
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 400

# --- Audio Settings Routes ---

@api_bp.route('/audio/devices', methods=['GET'])
def get_audio_devices():
    """Get available audio devices and current device"""
    try:
        available_devices = []
        current_device = None
        
        # Query available sinks using pactl
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                timeout=3
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # pactl not available or timed out
            return jsonify({'devices': [], 'current': None})
        
        # Map device names to friendly names
        device_map = {
            'headphones': 'Headphones',
            'usb': 'USB Audio',
            'hdmi': 'HDMI',
            'analog': 'Analog',
            'speaker': 'Speakers'
        }
        
        seen_devices = set()
        for line in result.stdout.splitlines():
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    device_name = parts[1].lower()
                    
                    # Determine friendly name
                    friendly_name = 'Unknown'
                    for key, value in device_map.items():
                        if key in device_name:
                            friendly_name = value
                            break
                    else:
                        # Use the device name as-is if no match
                        friendly_name = parts[1] if len(parts) > 1 else f"Device {len(available_devices)}"
                    
                    # Avoid duplicates
                    if friendly_name not in seen_devices:
                        available_devices.append({
                            'name': friendly_name,
                            'id': parts[0]
                        })
                        seen_devices.add(friendly_name)
        
        # Get current default sink
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=3
            )
            current_sink = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            current_sink = None
        
        # Map current sink to friendly name
        if current_sink:
            for device in available_devices:
                if device['id'] == current_sink:
                    current_device = device['name']
                    break
        
        if not current_device and available_devices:
            current_device = available_devices[0]['name']
        
        return jsonify({
            'devices': available_devices,
            'current': current_device
        })
    except Exception as e:
        print(f"[!] Audio devices endpoint error: {e}")
        return jsonify({'error': f'Failed to query devices: {str(e)}', 'devices': [], 'current': None}), 500

@api_bp.route('/audio/device', methods=['PUT'])
def set_audio_device():
    """Set the current audio device"""
    try:
        data = request.json
        device_name = data.get('device')
        
        if not device_name:
            return jsonify({'error': 'Device name required'}), 400
        
        # Get available devices to find the sink ID
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                timeout=3
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return jsonify({'error': 'Audio system not available'}), 503
        
        target_sink = None
        device_name_lower = device_name.lower()
        
        for line in result.stdout.splitlines():
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    current_name = parts[1].lower()
                    # Match by device ID or by matching device name substring
                    if (parts[0] == device_name or 
                        device_name_lower in current_name or
                        current_name in device_name_lower):
                        target_sink = parts[0]
                        break
        
        if not target_sink:
            return jsonify({'error': f'Device not found: {device_name}'}), 404
        
        # Set as default sink
        try:
            subprocess.run(
                ["pactl", "set-default-sink", target_sink],
                capture_output=True,
                timeout=3,
                check=False
            )
        except FileNotFoundError:
            pass
        
        return jsonify({'status': 'ok', 'device': device_name})
    except Exception as e:
        print(f"[!] Set audio device endpoint error: {e}")
        return jsonify({'error': f'Failed to set device: {str(e)}'}), 500

@api_bp.route('/audio/volume', methods=['GET'])
def get_audio_volume():
    """Get current audio volume (0-100)"""
    try:
        # Get volume from default sink
        try:
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
                timeout=3
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # pactl not available
            return jsonify({'volume': 50})
        
        # Parse output like "Volume: front-left: 65535 / 100% / 0.00 dB"
        volume = 50
        for line in result.stdout.splitlines():
            if '%' in line:
                # Extract percentage
                import re
                match = re.search(r'(\d+)%', line)
                if match:
                    volume = int(match.group(1))
                    break
        
        return jsonify({'volume': volume})
    except Exception as e:
        print(f"[!] Audio volume get endpoint error: {e}")
        return jsonify({'volume': 50})

@api_bp.route('/audio/volume', methods=['PUT'])
def set_audio_volume():
    """Set audio volume (0-100)"""
    try:
        data = request.json
        volume = int(data.get('volume', 50))
        
        # Clamp to 0-150 (PipeWire allows going above 100%)
        volume = max(0, min(150, volume))
        
        # Set volume for all sinks
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
                capture_output=True,
                timeout=3,
                check=False
            )
        except FileNotFoundError:
            # pactl not available, but don't fail
            pass
        
        return jsonify({'status': 'ok', 'volume': volume})
    except ValueError:
        return jsonify({'error': 'Volume must be a number'}), 400
    except Exception as e:
        print(f"[!] Audio volume set endpoint error: {e}")
        return jsonify({'error': f'Failed to set volume: {str(e)}'}), 500

@api_bp.route('/upload', methods=['POST'])
def upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    media_type = request.form.get('type', '').lower()
    title = request.form.get('title', file.filename)
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400
    file_bytes = file.read()
    file_size = len(file_bytes)
    file.seek(0)
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
    safe_name = sanitize_filename(file.filename)
    dest_dir = current_app.config['USER_MEDIA_BASE'] / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    try:
        file.save(dest_path)
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    thumb_url = None
    if media_type == 'image':
        thumb_dir = current_app.config['USER_MEDIA_BASE'] / 'thumbnails'
        thumb_path = generate_thumbnail(dest_path, thumb_dir)
        if thumb_path:
            thumb_url = f'/opt/music-player/user_media/thumbnails/{thumb_path.name}'
    timestamp = datetime.now().strftime('%s')
    entry_id = f"{media_type}_{timestamp}"
    catalogs = load_catalog_split()
    user_catalog = catalogs['user']
    user_catalog[entry_id] = {
        'type': media_type,
        'title': title,
        media_type: str(dest_path)
    }
    if media_type == 'image' and thumb_url:
        user_catalog[entry_id]['image'] = str(dest_path)
    if save_user_catalog(user_catalog):
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
    """Simple health check endpoint. Returns 200 if service is running."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'music-player'
    })


@api_bp.route('/service/restart', methods=['POST'])
def restart_service_endpoint():
    """Trigger service restart (called after successful update deployment)."""
    try:
        # Call privileged restart helper
        result = subprocess.run(
            ['sudo', '/opt/music-player/scripts/music-player-restart.sh', 'restart'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({
                'error': f'Restart failed: {result.stderr}'
            }), 500
        
        return jsonify({
            'status': 'restart_issued',
            'output': result.stdout
        }), 202
    
    except FileNotFoundError:
        return jsonify({'error': 'Restart helper script not found'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Restart command timed out'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/service/health-check', methods=['GET'])
def service_health_check():
    """Check if service is healthy and responding."""
    try:
        # Call privileged health check helper
        result = subprocess.run(
            ['sudo', '/opt/music-player/scripts/music-player-restart.sh', 'check-health'],
            capture_output=True,
            text=True,
            timeout=40
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': 'healthy',
                'service': 'music-player',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'unhealthy',
                'error': result.stderr or 'Service not responding'
            }), 503
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@api_bp.route('/updates', methods=['GET'])
def get_updates():
    settings = get_update_handler().get_settings()
    return jsonify({
        'status': 'ready',
        'update_dir': str(current_app.config['UPDATE_DIR']),
        'repo': settings.get('repo', ''),
        'branch': settings.get('branch', 'main'),
    })


@api_bp.route('/update/version', methods=['GET'])
def get_version():
    """Get the currently installed version."""
    handler = get_update_handler()
    return jsonify({
        'version': handler.get_current_version()
    })


@api_bp.route('/update/start', methods=['POST'])
def start_update():
    """Enqueue an update job (GitHub or ZIP). Returns immediately with job_id."""
    payload = request.get_json(silent=True) or {}
    source = (payload.get('source') or '').strip()
    
    handler = get_update_handler()
    
    if source == 'github':
        repo_url = (payload.get('repo') or '').strip()
        branch = (payload.get('branch') or 'main').strip()
        
        if not repo_url:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        job_id = handler.enqueue_github_update(repo_url, branch)
        return jsonify({
            'status': 'enqueued',
            'job_id': job_id,
            'source': 'github',
            'repo': repo_url,
            'branch': branch
        }), 202
    
    elif source == 'zip':
        zip_path = (payload.get('zip_path') or '').strip()
        
        if not zip_path:
            return jsonify({'error': 'ZIP path is required'}), 400
        
        job_id = handler.enqueue_zip_update(zip_path)
        return jsonify({
            'status': 'enqueued',
            'job_id': job_id,
            'source': 'zip',
            'zip_path': zip_path
        }), 202
    
    else:
        return jsonify({'error': 'Invalid source. Use "github" or "zip"'}), 400


@api_bp.route('/update/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of an update job."""
    handler = get_update_handler()
    job = handler.get_job(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Convert job to dict, handling all fields
    job_dict = {
        'job_id': job.job_id,
        'status': job.status,
        'phase': job.phase,
        'progress_percent': job.progress_percent,
        'created_at': job.created_at,
        'updated_at': job.updated_at,
        'logs': job.logs,
        'source': job.source,
        'repo_url': job.repo_url,
        'branch': job.branch,
        'zip_path': job.zip_path,
        'installed_version': job.installed_version,
        'error_message': job.error_message
    }
    
    return jsonify(job_dict)


@api_bp.route('/update/history', methods=['GET'])
def get_update_history():
    """Get recent update jobs."""
    limit = request.args.get('limit', default=10, type=int)
    handler = get_update_handler()
    jobs = handler.get_jobs_history(limit=limit)
    
    return jsonify({
        'history': [
            {
                'job_id': j.job_id,
                'status': j.status,
                'phase': j.phase,
                'created_at': j.created_at,
                'source': j.source,
                'repo_url': j.repo_url,
                'branch': j.branch,
                'error_message': j.error_message
            }
            for j in jobs
        ]
    })


@api_bp.route('/update/backups', methods=['GET'])
def list_backups():
    """List available backup snapshots for rollback."""
    handler = get_update_handler()
    backups = []
    
    backup_dir = handler.backup_dir
    if backup_dir.exists():
        for backup in sorted(backup_dir.iterdir(), reverse=True):
            if backup.is_dir() and backup.name.startswith('backup_'):
                # Parse timestamp from backup name
                try:
                    timestamp_str = backup.name.replace('backup_', '')
                    backups.append({
                        'name': backup.name,
                        'timestamp': timestamp_str,
                        'size_bytes': sum(
                            f.stat().st_size for f in backup.rglob('*') if f.is_file()
                        )
                    })
                except Exception:
                    pass
    
    return jsonify({'backups': backups})


@api_bp.route('/update/rollback/<backup_name>', methods=['POST'])
def rollback_to_backup(backup_name):
    """Rollback to a specific backup snapshot."""
    handler = get_update_handler()
    
    try:
        handler._rollback_from_backup(backup_name)
        # Optionally restart services here in future milestone
        return jsonify({
            'status': 'rolled_back',
            'message': f'Rolled back to {backup_name}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/update/github', methods=['POST'])
def update_from_github():
    payload = request.get_json(silent=True) or {}
    repo_url = (payload.get('repo') or '').strip()
    branch = (payload.get('branch') or 'main').strip()
    if not repo_url:
        return jsonify({'error': 'Repository URL is required'}), 400

    handler = get_update_handler()
    success, message = handler.apply_update_from_github(repo_url, branch)
    if success:
        return jsonify({'status': 'ok', 'message': message, 'repo': repo_url, 'branch': branch})
    return jsonify({'error': message}), 500


@api_bp.route('/update/upload', methods=['POST'])
def upload_update():
    if 'file' not in request.files:
        return jsonify({'error': 'No update package provided'}), 400

    upload_file = request.files['file']
    if not upload_file.filename:
        return jsonify({'error': 'No filename'}), 400

    current_app.config['UPDATE_DIR'].mkdir(parents=True, exist_ok=True)
    dest_path = current_app.config['UPDATE_DIR'] / upload_file.filename
    upload_file.save(dest_path)

    handler = get_update_handler()
    success, message = handler.apply_update(dest_path)
    if success:
        return jsonify({'status': 'ok', 'message': message, 'package': str(dest_path)})
    return jsonify({'error': message}), 500
