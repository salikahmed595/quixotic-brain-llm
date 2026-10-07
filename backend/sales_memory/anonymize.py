"""Anonymize personal data before indexing — PRD §18 / §17.2.

PRD §18 lists what to remove: Discord usernames, email addresses, phone numbers, payment
credentials, passwords, API keys, home addresses, private customer IDs.

Implemented detectors: usernames (names supplied by the parser + @mentions), emails, phone numbers,
payment card numbers (Luhn), passwords / API keys / secrets (key=value patterns and Quixotic's own
`qx_live_` keys). NOT detectable without company-specific rules (docs/PRD_GAPS.md): home addresses and
private customer IDs — pass `extra_patterns` (regex -> placeholder) once the formats are known.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
PHONE = re.compile(r"(?<![\w])\+?\d[\d\s().\-]{8,16}\d(?![\w])")
SECRET_KV = re.compile(r"(?i)\b(password|passwd|pwd|api[_\- ]?key|secret|token)\b(\s*[:=]\s*)\S+")
QX_KEY = re.compile(r"\bqx_live_\S+")
MENTION = re.compile(r"@[\w.\-]{2,32}")


def _luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


class Anonymizer:
    def __init__(self, usernames: Iterable[str] = (), extra_patterns: Optional[dict[str, str]] = None) -> None:
        names = sorted({u for u in usernames if u}, key=len, reverse=True)
        self._users = [re.compile(re.escape(n), re.IGNORECASE) for n in names]
        self._extra = [(re.compile(p), r) for p, r in (extra_patterns or {}).items()]

    def clean(self, text: str) -> str:
        text = QX_KEY.sub("[API_KEY]", text)
        text = SECRET_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
        text = EMAIL.sub("[EMAIL]", text)
        text = CARD.sub(lambda m: "[PAYMENT_CARD]" if _luhn(m.group(0)) else m.group(0), text)
        text = PHONE.sub(lambda m: "[PHONE]" if 10 <= sum(c.isdigit() for c in m.group(0)) <= 15 else m.group(0), text)
        text = MENTION.sub("[USER]", text)
        for rx in self._users:
            text = rx.sub("[USER]", text)
        for rx, repl in self._extra:
            text = rx.sub(repl, text)
        return text
