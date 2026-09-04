"""
Backend Startup & Runner Script
Starts docker-compose services (PostgreSQL & Redis), waits for container readiness,
runs Alembic database migrations, and launches FastAPI server via Uvicorn.
"""

import sys
import os
import time
import socket
import subprocess
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

def run_command(cmd, cwd=None, check=True):
    print(f"🚀 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, cwd=cwd or BASE_DIR, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        print(f"❌ Command failed with code {res.returncode}")
        sys.exit(res.returncode)
    return res

def wait_for_port(host: str, port: int, service_name: str, timeout: int = 30):
    print(f"⏳ Waiting for {service_name} at {host}:{port}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"✅ {service_name} is online and reachable at {host}:{port}!")
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(1.5)
    print(f"⚠️ Warning: Could not connect to {service_name} at {host}:{port} after {timeout} seconds.")
    return False

def main():
    print("=" * 60)
    print("🤖 AI Contract Reviewer Backend Startup")
    print("=" * 60)

    # 1. Start Docker containers (PostgreSQL & Redis)
    docker_cmd = None
    if DOCKER_COMPOSE_FILE.exists():
        # Check docker-compose or docker compose
        try:
            res_compose = subprocess.run(["docker-compose", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res_compose.returncode == 0:
                docker_cmd = ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "-d", "db", "redis"]
        except FileNotFoundError:
            pass

        if not docker_cmd:
            try:
                res_dock = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res_dock.returncode == 0:
                    docker_cmd = ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "-d", "db", "redis"]
            except FileNotFoundError:
                pass

    if docker_cmd:
        print("🐋 Launching PostgreSQL and Redis containers via Docker Compose...")
        run_command(docker_cmd, cwd=PROJECT_ROOT, check=False)
    else:
        print("ℹ️ docker-compose not found or not in PATH. Assuming local PostgreSQL & Redis instances are active.")

    # 2. Wait for DB and Redis ports
    wait_for_port("127.0.0.1", 5432, "PostgreSQL Database", timeout=15)
    wait_for_port("127.0.0.1", 6379, "Redis Server", timeout=15)

    # 3. Apply Alembic DB Migrations
    print("\n📦 Applying Alembic database migrations...")
    try:
        run_command([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BASE_DIR, check=False)
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # 4. Start Uvicorn FastAPI Server
    print("\n⚡ Starting FastAPI Uvicorn Server on http://127.0.0.1:8000 ...")
    try:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    except ImportError:
        run_command([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"], cwd=BASE_DIR)

if __name__ == "__main__":
    main()
