"""Regenerate docs/product/* from PRODUCT.md. Run from the repo root: python docs/product/split.py"""
import re, os, shutil
src = open('PRODUCT.md', encoding='utf-8').read().split('\n')
out = 'docs/product'
for f in os.listdir(out):
    if f != 'split.py':
        os.remove(f'{out}/{f}')
head = re.compile(r'^#{1,2} (\d+)\. (.+?)\s*$')
secs, cur, fence, pre = [], None, False, []
for ln in src:
    if ln.strip().startswith('```'):
        fence = not fence
    m = None if fence else head.match(ln)
    if m:
        cur = {'n': int(m.group(1)), 't': m.group(2), 'lines': []}
        secs.append(cur)
    (cur['lines'] if cur else pre).append(ln)
slug = lambda t: re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')
def clean(lines):
    s = re.sub(r'\n-{3,}\s*$', '', '\n'.join(lines).strip()).strip()
    return s + '\n'
OVERRIDE = {
 1: 'Name, type, org, AWS target, primary users; "One Brain. Multiple Quixotic products."',
 6: 'Diagram: Knowledge + Sales Memory + Business Rules -> RAG engine -> API layer -> apps',
 7: 'Pipeline: auth, permissions, filters, normalize, BM25 + BGE-M3, rerank 20-40 to 5-8, LLM, sources',
 9: 'Employee, Contributor, Manager, Administrator: what each can and cannot do',
 12: 'Knowledge types, Add Knowledge form (no technical terms), approval workflow, tracked fields',
 13: 'V1 file types, upload form, processing pipeline (extract, chunk, embed, index)',
 14: 'Metadata JSON per chunk; used for access, filtering, versions, analytics',
 17: 'Discord JSON import UI and 15-step processing pipeline',
 23: 'Roman Urdu normalization example; keep the original query for audit',
 25: 'BM25: exact names, codes, IDs, acronyms, error codes',
 28: 'Replaceable LLM layer (OpenAI, Gemini, Claude, Bedrock, local); generate_answer()',
 29: 'Answer only from retrieved knowledge; never invent policies or prices; "not found" reply',
 30: 'Source format (title, section, version, updated) and historical evidence counts',
 33: 'Sidebar: Ask Brain, Knowledge, Sales Memory, Add Information, Documents, Insights + Admin items',
 35: 'Failed questions list (low confidence, not found) with Add Missing Knowledge action',
 36: 'Knowledge health counters: active, outdated, no owner, stale, duplicates, conflicts',
 37: 'Core /v1 endpoints: ask, search, documents, sales-memory, feedback, health',
 38: 'POST /v1/ask request and response JSON',
 42: 'RBAC flow: user, role, department, permissions, metadata filter, retrieval (before retrieval)',
 43: 'Why AWS (credits, private networking, RDS, S3, ECS, SQS, CloudWatch)',
 44: 'V1 stack per layer: Next.js/Vercel, FastAPI/ECS, RDS pgvector, S3, SQS, BGE-M3, Bedrock',
 46: 'S3 buckets/paths: raw/documents, raw/discord, processed, exports, backups',
 47: 'Async jobs via SQS + ECS workers; frontend shows progress',
 50: 'Repo layout: frontend, backend modules, workers, evaluation, migrations, docs',
 52: 'Documents are data, never instructions; malicious-document example',
 54: 'Backups: RDS automatic, S3 versioning, metadata, config',
 55: 'CloudWatch metrics: errors, latency, CPU, queue depth, model latencies',
 56: 'Targets: search < 2s, full answer 5-8s, dashboard < 2s, instant upload acceptance',
 58: 'Company-specific evaluation question set with expected sources',
 62: 'User stories: employee, sales agent, manager, admin, developer',
 65: 'Core principle: knowledge belongs to the Brain; apps consume it, never duplicate it',
 67: 'Final definition: not just a chatbot; engine, RAG platform, sales memory, API, assistant',
}
def summary(body, subs):
    lines = [l.strip() for l in body.split('\n')[1:]]
    prose = [l for l in lines if l and not l.startswith(('#', '```', '|', '>', '<!--')) and not re.match(r'^(\d+\.|[-*•])\s', l)]
    first = prose[0] if prose else ''
    if first.endswith(':'):
        items = [re.sub(r'^([-*]|\d+\.)\s*', '', l) for l in lines if re.match(r'^([-*]|\d+\.)\s', l)][:4]
        first = (first[:-1] + ': ' + ', '.join(items)) if items else first
    if not first and subs:
        first = ', '.join(subs[:4])
    return first.replace('|', '/')[:130]
idx, tot = [], 0
for s in secs:
    body = re.sub(r'^#{1,2} (\d+)\. ', r'# \1. ', clean(s['lines']), count=1)
    fn = f"{s['n']:02d}-{slug(s['t'])}.md"
    open(f'{out}/{fn}', 'w', encoding='utf-8').write(f"<!-- PRODUCT.md section {s['n']} -->\n" + body)
    subs = [re.sub(r'^#+\s*', '', l) for l in body.split('\n') if re.match(r'^###+ ', l)]
    tok = len(body) // 4; tot += tok
    idx.append((s['n'], s['t'], fn, tok, OVERRIDE.get(s['n']) or summary(body, subs)))
open(f'{out}/00-title.md', 'w', encoding='utf-8').write(clean(pre))
groups = {'Vision & scope': range(1, 9), 'People & structure': range(9, 11), 'Ask Brain & knowledge': range(11, 16),
 'Sales memory & intelligence': range(16, 22), 'Language & retrieval': range(22, 29), 'Answer quality': range(29, 33),
 'Frontend & dashboards': range(33, 37), 'API & access': range(37, 43), 'Infrastructure & data': range(43, 51),
 'Security & operations': range(51, 57), 'Scale, evaluation & cost': range(57, 61), 'Plan & success': range(61, 68)}
full = sum(len(l) + 1 for l in src) // 4
L = ['# Quixotic Brain — Product Spec Index', '',
 f'`PRODUCT.md` (~{full:,} tokens) is split into {len(idx)} section files in `docs/product/` (largest ~{max(i[3] for i in idx)} tokens). Read this index, then open only the file(s) you need. Token counts are estimates (~4 chars/token).', '',
 '## Quick lookup', '', '| If you need… | Open |', '|---|---|',
 '| What the product is, goals, non-goals | 01, 04, 05 |', '| Roles & permissions (RBAC) | 09, 42 |', '| Ask Brain behaviour, modes, example | 11 |',
 '| Knowledge entry, approval states, versions | 12, 15 |', '| Uploading documents | 13 |', '| Sales memory & Discord import | 16–19 |',
 '| Retrieval pipeline | 07, 24–27 |', '| Answer rules (sources, confidence, no hallucination, priority) | 20, 29–32 |', '| API endpoints & keys | 37–40 |',
 '| Stack, AWS, database | 43–50 |', '| Security & audit | 51–53 |', '| Phases & acceptance criteria | 61, 63, 64 |', '']
for g, r in groups.items():
    L += [f'## {g}', '', '| # | Section | File | ~Tok | Covers |', '|---|---|---|---|---|']
    L += [f'| {n} | {t} | [{fn}]({fn}) | {tok} | {sm} |' for n, t, fn, tok, sm in idx if n in r]
    L.append('')
L += ['## Conventions', '', '- Every file is self-contained and starts with a comment naming its section number.',
 '- Cross-references use section numbers; jump to `NN-*.md`.', '- Source of truth is `PRODUCT.md`; edit it, then re-run `python docs/product/split.py`.', '']
open(f'{out}/INDEX.md', 'w', encoding='utf-8').write('\n'.join(L))
print(len(idx), 'sections, ~', tot, 'tokens total; index ~', len('\n'.join(L)) // 4)
