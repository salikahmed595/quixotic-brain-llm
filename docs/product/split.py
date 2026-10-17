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
 1: 'Permission-aware RAG assistant; never invent policies/prices/refunds; missing evidence -> knowledge-gap request',
 2: 'Six goals; targets: p95 chat < 8s, retrieval < 2s, >=95% cited, 0 cross-dept leaks, reindex < 60s, 160/40 load',
 3: 'Employee, Dept Manager/Reviewer, Knowledge Admin, System Admin, Founder/CEO; server-side deny-by-default',
 4: 'Screenshot-exact UI: shared hero/composer/cards, employee vs admin sidebar order, responsive rules',
 5: 'FR-AUTH-01..07: signup, email verification, Pending, admin approval, account states, Argon2id/sessions/MFA',
 6: 'FR-CHAT-01..09: chats, voice, suggestion cards, Company Knowledge default, not-found text, Web Search, scopes',
 7: 'Admin page table: Knowledge ... System minimum functionality',
 8: 'Obsidian Markdown vault, document fields/statuses, ACL-first hybrid retrieval, DeepSeek, atomic publication',
 9: 'Phase 2: Hermes Telegram/Discord proposals, voice notes, diffs, approval, reindex; knowledge-gap loop',
 10: 'RBAC + ABAC before retrieval, secrets server-side, audit, upload protection, provider approval, retention',
 11: 'React+TS+Tailwind, FastAPI, Postgres/pgvector, Redis worker, Docker; minimum API contract',
 12: 'Core data entities list; last indexed version + checksum; idempotent bot events',
 13: 'AT-01..AT-09 acceptance journeys',
 14: 'P0 Phase 1 ... P3 Later',
 15: 'Exclusions for v1',
 16: 'Definition of done; implementation direction to Claude Code',
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
groups = {'Vision, goals & roles': range(1, 4), 'UI': range(4, 5), 'Auth & chat': range(5, 7),
 'Admin & knowledge': range(7, 10), 'Security & architecture': range(10, 13), 'Acceptance, phases & done': range(13, 17)}
full = sum(len(l) + 1 for l in src) // 4
L = ['# Quixotic AI — Product Spec Index', '',
 f'`PRODUCT.md` (~{full:,} tokens) is split into {len(idx)} section files in `docs/product/` (largest ~{max(i[3] for i in idx)} tokens). Read this index, then open only the file(s) you need. Token counts are estimates (~4 chars/token).', '',
 '## Quick lookup', '', '| If you need… | Open |', '|---|---|',
 '| Vision, goals, targets | 01, 02 |', '| Roles & permissions | 03, 10 |', '| UI (screenshots, sidebars, responsive) | 04 |',
 '| Signup, approval, login, account states | 05 |', '| Chat behaviour, not-found text, Web Search | 06 |', '| Admin pages | 07 |',
 '| Documents, versions, retrieval pipeline | 08 |', '| Telegram/Discord/Hermes, knowledge gaps | 09 |', '| Stack & API contract | 11 |',
 '| Data entities | 12 |', '| Acceptance tests, phases, exclusions, done | 13–16 |', '']
for g, r in groups.items():
    L += [f'## {g}', '', '| # | Section | File | ~Tok | Covers |', '|---|---|---|---|---|']
    L += [f'| {n} | {t} | [{fn}]({fn}) | {tok} | {sm} |' for n, t, fn, tok, sm in idx if n in r]
    L.append('')
L += ['## Conventions', '', '- Every file is self-contained and starts with a comment naming its section number.',
 '- Cross-references use section numbers; jump to `NN-*.md`.', '- Source of truth is `PRODUCT.md`; edit it, then re-run `python docs/product/split.py`.', '']
open(f'{out}/INDEX.md', 'w', encoding='utf-8').write('\n'.join(L))
print(len(idx), 'sections, ~', tot, 'tokens total; index ~', len('\n'.join(L)) // 4)
