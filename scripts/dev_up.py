"""Start everything the app needs on your own machine, in one command:  python scripts/dev_up.py

  1. a local S3 + SQS stand-in (moto) on :5000, with the bucket and queue from .env
  2. database migrations
  3. the API (also serves the web app) on http://localhost:8000
  4. the background worker (processes uploads)
PostgreSQL must already be running:  docker compose up -d postgres
Press Ctrl+C to stop everything."""
import os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if not (ROOT / ".env").is_file():
    sys.exit("No .env file. Copy .env.example to .env and review the values first (see docs/backend.md).")
env = {**os.environ}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():     # .env -> environment (also for boto3's dummy credentials)
    if line.strip() and not line.lstrip().startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        v = re.sub(r"\s+#.*$", "", v).strip().strip("'\"")                # drop trailing "  # comment", like python-dotenv
        env.setdefault(k.strip(), v)
# PRD §11 front-end (web/): build it once if there is no build yet (needs Node.js; skipped with a note otherwise).
if not (ROOT / "web" / "dist" / "index.html").is_file():
    import shutil
    npm = shutil.which("npm")
    if npm:
        print("Building the web app (first run)...")
        subprocess.run([npm, "ci"], cwd=ROOT / "web", check=True)
        subprocess.run([npm, "run", "build"], cwd=ROOT / "web", check=True)
    else:
        print("Node.js is not installed, so the web app was not built. Install Node.js, then run: cd web && npm ci && npm run build")
procs = []
def start(*args): p = subprocess.Popen([sys.executable, *args], env=env, cwd=ROOT); procs.append(p); return p
try:
    start("-m", "moto.server", "-p", "5000"); time.sleep(4)
    import boto3
    kw = dict(region_name="us-east-1", endpoint_url="http://localhost:5000", aws_access_key_id="local", aws_secret_access_key="local")
    try: boto3.client("s3", **kw).create_bucket(Bucket=env["QB_S3_BUCKET"])
    except Exception as e: print("bucket:", e)
    try: boto3.client("sqs", **kw).create_queue(QueueName=env["QB_SQS_QUEUE_URL"].rsplit("/", 1)[1])
    except Exception as e: print("queue:", e)
    subprocess.run([sys.executable, "-m", "backend.cli", "migrate"], env=env, cwd=ROOT, check=True)
    start("-m", "uvicorn", "backend.main:app", "--port", "8000")
    start("-m", "workers.worker")
    print("\n  Open  http://localhost:8000  in your browser.   (Ctrl+C to stop)\n")
    while all(p.poll() is None for p in procs): time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in procs: p.terminate()
