#!/usr/bin/env python3
"""
Argus Environment Verification Script
Verifies Python version, ffmpeg/ffprobe, required Python packages, and free network ports.
"""
import shutil
import socket
import sys
from pathlib import Path

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

REQUIRED_PORTS = [
    (10000, "Master Node (ZeroMQ)"),
    (10002, "Detection Node (ZeroMQ)"),
    (10004, "Tracker Node (ZeroMQ)"),
    (10008, "Crash Node (ZeroMQ)"),
    (10010, "Alert / GUI Port (ZeroMQ)"),
    (8000,  "FastAPI Bridge (HTTP/WS)"),
    (5173,  "Vite Frontend Dev Server")
]

REQUIRED_PACKAGES = [
    ("zmq", "pyzmq"),
    ("cv2", "opencv-python"),
    ("numpy", "numpy"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("multipart", "python-multipart"),
]

def check_port_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False

def main():
    print(f"\n{BOLD}{CYAN}=== Argus Road Accident Detection System Check ==={RESET}\n")
    all_ok = True

    # 1. Python Version Check
    v = sys.version_info
    print(f"{BOLD}1. Python Environment:{RESET}")
    print(f"   Interpreter: {sys.executable}")
    print(f"   Version:     {v.major}.{v.minor}.{v.micro}")

    if v.major == 3 and v.minor == 11:
        print(f"   Status:      {GREEN}[OK] Python 3.11 is the recommended supported version for Argus.{RESET}")
    elif v.major == 3 and v.minor < 14:
        print(f"   Status:      {YELLOW}[WARN] Python {v.major}.{v.minor} detected. Python 3.11 is strongly recommended.{RESET}")
    else:
        print(f"   Status:      {RED}[FAIL] Python {v.major}.{v.minor} is incompatible (Python >= 3.14 removed 'imghdr').{RESET}")
        print(f"   {YELLOW}Fix: Install Python 3.11 via Homebrew: 'brew install python@3.11' and create a virtualenv.{RESET}")
        all_ok = False

    # 2. System Binaries Check (ffmpeg, ffprobe, node, npm)
    print(f"\n{BOLD}2. System Binaries:{RESET}")
    for bin_name in ["ffmpeg", "ffprobe", "node", "npm"]:
        path = shutil.which(bin_name)
        if path:
            print(f"   {bin_name:<10}: {GREEN}[OK]{RESET} Found at {path}")
        else:
            print(f"   {bin_name:<10}: {RED}[MISSING]{RESET} Not found in PATH.")
            all_ok = False
            if bin_name in ("ffmpeg", "ffprobe"):
                print(f"   {YELLOW}Fix: brew install ffmpeg{RESET}")
            elif bin_name in ("node", "npm"):
                print(f"   {YELLOW}Fix: brew install node{RESET}")

    # 3. Python Packages Check
    print(f"\n{BOLD}3. Required Python Packages:{RESET}")
    for mod_name, pkg_name in REQUIRED_PACKAGES:
        try:
            __import__(mod_name)
            print(f"   {pkg_name:<20}: {GREEN}[OK]{RESET}")
        except ImportError:
            print(f"   {pkg_name:<20}: {RED}[MISSING]{RESET}")
            all_ok = False

    # 4. Free Ports Check
    print(f"\n{BOLD}4. Network Ports Availability (127.0.0.1):{RESET}")
    for port, desc in REQUIRED_PORTS:
        is_free = check_port_free(port)
        if is_free:
            print(f"   Port {port:<5} ({desc:<27}): {GREEN}[AVAILABLE]{RESET}")
        else:
            print(f"   Port {port:<5} ({desc:<27}): {YELLOW}[OCCUPIED / IN USE]{RESET}")
            # If in use, might be already running Argus; warn rather than hard fail
            print(f"   {YELLOW}Notice: If another instance of Argus is running, run 'make stop' to free it.{RESET}")

    print("\n" + "=" * 52)
    if all_ok:
        print(f"{GREEN}{BOLD}✓ System environment is READY to launch Argus!{RESET}")
        print("Run 'make dev' to start all services.")
    else:
        print(f"{RED}{BOLD}✗ Some prerequisites are missing. Please resolve the items above.{RESET}")
    print("=" * 52 + "\n")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
