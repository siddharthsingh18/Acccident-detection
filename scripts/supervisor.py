#!/usr/bin/env python3
"""
Argus Full-Stack Multi-Process Supervisor.
Starts the 4 computer vision backend nodes, the FastAPI bridge, and the Vite frontend
in the correct sequential order with port readiness verification and colored log prefixes.
"""
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

# ANSI Colors
COLORS = {
    "MASTER": "\033[94m",    # Blue
    "DETECT": "\033[96m",    # Cyan
    "TRACKER": "\033[95m",   # Magenta
    "CRASH": "\033[93m",     # Yellow
    "BRIDGE": "\033[92m",    # Green
    "FRONTEND": "\033[97m",  # White
    "SYSTEM": "\033[91m",    # Red
    "RESET": "\033[0m",
    "BOLD": "\033[1m"
}

SERVICES = [
    {
        "name": "MASTER",
        "cmd": [str(VENV_PYTHON), "RunMaster.py"],
        "cwd": str(ROOT_DIR),
        "port": 10000,
        "color": COLORS["MASTER"]
    },
    {
        "name": "DETECT",
        "cmd": [str(VENV_PYTHON), "RunDetect.py"],
        "cwd": str(ROOT_DIR),
        "port": 10002,
        "color": COLORS["DETECT"]
    },
    {
        "name": "TRACKER",
        "cmd": [str(VENV_PYTHON), "RunTracker.py"],
        "cwd": str(ROOT_DIR),
        "port": 10004,
        "color": COLORS["TRACKER"]
    },
    {
        "name": "CRASH",
        "cmd": [str(VENV_PYTHON), "RunCrash.py"],
        "cwd": str(ROOT_DIR),
        "port": 10008,
        "color": COLORS["CRASH"]
    },
    {
        "name": "BRIDGE",
        "cmd": [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        "cwd": str(BACKEND_DIR),
        "port": 8000,
        "color": COLORS["BRIDGE"]
    },
    {
        "name": "FRONTEND",
        "cmd": ["npm", "run", "dev"],
        "cwd": str(FRONTEND_DIR),
        "port": 5173,
        "color": COLORS["FRONTEND"]
    }
]

processes = []
shutting_down = False

def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def wait_for_port(port: int, service_name: str, timeout: float = 15.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.3)
    return False

def pipe_output(proc, name, color):
    prefix = f"{color}[{name:<8}]{COLORS['RESET']} "
    for line in iter(proc.stdout.readline, ""):
        line = line.rstrip()
        if line:
            print(f"{prefix}{line}", flush=True)

def shutdown(signum=None, frame=None):
    global shutting_down
    if shutting_down:
        return
    shutting_down = True
    print(f"\n{COLORS['SYSTEM']}{COLORS['BOLD']}[SYSTEM] Shutting down all Argus services...{COLORS['RESET']}", flush=True)

    for p, name in reversed(processes):
        try:
            print(f"{COLORS['SYSTEM']}[SYSTEM] Terminating {name}...{COLORS['RESET']}", flush=True)
            p.terminate()
        except Exception:
            pass

    time.sleep(1.0)
    for p, name in processes:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

    print(f"{COLORS['SYSTEM']}[SYSTEM] All Argus processes stopped.{COLORS['RESET']}", flush=True)
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

def main():
    print(f"\n{COLORS['BOLD']}{COLORS['BRIDGE']}=================================================={COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}   ARGUS MULTI-NODE SUPERVISOR STARTING UP        {COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}=================================================={COLORS['RESET']}\n")

    for svc in SERVICES:
        name = svc["name"]
        color = svc["color"]
        port = svc["port"]

        print(f"{color}{COLORS['BOLD']}>>> Starting {name} on port {port}...{COLORS['RESET']}")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = f"{ROOT_DIR}:{BACKEND_DIR}"

        proc = subprocess.Popen(
            svc["cmd"],
            cwd=svc["cwd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        processes.append((proc, name))

        t = threading.Thread(target=pipe_output, args=(proc, name, color), daemon=True)
        t.start()

        # Wait for port readiness
        ready = wait_for_port(port, name, timeout=12.0)
        if ready:
            print(f"{color}✓ {name} is READY and listening on 127.0.0.1:{port}{COLORS['RESET']}\n")
        else:
            print(f"{COLORS['SYSTEM']}! {name} started (port {port} check pending/async){COLORS['RESET']}\n")

    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}=================================================={COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}  ALL ARGUS SERVICES ACTIVE & RUNNING!            {COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}  Frontend UI:  http://localhost:5173             {COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}  Bridge Docs:  http://127.0.0.1:8000/docs        {COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}  Press Ctrl+C to terminate all processes.        {COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{COLORS['BRIDGE']}=================================================={COLORS['RESET']}\n")

    while True:
        time.sleep(1)
        for proc, name in processes:
            ret = proc.poll()
            if ret is not None and not shutting_down:
                print(f"{COLORS['SYSTEM']}[SYSTEM] Process {name} exited unexpectedly with code {ret}!{COLORS['RESET']}", flush=True)

if __name__ == "__main__":
    main()
