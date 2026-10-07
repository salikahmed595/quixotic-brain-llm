"""Gemini, OpenAI and Claude providers (stack decision: "Gemini/OpenAI/Claude initially").
All receive the same PRD-derived system prompt and the same fenced context (see prompt.py).

Every provider offers `generate_answer(context, question)` (PRD §28) and, as an optional extra, `interpret_query(question, history)`:
a tiny call that restates an Urdu / Roman Urdu / mixed question as an English search query (PRD §23 "semantic interpretation")."""
from __future__ import annotations

from ..models import AnswerContext
from .prompt import INTERPRET_PROMPT, SYSTEM_PROMPT, build_interpret_input, build_user_prompt


class _Interprets:
    """Shared `interpret_query` built on each provider's `_complete(system, user, max_tokens)`."""

    def interpret_query(self, question: str, history=()) -> str:
        text = self._complete(INTERPRET_PROMPT, build_interpret_input(question, history), 80)
        return " ".join(text.split()).strip(" \"'`")[:300]


class GeminiGenerator(_Interprets):
    def __init__(self, model: str) -> None:
        from google import genai
        self._model, self._client = model, genai.Client()          # reads GEMINI_API_KEY / GOOGLE_API_KEY

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        from google.genai import types
        r = self._client.models.generate_content(model=self._model, contents=user,
                                                 config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens))
        return (r.text or "").strip()

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        from google.genai import types
        r = self._client.models.generate_content(
            model=self._model, contents=build_user_prompt(context, question),
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT))
        return (r.text or "").strip()


class OpenAIGenerator(_Interprets):
    def __init__(self, model: str) -> None:
        from openai import OpenAI
        self._model, self._client = model, OpenAI()                 # reads OPENAI_API_KEY

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        r = self._client.chat.completions.create(
            model=self._model, max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (r.choices[0].message.content or "").strip()

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        r = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_user_prompt(context, question)}])
        return (r.choices[0].message.content or "").strip()


class ClaudeGenerator(_Interprets):
    def __init__(self, model: str, max_tokens: int) -> None:
        import anthropic
        self._model, self._max, self._client = model, max_tokens, anthropic.Anthropic()   # reads ANTHROPIC_API_KEY

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        r = self._client.messages.create(model=self._model, max_tokens=max_tokens, system=system,
                                         messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        r = self._client.messages.create(
            model=self._model, max_tokens=self._max, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(context, question)}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
