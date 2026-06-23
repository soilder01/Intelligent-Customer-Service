#!/usr/bin/env python3
"""Start local API and frontend dev servers with correct addresses.

This script avoids the common mistake of opening 0.0.0.0 in a browser.
It binds services to 0.0.0.0 but prints localhost URLs for access.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Agent API and React frontend locally.")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--mock", action="store_true", help="Run frontend in mock mode without calling API")
    args = parser.parse_args()

    env = os.environ.copy()
    if args.mock:
        env["VITE_AGENT_API_BASE"] = "mock"
    else:
        env.setdefault("VITE_AGENT_API_BASE", "")

    api_cmd = [sys.executable, "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", str(args.api_port)]
    fe_cmd = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", str(args.frontend_port)]

    print(f"API access URL:      http://localhost:{args.api_port}/api/health")
    print(f"Frontend access URL: http://localhost:{args.frontend_port}/")
    print("Do not open http://0.0.0.0:<port>; 0.0.0.0 is only a bind address.\n")

    api = subprocess.Popen(api_cmd, cwd=ROOT, env=env)
    frontend = subprocess.Popen(fe_cmd, cwd=ROOT / "frontend", env=env)
    try:
        frontend.wait()
        return frontend.returncode or 0
    finally:
        api.terminate()
        api.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
