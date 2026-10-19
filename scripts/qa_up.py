"""QA instance on :8010 against the qa_copy database (never the live one): API + worker, Redis queue, console email, its own vault.
Used for live end-to-end, RAG, security and load testing. Run via .claude/launch.json "quixotic-qa"."""
import os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env.setdefault(k.strip(), v.strip())
env.update({"QB_DATABASE_URL": "postgresql://quixotic:quixotic@localhost:5432/qa_copy", "QB_QUEUE_BACKEND": "redis",
            "QB_REDIS_URL": "redis://localhost:6390/0", "QB_VAULT_DIR": str(ROOT / ".qa-vault"), "QB_PUBLIC_URL": "http://localhost:8010",
            "QB_MAIL_BACKEND": "console", "QB_TELEGRAM_BOT_TOKEN": "", "QB_RAW_STORAGE_DIR": str(ROOT / ".devstore"),
            "QB_FRONTEND_DIR": str(ROOT / "web" / "dist")})
procs = [subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8010"], env=env, cwd=ROOT),
         subprocess.Popen([sys.executable, "-m", "workers.worker"], env=env, cwd=ROOT)]
try:
    while all(p.poll() is None for p in procs): time.sleep(1)
finally:
    for p in procs: p.terminate()
