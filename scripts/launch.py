"""One-command launcher for Quant Pricer (used by start.command, start.bat and `make`).

serve (default)  Build the web app if stale, run a single FastAPI process serving API + SPA,
                 open the browser.
dev              Run uvicorn --reload and the Vite dev server side by side (hot reload).

Stdlib only; run through `uv run` so the Python environment is synced first.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST_INDEX = WEB / "dist" / "index.html"
VITE_PORT = 5173
IS_WINDOWS = os.name == "nt"


def log(msg: str) -> None:
    print(f"[quant-pricer] {msg}", flush=True)


def npm() -> str:
    exe = shutil.which("npm")
    if exe is None:
        sys.exit("npm not found: install Node.js 20+ from https://nodejs.org/")
    return exe


def ensure_web_deps() -> None:
    lock = WEB / "package-lock.json"
    marker = WEB / "node_modules" / ".package-lock.json"
    if not marker.exists() or marker.stat().st_mtime < lock.stat().st_mtime:
        log("installing web dependencies (npm ci)…")
        subprocess.run([npm(), "ci"], cwd=WEB, check=True)


def web_is_stale() -> bool:
    if not DIST_INDEX.exists():
        return True
    built = DIST_INDEX.stat().st_mtime
    sources = [
        *(WEB / "src").rglob("*"),
        *WEB.glob("*.json"),
        *WEB.glob("*.ts"),
        WEB / "index.html",
    ]
    return any(p.is_file() and p.stat().st_mtime > built for p in sources)


def wait_for(url: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def spawn(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    kwargs: dict[str, object] = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True  # own process group, so children die with it
    return subprocess.Popen(cmd, cwd=cwd, env=env, **kwargs)  # type: ignore[call-overload,no-any-return]


def stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def uvicorn_cmd(port: int, reload: bool) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if reload:
        cmd += ["--reload", "--reload-dir", "engine", "--reload-dir", "api"]
    return cmd


def run(procs: list[subprocess.Popen[bytes]]) -> int:
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.3)
        return next(p.returncode for p in procs if p.poll() is not None) or 0
    except KeyboardInterrupt:
        return 0
    finally:
        log("shutting down…")
        for p in procs:
            stop(p)


def serve(port: int, browser: bool) -> int:
    ensure_web_deps()
    if web_is_stale():
        log("building web app…")
        subprocess.run([npm(), "run", "build"], cwd=WEB, check=True)
    api = spawn(uvicorn_cmd(port, reload=False), ROOT)
    url = f"http://127.0.0.1:{port}"
    if not wait_for(f"{url}/api/health"):
        stop(api)
        sys.exit(f"API did not start on port {port} (already in use?)")
    log(f"running at {url}  (Ctrl+C to stop)")
    if browser:
        webbrowser.open(url)
    return run([api])


def dev(port: int, browser: bool) -> int:
    ensure_web_deps()
    api = spawn(uvicorn_cmd(port, reload=True), ROOT)
    web = spawn([npm(), "run", "dev"], WEB, env={**os.environ, "QP_API_PORT": str(port)})
    url = f"http://localhost:{VITE_PORT}"
    ok = wait_for(f"http://127.0.0.1:{port}/api/health") and wait_for(url)
    if not ok:
        for p in (api, web):
            stop(p)
        sys.exit("dev servers did not start (ports in use?)")
    log(f"dev UI at {url}, API at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    if browser:
        webbrowser.open(url)
    return run([api, web])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("mode", nargs="?", choices=["serve", "dev"], default="serve")
    parser.add_argument("--port", type=int, default=int(os.getenv("QP_API_PORT", "8765")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.mode == "dev":
        return dev(args.port, not args.no_browser)
    return serve(args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
