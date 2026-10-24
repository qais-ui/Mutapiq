"""Start the no-login legal demo from a normal clone (Python 3.11+).

Run: python run_demo.py
Ollama is optional for the review, required for AI-assisted catalogue selection.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    os.environ["MUTABIQ_DB"] = str(ROOT / "db" / "preview" / "mutabiq.db")
    os.environ.setdefault("MUTABIQ_MODEL", "qwen2.5:3b-instruct")
    from core.db import DB_PATH

    if not DB_PATH.exists():
        subprocess.run([sys.executable, "scripts/seed.py"], check=True, stdout=subprocess.DEVNULL)
    children = []
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        try:
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=2):
                ollama_running = True
        except OSError:
            ollama_running = False
        if not ollama_running and shutil.which("ollama"):
            children.append(subprocess.Popen(["ollama", "serve"], env={
                **os.environ, "OLLAMA_HOST": "127.0.0.1:11434",
                "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1",
                "OLLAMA_KEEP_ALIVE": "2m",
            }))
        children.append(subprocess.Popen([
            sys.executable, "-c",
            "from demo_site.app import app; app.run(host='127.0.0.1', port=5001, use_reloader=False)",
        ]))
        children.append(subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "demo_app.py",
            "--server.address=127.0.0.1", f"--server.port={os.getenv('PORT', '8501')}",
            "--browser.gatherUsageStats=false",
        ]))
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return next((child.returncode or 1 for child in children if child.poll() is not None), 1)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
