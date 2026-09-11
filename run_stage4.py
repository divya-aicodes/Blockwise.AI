"""Start the Stage 4 frontend and existing backend together for local use."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def main():
    frontend_root = ROOT / 'frontend'
    vite_entry = frontend_root / 'node_modules' / 'vite' / 'bin' / 'vite.js'
    node = _which('node.exe' if os.name == 'nt' else 'node')
    if not node:
        raise SystemExit('Node.js is not installed or is not on PATH. Install Node.js LTS and reopen PowerShell.')
    if not vite_entry.exists():
        raise SystemExit('Frontend dependencies are missing. Run: npm.cmd install --prefix frontend')

    # Reuse healthy services so running the launcher twice never creates a
    # second server or kills a process that this invocation did not create.
    processes = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        if not _backend_is_ready():
            backend = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
                 '--host', '127.0.0.1', '--port', '8000'],
                cwd=ROOT, creationflags=flags,
            )
            processes.append(backend)
            _wait_for('http://127.0.0.1:8000/health', backend, 'Backend')

        if not _frontend_is_ready():
            # Calling Vite through node.exe avoids the Windows npm.cmd wrapper
            # exiting before the child server is ready.
            frontend = subprocess.Popen(
                [node, str(vite_entry), '--host', '127.0.0.1', '--port', '5173'],
                cwd=frontend_root, creationflags=flags,
            )
            processes.append(frontend)
            _wait_for('http://127.0.0.1:5173/', frontend, 'Frontend')

        print('Dashboard: http://127.0.0.1:5173\nAPI docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop.',flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
    except KeyboardInterrupt:
        print('\nStopping project...', flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                else:
                    process.terminate()


def _which(command: str) -> str | None:
    """Resolve an executable without relying on npm's Windows batch wrapper."""
    for directory in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(directory) / command
        if candidate.exists():
            return str(candidate)
    return None


def _backend_is_ready() -> bool:
    try:
        with urlopen('http://127.0.0.1:8000/health', timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def _wait_for(url: str, process: subprocess.Popen, label: str) -> None:
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError(f'{label} stopped before becoming ready (exit code {process.returncode}).')
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(.25)
    raise RuntimeError(f'{label} did not become ready. Check the port and dependency installation.')


def _frontend_is_ready() -> bool:
    try:
        with urlopen('http://127.0.0.1:5173/', timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


if __name__ == '__main__':
    main()
