#!/usr/bin/env python3
"""
Argus System Unified Runner
Starts all backend microservices (Master, Detect, Tracker, Crash)
and optionally starts the GUI and Camera nodes.
"""

import sys
import os
import time
import subprocess
import signal

PYTHON = sys.executable

def start_backend():
    print("=" * 60)
    print("  Starting ARGUS Autonomous Accident Detection System")
    print("=" * 60)
    
    scripts = [
        ("Master Node  (Port 10000)", [PYTHON, "RunMaster.py"]),
        ("Detect Node  (Port 10002)", [PYTHON, "RunDetect.py"]),
        ("Tracker Node (Port 10004)", [PYTHON, "RunTracker.py"]),
        ("Crash Node   (Port 10008)", [PYTHON, "RunCrash.py"]),
    ]

    processes = []
    
    try:
        for name, cmd in scripts:
            print(f"[+] Launching {name}...")
            p = subprocess.Popen(cmd)
            processes.append((name, p))
            time.sleep(0.5)

        print("\nAll backend services are RUNNING!")
        print("-" * 60)
        
        mode = "all"
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()

        if mode in ("all", "gui"):
            print("[+] Launching Surveillance GUI (RunGui.py)...")
            gui_proc = subprocess.Popen([PYTHON, "RunGui.py"])
            processes.append(("Surveillance GUI", gui_proc))
            time.sleep(0.5)

        if mode in ("all", "camera"):
            print("[+] Launching Camera Node (RunCamera.py)...")
            cam_proc = subprocess.Popen([PYTHON, "RunCamera.py"])
            processes.append(("Camera Node", cam_proc))

        print("\nSystem running. Press Ctrl+C to terminate all services.\n")
        
        # Wait for any process to terminate or keyboard interrupt
        while True:
            for name, p in processes:
                ret = p.poll()
                if ret is not None and name in ("Surveillance GUI", "Camera Node"):
                    # GUI or Camera was closed by the user
                    pass
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Shutting down all Argus services...")
    finally:
        for name, p in processes:
            if p.poll() is None:
                print(f"[-] Stopping {name} (PID: {p.pid})...")
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("[✓] All services stopped.")

if __name__ == "__main__":
    start_backend()
