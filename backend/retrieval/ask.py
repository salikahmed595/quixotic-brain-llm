"""Ask Brain orchestration — PRD §7 (flow), §11, §20, §29, §30, §32.

Authentication and the permission check happen before this service is called; it receives the
already-resolved department scope.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence
from uuid import UUID

from ..config import Settings
from ..generation.base import GenerationProvider
from ..generation.prompt import MISSING_COMPANY_INFO, OFF_TOPIC
from ..models import AnswerContext, Candidate
from .language import NormalizedQuery
from .search import SearchService, confidence_label

# PRD §6 FR-CHAT-04: "If no verified answer is found: 'I couldn't find an approved answer in the company knowledge base.'
# Offer Report missing information." The exact wording is the PRD's; it is used for every case without approved evidence.
NOT_FOUND_TEXT = "I couldn't find an approved answer in the company knowledge base."
LOW_CONFIDENCE_TEXT = NOT_FOUND_TEXT
NOT_FOUND_ACTIONS = ["report_missing_information", "search_documents"]
LOW_CONFIDENCE_ACTIONS = NOT_FOUND_ACTIONS
# The answer model writes exactly this when the passages it was given do not answer the question (generation/prompt.py rule 3).
NO_APPROVED_ANSWER = "NO_APPROVED_ANSWER"
# Owner request (2026-10-08): an answer written only from past sales chats always starts with this line (PRD §19: keep
# historical correlation and official policy clearly distinguishable).
# MEASURED on 800 of the owner's chats: "hello" (0.97) and "thanks" (0.88) match chat lines more closely than real sales
# questions do (0.58-0.72), so similarity alone cannot decide; the answer model also confirms the chats are on topic.
NO_RELEVANT_HISTORY = "NO_RELEVANT_HISTORY"
HISTORY_ONLY_LABEL = ("Based on past sales chats, not an official Quixotic policy. "
                      "No approved policy or SOP covers this yet.")
# Owner decision 2026-10-21: a "what should I reply?" question with no policy and no matching past chat gets careful advice that
# follows the selling boundaries, always under this label, never with prices/discounts/deadlines (checked below), still a gap.
GENERAL_GUIDANCE = "GENERAL_GUIDANCE"
GENERAL_GUIDANCE_LABEL = ("General guidance, not company policy. No approved policy or past chat covers this yet; "
                          "check prices, discounts and deadlines with your team lead.")
_FORBIDDEN_IN_GUIDANCE = re.compile(r"[$€£₨]|\bPKR\b|\bRs\.?\s*\d|\d+\s*%|\b\d+\s*(?:day|days|hour|hours|week|weeks)\b"
                                    r"|\bdollars?\b", re.I)
_OFFERS = re.compile(r"\b(?:offer|give|provide|apply|process|start|issue)\w*\s+(?:you\s+|a\s+|an\s+|the\s+|some\s+|your\s+)*"
                     r"(?:discount|refund|price\s+cut|cheaper)", re.I)
# General assistant (owner 2026-10-21): money figures in a commercial context must come from approved knowledge. MEASURED on the
# server: asked "what discount can I give a returning client?" with no policy, the model once invented "5% off, $10-$25" tiers.
_MONEY = re.compile(r"\$\s?\d[\d,.]*|\d+(?:\.\d+)?\s?%|\bPKR\s?\d[\d,]*|\bRs\.?\s?\d[\d,]*|\b\d[\d,]*\s?(?:dollars?|rupees?)\b", re.I)
_COMMERCIAL = re.compile(r"discount|price|pricing|refund|fee|cost|rate|payment|upfront|commission|salary|package|deposit|charge",
                         re.I)
STRICT_RETRY_NOTE = ("\n\n(System check: do not state ANY price, amount, percentage, discount or fee figure. None is approved for "
                     "this. Say it is not in the company knowledge base and suggest confirming with the team lead.)")
SAFE_MISSING = ("That is not in the company knowledge base yet, so I can't give you a figure. Please confirm it with your team lead "
                "before telling the client.")


def _invented_money(text: str, knowledge) -> bool:
    if not _COMMERCIAL.search(text):
        return False
    allowed = {m.group(0).replace(" ", "").lower() for c in knowledge for m in _MONEY.finditer(c.text or "")}
    return any(m.group(0).replace(" ", "").lower() not in allowed for m in _MONEY.finditer(text))


# Owner 2026-10-21 "for our office only": out-of-scope questions get this fixed reply (no gap, no model text).
OFF_TOPIC_TEXT = ("I'm Quixotic AI, the office assistant, so I only help with Quixotic work: client replies and sales, company "
                  "policies and SOPs, work messages and translation. What can I help you with at work?")
# Payment terms are company policy too (owner rule). MEASURED on the server: with no policy imported, gpt-5-nano kept offering
# "a payment plan", "milestones" and "pausing work" despite the prompt, so unapproved term offers are removed in code.
_TERMS = re.compile(r"payment plan|instal+ments?|milestones?|split (?:the )?(?:payment|work|invoice)|partial payment|"
                    r"pause (?:the )?(?:work|project)|deposit|upfront|discount|refund|free revision|extra revisions?", re.I)
CHECK_WITH_TEAM = "Let me check the options with my team and get back to you shortly."
ASK_TEAM_LEAD = ("Payment plans, discounts and similar options are not in the company knowledge yet: ask your team lead "
                 "which options are approved.")


def _unapproved_terms(text: str, knowledge) -> set:
    allowed = " ".join((c.text or "") for c in knowledge).lower()
    return {m.group(0).lower() for m in _TERMS.finditer(text) if m.group(0).lower() not in allowed}


def _drop_term_offers(text: str, knowledge) -> str:
    """Lines offering an unapproved term are replaced: a client message (>>) by one 'check with my team' message, advice to the
    user (any other line, e.g. '- Offer a payment plan') by one 'ask your team lead' line. 'Why:' lines are kept."""
    out, msg_done, tip_done = [], False, False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.lower().startswith("why:") or not _unapproved_terms(line, knowledge):
            out.append(line)
        elif stripped.startswith(">>"):
            if not msg_done:
                out.append(f">> {CHECK_WITH_TEAM}")
                msg_done = True
        elif not tip_done:
            out.append(f"- {ASK_TEAM_LEAD}")
            tip_done = True
    return "\n".join(out)


SUCCESSFUL_OUTCOME = "closed"        # §16.2 example outcome value; PRD defines no other success rule


def order_by_priority(chunks: list[Candidate], tiers: dict[str, int]) -> list[Candidate]:
    """§20 hierarchy. Tier numbers per document_type come from configuration (the PRD names the
    tiers, not the mapping). Unmapped types sit between tier 3 and the historical tier 4; with no
    mapping configured the reranker order is kept."""
    if not tiers:
        return chunks
    return sorted(chunks, key=lambda c: tiers.get(c.document_type or "", 3.5))      # stable sort


def source_of(c: Candidate) -> dict:
    """PRD §6 FR-CHAT-04 citations: document title, relevant section and effective/updated date, plus the version (AT-03)."""
    return {"title": c.title, "section": c.section, "version": c.version, "document_id": str(c.item_id), "version_id": str(c.version_id),
            "updated": c.updated_at.isoformat() if c.updated_at else None}


@dataclass
class AskResult:
    answer: str
    confidence: str
    confidence_score: Optional[float]
    found: bool                                           # False -> a "failed question" (§35)
    sources: list[dict] = field(default_factory=list)
    historical_cases: Optional[dict] = None               # §30 "17 similar cases / 12 successful outcomes"
    actions: list[str] = field(default_factory=list)
    query: Optional[NormalizedQuery] = None
    retrieved: list[Candidate] = field(default_factory=list)


NON_ENGLISH = ("roman_urdu", "urdu", "mixed")


class AskService:
    def __init__(self, search: SearchService, generator: GenerationProvider, settings: Settings) -> None:
        self.search, self.generator, self.settings = search, generator, settings

    def _interpret(self, question: str, history: Sequence[tuple[str, str]]) -> str:
        """PRD §23 'semantic interpretation': for Urdu / Roman Urdu / mixed questions and for follow-ups in a chat; a first English
        question needs no extra call, so it stays fast."""
        if not self.settings.query_interpretation or not hasattr(self.generator, "interpret_query"):
            return ""
        # A follow-up inside a chat ("what should I say to Ali if he still refuses?") is restated as a standalone query using
        # the chat so far, in any language. MEASURED on the owner's first chats: without it this 10-word follow-up found nothing.
        if not history and self.search.language.detect(question) not in NON_ENGLISH:
            return ""
        return self.generator.interpret_query(question, list(history)[-1:]) or ""

    def ask(self, question: str, department_ids: frozenset[UUID], include_sales_history: bool = False,
            sales_department_ids: frozenset[UUID] = frozenset(), levels: frozenset[str] = frozenset(),
            history: Sequence[tuple[str, str]] = (), asker: Optional[dict] = None,
            preferences: Optional[dict] = None, recheck=None) -> AskResult:
        """`history`: earlier (question, answer) pairs of the same chat, oldest first. Used only to understand what a short
        follow-up refers to, never as a source of facts. `recheck(version_ids) -> still allowed ids` re-checks permissions and
        publication right before the answer is returned (PRD §8 "Recheck permissions before providing the final source/answer")."""
        previous = history[-1][0] if history else None
        interpretation = self._interpret(question, history)
        out = self.search.search(question, department_ids, levels, previous_question=previous,
                                 extra_search_text=interpretation)
        base = dict(confidence=out.confidence, confidence_score=out.confidence_score, query=out.query,
                    retrieved=out.candidates)
        min_sim = self.settings.sales_history_min_similarity
        cases = []
        if (self.settings.sales_history_enabled and (include_sales_history or min_sim is not None)   # owner: OFF (2026-10-17)
                and sales_department_ids and out.embedding is not None):
            cases = self.search.store.sales_search(out.embedding, self.search.embedder.name,
                                                   sales_department_ids, self.settings.historical_top_k)
            if min_sim is not None:
                cases = [c for c in cases if c.similarity >= min_sim]
        if getattr(self.settings, "general_assistant", False):                   # owner 2026-10-21: ChatGPT-like assistant
            return self._general(out, cases, history, asker, preferences, recheck, base)
        if not out.candidates or out.confidence == "low":
            return self._fallback(out, cases, min_sim, history, asker, preferences, base)

        context = AnswerContext(knowledge=order_by_priority(out.candidates, self.settings.priority_tiers),
                                sales_cases=cases, history=list(history),
                                asker=asker or {}, preferences=preferences or {})
        answer = self.generator.generate_answer(context, out.query.original)
        if NO_APPROVED_ANSWER in answer:              # the passages do not answer it: past chats / careful guidance / exact reply
            return self._fallback(out, cases, min_sim, history, asker, preferences, base)
        if recheck is not None:
            used = {c.version_id for c in context.knowledge}
            allowed = recheck(used)
            if not allowed:                           # everything it used was unpublished or became off-limits meanwhile
                return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=NOT_FOUND_ACTIONS, **base)
            if len(allowed) < len(used):              # answer again from what is still allowed only
                context.knowledge = [c for c in context.knowledge if c.version_id in allowed]
                answer = self.generator.generate_answer(context, out.query.original)
                if NO_APPROVED_ANSWER in answer:
                    return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=NOT_FOUND_ACTIONS, **base)
        hist = ({"similar": len(cases), "successful": sum(c.outcome == SUCCESSFUL_OUTCOME for c in cases)}
                if cases else None)
        seen, sources = set(), []
        for c in context.knowledge:
            key = (c.version_id, c.section)
            if key not in seen:
                seen.add(key)
                sources.append(source_of(c))
        return AskResult(answer=answer, found=True, sources=sources, historical_cases=hist, **base)

    def _general(self, out, cases, history, asker, preferences, recheck, base) -> AskResult:
        """General assistant: always answers. Permitted, published knowledge (filters applied before retrieval, §8/§10) and similar
        past chats are passed as context; weak matches are left out so they cannot mislead. A missing company fact is a gap (§9)."""
        knowledge = order_by_priority(out.candidates, self.settings.priority_tiers) if out.candidates and out.confidence != "low" else []
        if knowledge and recheck is not None:
            allowed = recheck({c.version_id for c in knowledge})
            knowledge = [c for c in knowledge if c.version_id in allowed]
        context = AnswerContext(knowledge=knowledge, sales_cases=cases, history=list(history), asker=asker or {},
                                preferences=preferences or {}, general_mode=True,
                                user_language=getattr(out.query, "language", "") or "")
        text = self.generator.generate_answer(context, out.query.original).strip()
        if _invented_money(text, knowledge):                 # PRD §1: never invent prices/discounts -> one strict retry
            text = self.generator.generate_answer(context, out.query.original + STRICT_RETRY_NOTE).strip()
            if _invented_money(text, knowledge):
                text = f"{SAFE_MISSING}\n{MISSING_COMPANY_INFO}"
        if text.startswith(OFF_TOPIC) or text.strip(" .") == OFF_TOPIC:
            return AskResult(answer=OFF_TOPIC_TEXT, found=True, confidence="general", confidence_score=out.confidence_score,
                             query=out.query, retrieved=out.candidates)
        text = re.sub(r"(?im)^\s*(?:line|step)\s*\d+\s*[:.)-]\s*", "", text)
        text = _drop_term_offers(text, knowledge)            # payment plans, discounts ... only when knowledge allows   # format labels are not for the reader
        missing = MISSING_COMPANY_INFO in text
        text = "\n".join(l for l in text.replace(MISSING_COMPANY_INFO, "").splitlines()).strip()
        for marker in (NO_APPROVED_ANSWER, NO_RELEVANT_HISTORY, GENERAL_GUIDANCE, OFF_TOPIC):
            text = text.replace(marker, "").strip()
        if not text:
            return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=NOT_FOUND_ACTIONS, **base)
        seen, sources = set(), []
        for c in knowledge:
            key = (c.version_id, c.section)
            if key not in seen:
                seen.add(key)
                sources.append(source_of(c))
        hist = ({"similar": len(cases), "successful": sum(c.outcome == SUCCESSFUL_OUTCOME for c in cases)} if cases else None)
        return AskResult(answer=text, found=not missing, actions=NOT_FOUND_ACTIONS if missing else [],
                         confidence=out.confidence if knowledge else "general", confidence_score=out.confidence_score,
                         query=out.query, retrieved=out.candidates, sources=sources, historical_cases=hist)

    def _fallback(self, out, cases, min_sim, history, asker, preferences, base) -> AskResult:
        if cases and min_sim is not None:                                         # owner request: history-only answer
            res = self._history_only(out, cases, history, asker, preferences)
            if res is not None:
                return res
        if getattr(self.settings, "general_guidance", False):                    # owner 2026-10-21: careful reply advice
            res = self._guidance_only(out, history, asker, preferences)
            if res is not None:
                return res
        # PRD §6 FR-CHAT-04: no verified answer -> the exact sentence, offer Report missing information
        return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=NOT_FOUND_ACTIONS, **base)

    def _guidance_only(self, out, history, asker, preferences) -> Optional[AskResult]:
        """Only for "what should I reply to the client?" questions (the model decides; anything else -> None). The text must
        start with GENERAL_GUIDANCE and contain no price, amount, percentage or time promise, else it is discarded (§1)."""
        context = AnswerContext(knowledge=[], sales_cases=[], history=list(history), asker=asker or {},
                                preferences=preferences or {}, guidance_only=True)
        text = self.generator.generate_answer(context, out.query.original).strip()
        if not text.startswith(GENERAL_GUIDANCE) or NO_APPROVED_ANSWER in text:
            return None
        body = text[len(GENERAL_GUIDANCE):].strip(" :\n")
        if not body or _FORBIDDEN_IN_GUIDANCE.search(body) or _OFFERS.search(body):
            return None
        return AskResult(answer=f"{GENERAL_GUIDANCE_LABEL}\n\n{body}", found=False, actions=NOT_FOUND_ACTIONS,
                         confidence="low", confidence_score=out.confidence_score, query=out.query, retrieved=out.candidates)

    def _history_only(self, out, cases, history, asker, preferences) -> Optional[AskResult]:
        """No approved knowledge matched: answer from similar past sales chats only, labelled as such. Still counted as a
        knowledge gap (found=False) so administrators see that a policy/SOP is missing (§35). Confidence comes from how close
        the past chats are, on the same vector thresholds as knowledge (§31). None when the answer model finds them off topic."""
        context = AnswerContext(knowledge=[], sales_cases=cases, history=list(history),
                                asker=asker or {}, preferences=preferences or {})
        text = self.generator.generate_answer(context, out.query.original)
        if NO_RELEVANT_HISTORY in text or NO_APPROVED_ANSWER in text:   # not about this question -> next fallback
            return None
        if _FORBIDDEN_IN_GUIDANCE.search(text) or _OFFERS.search(text):  # past chats never authorise prices/discounts/refunds (§1)
            return None
        answer = f"{HISTORY_ONLY_LABEL}\n\n{text}"
        top = max(c.similarity for c in cases)
        s = self.settings
        hist = {"similar": len(cases), "successful": sum(c.outcome == SUCCESSFUL_OUTCOME for c in cases)}
        return AskResult(answer=answer, found=False, historical_cases=hist, confidence_score=top,
                         confidence=confidence_label(top, s.confidence_vector_high, s.confidence_vector_medium),
                         query=out.query, retrieved=out.candidates)
