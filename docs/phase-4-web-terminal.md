# Phase 4: Web Terminal Access (Nice to Have)

## Overview

Access Linux shell via web browser for debugging and administration. Includes basic security (authentication, command blacklist, rate limiting).

### Current implementation status (2026-07-04)
- Added a basic browser terminal page at `/api/terminal` with a command execution endpoint.
- Implemented a simple command blacklist and rate-limiting guard for safe local admin use.
- Remaining work: stronger authentication, richer terminal features, and true PTY/WebSocket support.

**⚠️ Security Warning**: This feature allows arbitrary command execution. Use only on trusted networks. Requires strong authentication.

**Time Estimate**: 2-3 days
**Dependencies**: Flask (Phase 1), xterm.js, pyxterm or similar
**Prerequisites**: Phase 1 complete

---

## Architecture

### Web Terminal Flow

```
Browser
  ↓
xterm.js (WebSocket)
  ↓
Flask WebSocket Handler
  ↓
PTY (Pseudo-Terminal)
  ↓
Bash Shell Process
```

### Directory Structure

```
src/music_player/web/
├── terminal_handler.py    (NEW)
│   ├── TerminalSession
│   ├── CommandValidator
│   └── TerminalManager
├── routes.py              (EXTEND with WebSocket)
└── templates/
    └── terminal.html      (NEW)

src/music_player/static/js/
├── xterm.min.js           (downloaded library)
├── xterm-addon-fit.min.js
└── terminal.js            (NEW - handler)
```

---

## Implementation: Step by Step

### Step 1: Terminal Handler Module

```python
# src/music_player/web/terminal_handler.py

import os
import subprocess
import pty
import select
import fcntl
import struct
import signal
import time
from threading import Thread
from typing import Optional, Callable, Set
from pathlib import Path
import json

class CommandValidator:
    """Validate and sanitize terminal commands."""
    
    # Commands that pose security risk
    BLACKLIST = {
        'rm -rf',
        'dd ',
        'mkfs',
        'shutdown',
        'reboot',
        'halt',
        ':(){:|:&};:',  # Fork bomb
        'curl | bash',
        'wget | bash',
    }
    
    # Commands allowed without restriction
    WHITELIST = {
        'ls', 'cat', 'echo', 'pwd', 'cd', 'ps', 'top',
        'df', 'du', 'free', 'date', 'time', 'whoami',
        'find', 'grep', 'tail', 'head', 'wc', 'sort',
        'mkdir', 'touch', 'cp', 'mv', 'chmod',
        'systemctl status', 'journalctl', 'ps aux',
    }
    
    def __init__(self, allow_dangerous: bool = False):
        self.allow_dangerous = allow_dangerous
        self.commands_executed = 0
        self.last_command_time = 0
    
    def is_allowed(self, command: str) -> tuple[bool, str]:
        """Check if command is allowed.
        
        Args:
            command: Full command string
        
        Returns:
            (is_allowed, reason_if_denied)
        """
        cmd = command.strip().lower()
        
        if not cmd:
            return True, ""
        
        # Check blacklist
        for blocked in self.BLACKLIST:
            if blocked in cmd:
                return False, f"Command contains blocked pattern: {blocked}"
        
        # Rate limiting
        now = time.time()
        if now - self.last_command_time < 0.1:  # Min 100ms between commands
            return False, "Rate limit exceeded"
        
        self.last_command_time = now
        self.commands_executed += 1
        
        # Command count limit (prevent spam)
        if self.commands_executed > 10000:
            return False, "Session command limit exceeded"
        
        return True, ""


class TerminalSession:
    """Manage a single PTY session."""
    
    def __init__(self, session_id: str, on_output: Callable = None):
        self.session_id = session_id
        self.on_output = on_output
        self.process = None
        self.master_fd = None
        self.slave_fd = None
        self.active = False
        self.validator = CommandValidator()
        self.command_history = []
    
    def start(self) -> bool:
        """Start PTY session."""
        try:
            # Fork and create PTY
            self.master_fd, self.slave_fd = pty.openpty()
            
            self.process = subprocess.Popen(
                ['/bin/bash', '--norc'],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd='/opt/music-player',
                start_new_session=True
            )
            
            # Set non-blocking mode
            for fd in [self.master_fd]:
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            self.active = True
            
            # Start read thread
            self.read_thread = Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            
            return True
        
        except Exception as e:
            print(f"Failed to start terminal: {e}")
            return False
    
    def send_command(self, command: str) -> tuple[bool, str]:
        """Send command to terminal.
        
        Args:
            command: Shell command
        
        Returns:
            (success, error_message)
        """
        if not self.active:
            return False, "Terminal not active"
        
        allowed, reason = self.validator.is_allowed(command)
        if not allowed:
            return False, reason
        
        try:
            # Send command with newline
            cmd = command.rstrip() + '\n'
            os.write(self.master_fd, cmd.encode())
            
            self.command_history.append({
                'command': command,
                'timestamp': time.time()
            })
            
            return True, ""
        
        except Exception as e:
            return False, f"Send failed: {str(e)}"
    
    def resize_pty(self, rows: int, cols: int) -> bool:
        """Resize PTY on window change."""
        try:
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, 'TIOCSWINSZ', winsize)
            return True
        except Exception as e:
            print(f"Resize failed: {e}")
            return False
    
    def _read_loop(self) -> None:
        """Background thread reading PTY output."""
        buffer = b''
        
        while self.active:
            try:
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                
                if ready:
                    data = os.read(self.master_fd, 4096)
                    
                    if data:
                        buffer += data
                        
                        # Try to decode and send
                        try:
                            text = buffer.decode('utf-8', errors='replace')
                            if self.on_output:
                                self.on_output(text)
                            buffer = b''
                        except UnicodeDecodeError:
                            # Wait for more data
                            pass
                    else:
                        # Process ended
                        self.stop()
                        break
            
            except OSError:
                # File descriptor closed
                self.stop()
                break
            except Exception as e:
                print(f"Read error: {e}")
                self.stop()
                break
    
    def stop(self) -> None:
        """Stop terminal session."""
        if self.active:
            try:
                if self.process:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                if self.master_fd:
                    os.close(self.master_fd)
                if self.slave_fd:
                    os.close(self.slave_fd)
            except:
                pass
            
            self.active = False


class TerminalManager:
    """Manage multiple terminal sessions."""
    
    def __init__(self, max_sessions: int = 5):
        self.sessions: dict[str, TerminalSession] = {}
        self.max_sessions = max_sessions
        self.session_output_buffers = {}
    
    def create_session(self, session_id: str) -> tuple[bool, str]:
        """Create new terminal session."""
        if len(self.sessions) >= self.max_sessions:
            return False, "Max sessions reached"
        
        session = TerminalSession(
            session_id,
            on_output=lambda data: self._buffer_output(session_id, data)
        )
        
        if session.start():
            self.sessions[session_id] = session
            self.session_output_buffers[session_id] = []
            return True, ""
        
        return False, "Failed to start session"
    
    def send_command(self, session_id: str, command: str) -> tuple[bool, str]:
        """Send command to session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "Session not found"
        
        return session.send_command(command)
    
    def get_output(self, session_id: str) -> str:
        """Get buffered output."""
        buffer = self.session_output_buffers.get(session_id, [])
        output = ''.join(buffer)
        self.session_output_buffers[session_id] = []
        return output
    
    def resize_session(self, session_id: str, rows: int, cols: int) -> bool:
        """Resize session PTY."""
        session = self.sessions.get(session_id)
        if session:
            return session.resize_pty(rows, cols)
        return False
    
    def close_session(self, session_id: str) -> bool:
        """Close session."""
        session = self.sessions.get(session_id)
        if session:
            session.stop()
            del self.sessions[session_id]
            del self.session_output_buffers[session_id]
            return True
        return False
    
    def _buffer_output(self, session_id: str, data: str) -> None:
        """Buffer terminal output."""
        if session_id in self.session_output_buffers:
            self.session_output_buffers[session_id].append(data)


# Global manager
_terminal_manager = TerminalManager()

def get_terminal_manager() -> TerminalManager:
    """Singleton accessor."""
    return _terminal_manager
```

### Step 2: WebSocket Routes

Add to `src/music_player/web/routes.py`:

```python
# Add imports
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import session
import uuid

# Initialize SocketIO (add to app factory in app.py)
socketio = None

def init_socketio(app):
    """Initialize SocketIO for web terminal."""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect(auth):
        """Handle WebSocket connection."""
        session_id = str(uuid.uuid4())[:8]
        session['terminal_id'] = session_id
        
        # Create terminal session
        from music_player.web.terminal_handler import get_terminal_manager
        manager = get_terminal_manager()
        success, msg = manager.create_session(session_id)
        
        if success:
            emit('connected', {'session_id': session_id})
        else:
            emit('error', {'message': msg})
    
    @socketio.on('command')
    def handle_command(data):
        """Handle terminal command."""
        session_id = session.get('terminal_id')
        if not session_id:
            return
        
        command = data.get('command', '')
        
        from music_player.web.terminal_handler import get_terminal_manager
        manager = get_terminal_manager()
        success, msg = manager.send_command(session_id, command)
        
        if not success:
            emit('output', {'data': f"[Error: {msg}]\r\n"})
    
    @socketio.on('resize')
    def handle_resize(data):
        """Handle window resize."""
        session_id = session.get('terminal_id')
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        
        from music_player.web.terminal_handler import get_terminal_manager
        manager = get_terminal_manager()
        manager.resize_session(session_id, rows, cols)
    
    @socketio.on('get_output')
    def handle_get_output():
        """Poll for output."""
        session_id = session.get('terminal_id')
        if not session_id:
            return
        
        from music_player.web.terminal_handler import get_terminal_manager
        manager = get_terminal_manager()
        output = manager.get_output(session_id)
        
        if output:
            emit('output', {'data': output})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle disconnect."""
        session_id = session.get('terminal_id')
        if session_id:
            from music_player.web.terminal_handler import get_terminal_manager
            manager = get_terminal_manager()
            manager.close_session(session_id)

# Route to serve terminal page
@api_bp.route('/terminal', methods=['GET'])
def get_terminal_page():
    """Serve terminal UI."""
    return render_template('terminal.html')
```

Update `app.py` to initialize SocketIO:

```python
# In create_app()
def create_app():
    app = Flask(...)
    # ... existing config ...
    
    # Initialize extensions
    from music_player.web.routes import init_socketio
    init_socketio(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    # Use SocketIO instead of plain Flask
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### Step 3: Terminal UI Template

```html
<!-- src/music_player/web/templates/terminal.html -->

{% extends "base.html" %}

{% block content %}

<style>
    #terminal-container {
        background: #000;
        border-radius: 4px;
        overflow: hidden;
        height: 600px;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.4;
        color: #00d000;
        padding: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    
    #terminal {
        width: 100%;
        height: 100%;
        outline: none;
    }
    
    .terminal-info {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 20px;
        border-left: 4px solid #dc3545;
    }
    
    .terminal-info h3 {
        margin-top: 0;
        color: #dc3545;
    }
    
    .terminal-info ul {
        margin: 10px 0;
        padding-left: 20px;
    }
    
    .terminal-info li {
        margin: 5px 0;
        font-size: 14px;
    }
</style>

<div class="card">
    <h2>⚡ Web Terminal</h2>
    
    <div class="terminal-info">
        <h3>⚠️ Security Warning</h3>
        <ul>
            <li>This terminal has arbitrary command execution capabilities</li>
            <li>Use only on trusted networks</li>
            <li>Some dangerous commands are blocked for safety</li>
            <li>All commands are logged</li>
            <li>Session will close if idle for 30 minutes</li>
        </ul>
    </div>
    
    <div id="terminal-container">
        <div id="terminal"></div>
    </div>
    
    <p style="margin-top: 15px; font-size: 12px; color: #666;">
        Working directory: <code>/opt/music-player</code>
    </p>
</div>

<!-- xterm.js library -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm-addon-fit.min.js"></script>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

<script>
// Initialize terminal
const term = new Terminal({
    rows: 24,
    cols: 80,
    cursorBlink: true,
    theme: {
        background: '#000',
        foreground: '#00d000',
        cursor: '#00ff00'
    }
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);

term.open(document.getElementById('terminal'));
fitAddon.fit();

// Connect to WebSocket
const socket = io();

socket.on('connect', () => {
    term.writeln('Connected to Axehead FM');
    term.write('$ ');
});

socket.on('output', (data) => {
    term.write(data.data);
});

socket.on('error', (data) => {
    term.writeln(`Error: ${data.message}`);
});

// Handle terminal input
let currentCommand = '';

term.onData(data => {
    if (data === '\r') {
        // Enter pressed
        term.writeln('');
        
        if (currentCommand.trim()) {
            socket.emit('command', { command: currentCommand });
            currentCommand = '';
        }
        
        // Poll for output
        socket.emit('get_output');
        
        term.write('$ ');
    } else if (data === '\u007F') {
        // Backspace
        if (currentCommand.length > 0) {
            currentCommand = currentCommand.slice(0, -1);
            term.write('\b \b');
        }
    } else if (data >= ' ' && data <= '~') {
        // Printable character
        currentCommand += data;
        term.write(data);
    }
});

// Handle window resize
window.addEventListener('resize', () => {
    fitAddon.fit();
    const dims = fitAddon.proposeDimensions();
    if (dims) {
        socket.emit('resize', {
            rows: dims.rows,
            cols: dims.cols
        });
    }
});

// Fit on load
setTimeout(() => {
    fitAddon.fit();
    const dims = fitAddon.proposeDimensions();
    if (dims) {
        socket.emit('resize', {
            rows: dims.rows,
            cols: dims.cols
        });
    }
}, 100);
</script>

{% endblock %}
```

---

## Security Hardening

### 1. Authentication

Add to routes:

```python
from flask import request, abort
import functools

def require_terminal_auth(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple PIN auth (in production, use proper auth)
        pin = request.args.get('pin')
        if pin != '1234':  # Change this!
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/terminal', methods=['GET'])
@require_terminal_auth
def get_terminal_page():
    return render_template('terminal.html')
```

### 2. Command Timeout

Add to TerminalSession:

```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Command timeout")

def send_command(self, command: str) -> tuple[bool, str]:
    # ... validation ...
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout
    
    try:
        os.write(self.master_fd, cmd.encode())
        signal.alarm(0)  # Cancel alarm
    except TimeoutError:
        return False, "Command timeout"
```

### 3. Session Timeout

```python
# In TerminalSession
self.last_activity = time.time()

# Periodically check
def is_idle(self, timeout_seconds: int = 1800) -> bool:
    return (time.time() - self.last_activity) > timeout_seconds
```

### 4. Logging

```python
# Log all commands executed
def _log_command(self, command: str) -> None:
    log_file = Path('/opt/music-player/terminal_commands.log')
    with open(log_file, 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'session': self.session_id,
            'command': command
        }) + '\n')
```

---

## Installation

```bash
# Install required packages
pip install flask-socketio python-socketio python-engineio

# On Raspberry Pi
pip install ptyprocess
```

---

## Testing Checklist

### Local Tests
- [ ] Terminal connects via WebSocket
- [ ] Can execute simple commands (ls, pwd, etc)
- [ ] Blocked commands are rejected
- [ ] Output displays correctly
- [ ] Resize works
- [ ] Multiple sessions independent

### Security Tests
- [ ] Blacklist blocks dangerous commands
- [ ] Rate limiting prevents spam
- [ ] Session timeout works
- [ ] Command logging works
- [ ] PIN auth required (if enabled)

### Edge Cases
- [ ] Handle commands with output overflow
- [ ] Escape sequence rendering
- [ ] Long command history
- [ ] Rapid disconnect/reconnect

---

## Usage Examples

Once deployed:

```bash
# Check system resources
free -h
df -h
ps aux

# Monitor player
systemctl status music-player
journalctl -u music-player -f

# Manage files
ls -la /opt/music-player/media/
du -sh /opt/music-player/media/*

# Restart service
systemctl restart music-player
```

---

## Limitations & Future Work

- [ ] No file upload/download (would require base64 encoding)
- [ ] Limited color support
- [ ] No copy/paste optimization
- [ ] Basic prompt detection only
- [ ] No command history search (Ctrl+R)

Would be nice to add:
- SFTP interface for file management
- Proper RBAC with user accounts
- Command history with search
- Session recording
- WebGL acceleration for large outputs

---

## Troubleshooting

### WebSocket Connection Fails
```bash
# Check Flask-SocketIO is installed
pip list | grep -i socket

# Check port 5000 is open
netstat -tlnp | grep 5000
```

### PTY Creation Fails
- Ensure script runs as non-root with TTY capabilities
- Check `/dev/pts` is available

### Slow Output
- Reduce `select()` timeout in `_read_loop()`
- Increase buffer size in `os.read()`

---

## Final Notes

This is a **nice-to-have** feature. Prioritize Phase 1-3 for core functionality.

Terminal access is powerful but requires careful security consideration on production systems.

For headless operation, consider SSH as safer alternative to web terminal.
