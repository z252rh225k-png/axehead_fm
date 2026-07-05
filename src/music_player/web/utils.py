from pathlib import Path
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

ALLOWED_AUDIO = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}
ALLOWED_VIDEO = {'mp4', 'mkv', 'avi', 'bin'}
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

def get_file_extension(filename: str) -> str:
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def is_valid_audio(filename: str, size: int) -> tuple:
    ext = get_file_extension(filename)
    if ext not in ALLOWED_AUDIO:
        return False, f'Audio must be: {", ".join(ALLOWED_AUDIO)}'
    if size > MAX_FILE_SIZE:
        return False, f'File too large (max {MAX_FILE_SIZE/1024/1024:.0f}MB)'
    return True, ''

def is_valid_video(filename: str, size: int) -> tuple:
    ext = get_file_extension(filename)
    if ext not in ALLOWED_VIDEO:
        return False, f'Video must be: {", ".join(ALLOWED_VIDEO)}'
    if size > MAX_FILE_SIZE:
        return False, f'File too large (max {MAX_FILE_SIZE/1024/1024:.0f}MB)'
    return True, ''

def is_valid_image(filename: str, size: int) -> tuple:
    ext = get_file_extension(filename)
    if ext not in ALLOWED_IMAGE:
        return False, f'Image must be: {", ".join(ALLOWED_IMAGE)}'
    if size > 50 * 1024 * 1024:
        return False, 'Image too large (max 50MB)'
    return True, ''

def sanitize_filename(filename: str) -> str:
    secure = secure_filename(filename)
    if not secure:
        secure = f"file_{uuid.uuid4().hex[:8]}"
    return secure

def generate_thumbnail(image_path: Path, thumb_dir: Path) -> Path:
    try:
        img = Image.open(image_path)
        img.thumbnail((128, 64), Image.Resampling.LANCZOS)
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"{image_path.stem}_thumb.png"
        img.save(thumb_path)
        return thumb_path
    except Exception as e:
        print(f"Thumbnail generation failed: {e}")
        return None

def get_relative_path(full_path: Path, base: Path) -> str:
    try:
        return str(full_path.relative_to(base))
    except ValueError:
        return str(full_path)

def get_file_size_display(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"
