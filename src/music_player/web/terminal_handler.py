import shlex
import subprocess
import time
from typing import List


class CommandValidator:
    """Very small command filter for the basic web terminal."""

    BLACKLIST = {
        "rm -rf",
        "dd ",
        "mkfs",
        "shutdown",
        "reboot",
        "halt",
        "curl | bash",
        "wget | bash",
    }

    def __init__(self) -> None:
        self.commands_executed = 0
        self.last_command_time = 0.0

    def is_allowed(self, command: str) -> tuple[bool, str]:
        cmd = command.strip().lower()
        if not cmd:
            return True, ""
        for blocked in self.BLACKLIST:
            if blocked in cmd:
                return False, f"Blocked command pattern: {blocked.strip()}"

        now = time.time()
        if now - self.last_command_time < 0.1:
            return False, "Rate limit exceeded"
        self.last_command_time = now
        self.commands_executed += 1
        if self.commands_executed > 200:
            return False, "Session command limit exceeded"
        return True, ""


class TerminalSession:
    """Simple shell execution helper for the web terminal."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.validator = CommandValidator()
        self.history: List[str] = []

    def execute(self, command: str) -> dict:
        allowed, reason = self.validator.is_allowed(command)
        if not allowed:
            return {"ok": False, "error": reason}

        self.history.append(command)
        try:
            argv = shlex.split(command)
            result = subprocess.run(
                argv,
                cwd="/opt/music-player",
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            output = (result.stdout or "") + (result.stderr or "")
            return {
                "ok": True,
                "output": output,
                "returncode": result.returncode,
            }
        except FileNotFoundError:
            return {"ok": False, "error": "Command not found"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Command timed out"}
