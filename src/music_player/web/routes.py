from flask import Blueprint, request, jsonify, render_template, current_app
from pathlib import Path
import json
import subprocess
from datetime import datetime
from music_player.web.update_handler import UpdateHandler
from music_player.web.terminal_handler import TerminalSession
from music_player.hardware.network_manager import get_network_manager
from music_player.web.utils import (
    is_valid_audio, is_valid_video, is_valid_image,
    sanitize_filename, generate_thumbnail, get_file_size_display
)

api_bp = Blueprint('api', __name__)


def get_update_handler() -> UpdateHandler:
    return UpdateHandler(current_app.config['UPDATE_ROOT'])

def load_catalog() -> dict:
    path = current_app.config['CATALOG_PATH']
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def save_catalog(catalog: dict) -> bool:
    try:
        path = current_app.config['CATALOG_PATH']
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(catalog, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save catalog: {e}")
        return False

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    return render_template('dashboard.html')


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


@api_bp.route('/catalog', methods=['GET'])
def get_catalog():
    catalog = load_catalog()
    return jsonify(catalog)

@api_bp.route('/catalog/<entry_id>', methods=['GET'])
def get_catalog_entry(entry_id):
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
    return jsonify({entry_id: catalog[entry_id]})

@api_bp.route('/catalog/<entry_id>', methods=['PUT'])
def update_catalog_entry(entry_id):
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
    catalog = load_catalog()
    if entry_id not in catalog:
        return jsonify({'error': 'Entry not found'}), 404
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
    dest_dir = current_app.config['MEDIA_BASE'] / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    try:
        file.save(dest_path)
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    thumb_url = None
    if media_type == 'image':
        thumb_dir = current_app.config['MEDIA_BASE'] / 'thumbnails'
        thumb_path = generate_thumbnail(dest_path, thumb_dir)
        if thumb_path:
            thumb_url = f'/opt/music-player/media/thumbnails/{thumb_path.name}'
    timestamp = datetime.now().strftime('%s')
    entry_id = f"{media_type}_{timestamp}"
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
