"""Quality regression suite V2 runner (owner request 2026-10-26). Runs every case in cases.json live against the API, then grades it:
fixed checks in code (language, length, structure, forbidden phrases, image prompt) plus an LLM judge for the 'must' criteria.
A case passes only if every fixed check AND every judged criterion passes, in EVERY repeat.

    python -m evaluation.quality_v2.run --base https://maqsad.quixoticcreatives.com --repeat 2 --label after
    python -m evaluation.quality_v2.run --only TR1,FB1

Credentials: QA_EMPLOYEE_USER / QA_PASSWORD (environment or web/.env.visual). Judge: OPENAI_API_KEY (environment or .env),
model QB_JUDGE_MODEL (default gpt-5-mini). Results: evaluation/quality_v2/results/<label>.json with, per case and repeat, the
input, mode, history (with the live answers), expected language and structure, constraints, output, pass/fail and reasons."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from backend.retrieval.language import LanguageService

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LANG = LanguageService(0.3)


def _env_file(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.split(" #")[0].strip()
    return out


ENV = {**_env_file(ROOT / ".env"), **_env_file(ROOT / "web" / ".env.visual"), **os.environ}


class Client:
    def __init__(self, base: str):
        self.http = httpx.Client(base_url=base, timeout=600)
        r = self.http.post("/v1/auth/login", json={"identifier": ENV["QA_EMPLOYEE_USER"], "password": ENV["QA_PASSWORD"]})
        r.raise_for_status()
        self.http.headers["x-csrf-token"] = r.json()["csrf_token"]

    def turn(self, mode: str, text: str, target: str | None, conversation_id: str | None) -> dict:
        t = time.time()
        if mode == "translate":
            r = self.http.post("/v1/translate", json={"text": text, "target": target or "auto"})
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"detail": r.text[:300]}
            return {"status": r.status_code, "seconds": round(time.time() - t, 1), "answer": j.get("translation") or j.get("detail"),
                    "detected": j.get("source"), "target": j.get("target")}
        r = self.http.post("/v1/ask", json={"question": text, "conversation_id": conversation_id})
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"detail": r.text[:300]}
        return {"status": r.status_code, "seconds": round(time.time() - t, 1), "answer": j.get("answer") or j.get("detail"),
                "conversation_id": j.get("conversation_id"), "image": bool(j.get("image")), "image_prompt": j.get("image_prompt"),
                "task": j.get("task")}


def _language(text: str) -> str:
    body = "\n".join(l for l in text.splitlines() if l.strip())
    return LANG.detect(body)


def fixed_checks(case: dict, out: dict) -> list[dict]:
    c, text, res = case.get("checks", {}), out.get("answer") or "", []

    def add(name, ok, why=""):
        res.append({"check": name, "pass": bool(ok), "reason": "" if ok else why})

    add("http 200", out.get("status") == 200, f"status {out.get('status')}: {text[:120]}")
    words = len(re.findall(r"[\w']+", text))
    if "language" in c:
        got = _language(text)
        ok = got == c["language"] or (c["language"] == "roman_urdu" and got == "mixed")
        add(f"language {c['language']}", ok, f"detected {got}")
    if c.get("not_same_as_input"):
        norm = lambda s: re.sub(r"\W", "", s.lower())
        add("not a copy of the input", norm(text) != norm(case["input"]), "output equals the input")
    if "max_words" in c:
        add(f"<= {c['max_words']} words", words <= c["max_words"], f"{words} words")
    if "min_words" in c:
        add(f">= {c['min_words']} words", words >= c["min_words"], f"{words} words")
    if c.get("no_bullets"):
        add("no bullets", not re.search(r"(?m)^\s*(?:[-*•]|\d+[.)])\s", text), "has bullet or numbered lines")
    if "paragraphs" in c:
        n = len([b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()])
        add(f"{c['paragraphs']} paragraph(s)", n == c["paragraphs"], f"{n} paragraphs")
    if "max_messages" in c:
        n = len(re.findall(r"(?m)^\s*>>", text))
        add(f"<= {c['max_messages']} message(s)", n <= c["max_messages"], f"{n} >> messages")
    for pat in c.get("forbid", []):
        m = re.search(pat, text)
        add(f"forbid {pat}", not m, f"found {m.group(0)!r}" if m else "")
    for word in c.get("must_contain", []):
        add(f"contains {word}", word in text, "missing")
    if c.get("image"):
        add("image created", out.get("image"), "no image returned")
    if c.get("image_prompt_contains_any"):
        p = out.get("image_prompt") or ""
        add("image prompt keeps the request", any(w.lower() in p.lower() for w in c["image_prompt_contains_any"]), f"prompt: {p[:160]}")
    return res


JUDGE_PROMPT = """You grade one answer of Quixotic AI, an assistant used by staff of a digital-artwork company that sells to Discord
clients. Grade ONLY against the listed criteria, strictly and literally. Count items exactly. The output is the assistant's
answer as shown to the employee ('>>' lines are messages meant to be sent to a client).
Return ONLY JSON: {"criteria": [{"criterion": "...", "pass": true|false, "reason": "short reason"}]}"""


def judge(case: dict, history: list[dict], out: dict) -> list[dict]:
    if not case.get("must"):
        return []
    from openai import OpenAI
    client = OpenAI(api_key=ENV.get("OPENAI_API_KEY"))
    hist = "\n".join(f"[earlier turn] employee: {h['q']}\nassistant: {(h.get('answer') or '')[:1500]}" for h in history)
    user = (f"Task mode: {case['mode']}" + (f" (target {case.get('target')})" if case["mode"] == "translate" else "") +
            f"\n{hist}\n[current] employee: {case['input']}\nExpected language: {case['expected_language']}; expected structure: "
            f"{case['expected_structure']}\n\nASSISTANT OUTPUT:\n{out.get('answer')}\n" +
            (f"IMAGE PROMPT USED: {out.get('image_prompt')}\n" if out.get("image_prompt") else "") +
            "\nCriteria:\n" + "\n".join(f"- {m}" for m in case["must"]))
    for _ in range(3):
        try:
            r = client.chat.completions.create(model=ENV.get("QB_JUDGE_MODEL", "gpt-5-mini"), reasoning_effort="low",
                                               messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}])
            raw = r.choices[0].message.content or ""
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            return [{"check": f"judge: {c['criterion']}", "pass": bool(c["pass"]), "reason": c.get("reason", "")} for c in data["criteria"]]
        except Exception as e:                        # judge hiccup: retry, then record it as a failure with the reason
            err = str(e)
    return [{"check": "judge", "pass": False, "reason": f"judge failed: {err[:200]}"}]


def run_case(base: str, case: dict, repeat: int) -> dict:
    cl = Client(base)
    cid, history = None, []
    for h in case.get("history", []):
        o = cl.turn(h["mode"], h["q"], h.get("target"), cid)
        cid = o.get("conversation_id") or cid
        history.append({**h, "answer": o.get("answer")})
    out = cl.turn(case["mode"], case["input"], case.get("target"), cid)
    checks = fixed_checks(case, out) + judge(case, history, out)
    failed = [c for c in checks if not c["pass"]]
    return {"id": case["id"], "issue": case["issue"], "repeat": repeat, "mode": case["mode"], "target": case.get("target"),
            "input": case["input"], "history": history, "expected_language": case["expected_language"],
            "expected_structure": case["expected_structure"], "constraints": {"checks": case.get("checks", {}), "must": case.get("must", [])},
            "output": out.get("answer"), "image_prompt": out.get("image_prompt"), "task": out.get("task"), "seconds": out.get("seconds"),
            "pass": not failed, "failure_reason": "; ".join(f"{c['check']}: {c['reason']}" for c in failed), "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=ENV.get("QA_BASE_URL", "https://maqsad.quixoticcreatives.com"))
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--label", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    jobs = [(c, r) for c in cases for r in range(1, a.repeat + 1)]
    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(lambda j: run_case(a.base, *j), jobs))
    (HERE / "results").mkdir(exist_ok=True)
    path = HERE / "results" / f"{a.label}.json"
    by_case = {}
    for r in results:
        by_case.setdefault(r["id"], []).append(r)
    summary = [{"id": k, "issue": v[0]["issue"], "pass": all(x["pass"] for x in v), "passed_repeats": f"{sum(x['pass'] for x in v)}/{len(v)}",
                "failure_reasons": [x["failure_reason"] for x in v if not x["pass"]]} for k, v in by_case.items()]
    path.write_text(json.dumps({"label": a.label, "base": a.base, "repeat": a.repeat, "summary": summary, "results": results},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    for s in summary:
        print(f"{'PASS' if s['pass'] else 'FAIL'}  {s['id']:4} issue {s['issue']}  {s['passed_repeats']}  " +
              (s["failure_reasons"][0][:230] if s["failure_reasons"] else ""))
    print(f"\n{sum(s['pass'] for s in summary)}/{len(summary)} cases pass in every repeat -> {path}")


if __name__ == "__main__":
    main()
