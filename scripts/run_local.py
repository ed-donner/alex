#!/usr/bin/env python3
"""
Run both frontend and backend locally for development.
This script starts the NextJS frontend and FastAPI backend in parallel.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# On Windows, npm/node are .cmd files and need shell=True to be found
IS_WINDOWS = sys.platform == "win32"

# On Windows, stdout may default to a non-UTF-8 codepage (e.g. cp1252) when not
# attached to a real console, which crashes on the emoji this script prints
if IS_WINDOWS:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Track subprocesses for cleanup
processes = []

def cleanup(signum=None, frame=None):
    """Clean up all subprocess on exit"""
    print("\n🛑 Shutting down services...")
    for proc in processes:
        try:
            if IS_WINDOWS:
                # proc.terminate() only kills the immediate wrapper (uv/cmd.exe),
                # leaving the real backend/frontend server as an orphan. Kill the
                # whole process tree instead.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True
                )
            else:
                proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
    sys.exit(0)

# Register cleanup handlers
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def check_requirements():
    """Check if required tools are installed"""
    checks = []

    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
        checks.append(f"✅ Node.js: {node_version}")
    except FileNotFoundError:
        checks.append("❌ Node.js not found - please install Node.js")

    # Check npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True, shell=IS_WINDOWS)
        npm_version = result.stdout.strip()
        checks.append(f"✅ npm: {npm_version}")
    except FileNotFoundError:
        checks.append("❌ npm not found - please install npm")

    # Check uv (which manages Python for us)
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        uv_version = result.stdout.strip()
        checks.append(f"✅ uv: {uv_version}")
    except FileNotFoundError:
        checks.append("❌ uv not found - please install uv")

    print("\n📋 Prerequisites Check:")
    for check in checks:
        print(f"  {check}")

    # Exit if any critical tools are missing
    if any("❌" in check for check in checks):
        print("\n⚠️  Please install missing dependencies and try again.")
        sys.exit(1)

def check_env_files():
    """Check if environment files exist"""
    project_root = Path(__file__).parent.parent

    root_env = project_root / ".env"
    frontend_env = project_root / "frontend" / ".env.local"

    missing = []

    if not root_env.exists():
        missing.append(".env (root project file)")
    if not frontend_env.exists():
        missing.append("frontend/.env.local")

    if missing:
        print("\n⚠️  Missing environment files:")
        for file in missing:
            print(f"  - {file}")
        print("\nPlease create these files with the required configuration.")
        print("The root .env should have all backend variables from Parts 1-7.")
        print("The frontend/.env.local should have Clerk keys.")
        sys.exit(1)

    print("✅ Environment files found")

def start_backend():
    """Start the FastAPI backend"""
    backend_dir = Path(__file__).parent.parent / "backend" / "api"

    print("\n🚀 Starting FastAPI backend...")

    # Check if dependencies are installed
    if not (backend_dir / ".venv").exists() and not (backend_dir / "uv.lock").exists():
        print("  Installing backend dependencies...")
        subprocess.run(["uv", "sync"], cwd=backend_dir, check=True)

    # Start the backend
    proc = subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout (main.py's logging goes to stderr)
        text=True,
        bufsize=1
    )
    processes.append(proc)

    # Continuously drain the backend's output pipe. Without this, once the OS
    # pipe buffer fills up (main.py's logging.basicConfig() defaults to
    # stderr), the backend's next log call blocks forever, freezing its
    # single-threaded event loop - and with it, every request including /health.
    import threading

    def read_backend_output():
        for line in proc.stdout:
            print(f"    Backend: {line.strip()}")

    threading.Thread(target=read_backend_output, daemon=True).start()

    # Wait for backend to start
    print("  Waiting for backend to start...")
    for _ in range(30):  # 30 second timeout
        try:
            import httpx
            response = httpx.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("  ✅ Backend running at http://localhost:8000")
                print("     API docs: http://localhost:8000/docs")
                return proc
        except:
            time.sleep(1)

    print("  ❌ Backend failed to start")
    cleanup()

def start_frontend():
    """Start the NextJS frontend"""
    frontend_dir = Path(__file__).parent.parent / "frontend"

    print("\n🚀 Starting NextJS frontend...")

    # Check if dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        print("  Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True, shell=IS_WINDOWS)

    # Start the frontend
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout
        text=True,
        bufsize=1,
        shell=IS_WINDOWS
    )
    processes.append(proc)

    # Wait for frontend to start
    print("  Waiting for frontend to start...")
    import httpx
    import threading

    # Read frontend output in a background thread (select.select doesn't work on Windows pipes)
    started_flag = {"started": False}

    def read_output():
        for line in proc.stdout:
            print(f"    Frontend: {line.strip()}")
            if "ready" in line.lower() or "compiled" in line.lower() or "started server" in line.lower():
                started_flag["started"] = True

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    for i in range(90):  # 90 second timeout (cold Next.js starts can take ~30s)
        if proc.poll() is not None:
            print("  ❌ Frontend process exited unexpectedly (see output above)")
            cleanup()

        if started_flag["started"] or i > 5:  # Start checking after 5 seconds
            try:
                response = httpx.get("http://localhost:3000", timeout=1)
                print("  ✅ Frontend running at http://localhost:3000")
                return proc
            except httpx.ConnectError:
                pass  # Server not ready yet
            except:
                # Any other response means server is up
                print("  ✅ Frontend running at http://localhost:3000")
                return proc

        time.sleep(1)

    print("  ❌ Frontend failed to start")
    cleanup()

def monitor_processes():
    """Monitor running processes and show their output"""
    print("\n" + "="*60)
    print("🎯 Alex Financial Advisor - Local Development")
    print("="*60)
    print("\n📍 Services:")
    print("  Frontend: http://localhost:3000")
    print("  Backend:  http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print("\n📝 Logs will appear below. Press Ctrl+C to stop.\n")
    print("="*60 + "\n")

    import httpx
    last_health_check = 0.0
    consecutive_backend_failures = 0
    consecutive_frontend_failures = 0
    FAILURE_THRESHOLD = 3  # require 3 consecutive misses before treating it as dead

    # Monitor processes
    while True:
        # Both backend and frontend stdout are drained by their own background
        # reader threads (started in start_backend/start_frontend), so this
        # loop doesn't read their output itself - doing so would race with
        # those threads and reintroduce the pipe-buffer deadlock they exist to
        # prevent.

        # On Windows, the intermediate wrapper process (uv/cmd.exe) can exit
        # on its own while the real server underneath keeps running, so we
        # can't rely on proc.poll() to detect a crash. Poll the actual
        # services instead. The backend does blocking AWS calls per-request,
        # so a single slow health check under load isn't necessarily a crash -
        # require several consecutive misses before shutting down.
        now = time.time()
        if now - last_health_check > 5:
            last_health_check = now

            try:
                backend_ok = httpx.get("http://localhost:8000/health", timeout=5).status_code == 200
            except Exception:
                backend_ok = False
            consecutive_backend_failures = 0 if backend_ok else consecutive_backend_failures + 1

            try:
                httpx.get("http://localhost:3000", timeout=5)
                frontend_ok = True
            except httpx.ConnectError:
                frontend_ok = False
            except Exception:
                frontend_ok = True  # any response at all means it's up
            consecutive_frontend_failures = 0 if frontend_ok else consecutive_frontend_failures + 1

            if consecutive_backend_failures >= FAILURE_THRESHOLD or consecutive_frontend_failures >= FAILURE_THRESHOLD:
                dead = "Backend" if consecutive_backend_failures >= FAILURE_THRESHOLD else "Frontend"
                print(f"\n⚠️  {dead} stopped responding!")
                cleanup()

        time.sleep(0.1)

def main():
    """Main entry point"""
    print("\n🔧 Alex Financial Advisor - Local Development Setup")
    print("="*50)

    # Check prerequisites
    check_requirements()
    check_env_files()

    # Install httpx if needed
    try:
        import httpx
    except ImportError:
        print("\n📦 Installing httpx for health checks...")
        subprocess.run(["uv", "add", "httpx"], check=True)

    # Start services
    start_backend()
    start_frontend()

    # Monitor processes
    try:
        monitor_processes()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()