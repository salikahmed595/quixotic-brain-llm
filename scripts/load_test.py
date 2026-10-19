"""AT-09 load test — PRD §2 targets and §13 AT-09: 160 logged-in employees, a 40-concurrent-chat baseline and a 160-chat burst;
p95 chat answer < 8 s, p95 retrieval < 2 s; errors and recovery.

    # 1. test accounts (run where the database is reachable, e.g. inside the api container)
    LOAD_PASSWORD=... python scripts/load_test.py prepare --users 160 --department Sales
    # 2. the test (from any machine that can reach the site)
    LOAD_PASSWORD=... python scripts/load_test.py run --url https://ai.example.com --users 160 --baseline 40 --mode search
    LOAD_PASSWORD=... python scripts/load_test.py run --url https://ai.example.com --users 160 --baseline 40 --mode answer
    # 3. remove them
    python scripts/load_test.py cleanup

--mode search measures retrieval only (no AI cost). --mode answer calls the answer model for every question (costs money).
Questions come from --questions FILE (one per line) or a small built-in set; use questions your documents actually answer."""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import sys
import time
from pathlib import Path

PREFIX = "load_"
QUESTIONS = ["What is the refund policy?", "How do I hand over a client to the upseller?", "What do I say when a customer says it is too expensive?",
             "What is the booking script?", "How do we qualify a lead?", "What are the office hours?", "How long do refunds take?",
             "Customer wants a discount, what can I offer?", "What is the escalation process for complaints?", "How do I greet a new customer?"]


def prepare(n: int, department: str) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.auth.security import hash_password
    from backend.config import get_settings
    from backend.database.pool import make_pool
    from backend.database.users import UserStore
    from backend.permissions.roles import Role
    pw = os.environ["LOAD_PASSWORD"]
    s = get_settings()
    users = UserStore(make_pool(s.database_url), s.tenant_id)
    dept = users.department_by_name(department)
    if not dept:
        raise SystemExit(f"unknown department {department!r}")
    h = hash_password(pw)
    made = 0
    for i in range(1, n + 1):
        name = f"{PREFIX}{i:03d}"
        if not users.get_by_login(name):
            users.create_user(name, f"{name}@load.invalid", f"Load test {i:03d}", h, Role.EMPLOYEE, [dept["id"]])
            made += 1
    print(f"{made} new load-test employees in {department} ({n} total)")


def cleanup() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.config import get_settings
    from backend.database.pool import make_pool
    from backend.database.users import UserStore
    s = get_settings()
    users = UserStore(make_pool(s.database_url), s.tenant_id)
    n = 0
    for u in users.list_users(PREFIX):
        if u["employee_id"].startswith(PREFIX) and u["account_status"] == "active":
            users.set_status(u["id"], "deactivated", None, "load test finished")
            n += 1
    print(f"{n} load-test accounts deactivated")


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


async def run(url: str, n: int, baseline: int, rounds: int, mode: str, questions: list[str]) -> int:
    import httpx
    pw = os.environ["LOAD_PASSWORD"]
    limits = httpx.Limits(max_connections=n + 10, max_keepalive_connections=n + 10)
    async with httpx.AsyncClient(base_url=url.rstrip("/"), timeout=120, limits=limits) as http:
        async def login(i: int):
            r = await http.post("/v1/auth/login", json={"identifier": f"{PREFIX}{i:03d}", "password": pw})
            r.raise_for_status()
            return {"Authorization": "Bearer " + r.cookies["qb_session"]}
        t0 = time.perf_counter()
        sessions = await asyncio.gather(*(login(i) for i in range(1, n + 1)), return_exceptions=True)
        ok = [s for s in sessions if isinstance(s, dict)]
        print(f"signed in {len(ok)}/{n} employees in {time.perf_counter() - t0:.1f} s ({n} concurrent sessions: {'OK' if len(ok) == n else 'FAILED'})")
        if not ok:
            return 1
        path = "/v1/search" if mode == "search" else "/v1/ask"

        async def one(h) -> tuple[float, bool]:
            q = random.choice(questions)
            s = time.perf_counter()
            try:
                r = await http.post(path, headers=h, json={"question": q})
                return time.perf_counter() - s, r.status_code == 200
            except httpx.HTTPError:
                return time.perf_counter() - s, False

        async def phase(name: str, concurrency: int, total: int) -> tuple[list[float], int]:
            sem, times, errors = asyncio.Semaphore(concurrency), [], 0

            async def worker(k: int):
                nonlocal errors
                async with sem:
                    dt, good = await one(ok[k % len(ok)])
                    times.append(dt)
                    errors += 0 if good else 1
            s = time.perf_counter()
            await asyncio.gather(*(worker(k) for k in range(total)))
            wall = time.perf_counter() - s
            print(f"{name}: {total} requests, {concurrency} at a time, {wall:.1f} s, p50 {pct(times, 50):.2f} s, p95 {pct(times, 95):.2f} s, "
                  f"p99 {pct(times, 99):.2f} s, errors {errors} ({100 * errors / total:.1f}%)")
            return times, errors

        base, e1 = await phase("baseline", baseline, baseline * rounds)
        burst, e2 = await phase("burst", len(ok), len(ok))
        target = 2.0 if mode == "search" else 8.0
        verdict = pct(base, 95) < target and pct(burst, 95) < target and e1 + e2 == 0
        print(f"target p95 < {target:.0f} s ({'retrieval' if mode == 'search' else 'chat answer'}): {'PASS' if verdict else 'FAIL'}")
        return 0 if verdict else 2


def main() -> int:
    ap = argparse.ArgumentParser(prog="load_test")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--users", type=int, default=160); p.add_argument("--department", required=True)
    sub.add_parser("cleanup")
    r = sub.add_parser("run")
    r.add_argument("--url", required=True); r.add_argument("--users", type=int, default=160); r.add_argument("--baseline", type=int, default=40)
    r.add_argument("--rounds", type=int, default=3, help="baseline requests = baseline x rounds")
    r.add_argument("--mode", choices=["search", "answer"], default="search"); r.add_argument("--questions")
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.users, a.department); return 0
    if a.cmd == "cleanup":
        cleanup(); return 0
    qs = [l.strip() for l in Path(a.questions).read_text(encoding="utf-8").splitlines() if l.strip()] if a.questions else QUESTIONS
    return asyncio.run(run(a.url, a.users, a.baseline, a.rounds, a.mode, qs))


if __name__ == "__main__":
    sys.exit(main())
