"""DeepSeek (PRD §8, §11 default answer LLM), OpenAI, Gemini and Claude providers.
All receive the same PRD-derived system prompt and the same fenced context (see prompt.py).

Every provider offers `generate_answer(context, question)` (PRD §28) and, as an optional extra, `interpret_query(question, history)`:
a tiny call that restates an Urdu / Roman Urdu / mixed question as an English search query (PRD §23 "semantic interpretation")."""
from __future__ import annotations

import re

from ..models import AnswerContext
from .prompt import (INTERPRET_PROMPT, SYSTEM_PROMPT, system_prompt_for, TRANSLATE_PROMPT, build_interpret_input, build_translate_input,
                     build_user_prompt)


class _Interprets:
    """Shared `interpret_query` built on each provider's `_complete(system, user, max_tokens)`."""
    _translate_kwargs: dict = {}                     # extra `_complete` arguments for translation (OpenAI reasoning models)

    def interpret_query(self, question: str, history=()) -> str:
        text = self._complete(INTERPRET_PROMPT, build_interpret_input(question, history), 80)
        return " ".join(text.split()).strip(" \"'`")[:300]

    def translate_for_client(self, text: str, target: str = "English", slang: bool = False) -> str:
        """Owner-approved addition (docs/PRD_GAPS.md §0): any language -> the selected target language, client-ready."""
        return self._complete(TRANSLATE_PROMPT, build_translate_input(text, target, slang), 2000,
                              **self._translate_kwargs).strip().strip('"')


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
            config=types.GenerateContentConfig(system_instruction=system_prompt_for(context)))
        return (r.text or "").strip()


def _reasoning_model(model: str) -> bool:
    """OpenAI reasoning models (gpt-5 family, o-series) think before answering; their thinking counts against the token budget."""
    m = model.lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


_WANTS_DETAIL = re.compile(r"\b(detail\w*|step[- ]by[- ]step|explain|in depth|thorough\w*|elaborate|full (?:guide|answer|"
                           r"explanation|list)|long|comprehensive|tafseel|tafsil|poori? (?:detail|tafseel))\b", re.I)


def _verbosity(context: AnswerContext, question: str) -> str:
    """Owner 2026-10-24 'length follows the request'. MEASURED live: with the 'balanced' style, gpt-5-mini answered 'what colour
    works best for a gaming logo?' in 342 words despite the prompt; the GPT-5 verbosity setting is the reliable lever."""
    prefs = context.preferences or {}
    if prefs.get("discord_slang"):                      # Discord Slang Mode: short messages
        return "low"
    style = prefs.get("answer_style")
    if _WANTS_DETAIL.search(question or "") or style == "detailed":
        return "high"
    return "low"


class OpenAIGenerator(_Interprets):
    def __init__(self, model: str, reasoning_effort: str | None = None) -> None:
        from openai import OpenAI
        self._model, self._client = model, OpenAI()                 # reads OPENAI_API_KEY
        self._effort = reasoning_effort
        # Translation needs the style rules followed (measured 2026-10-20: "minimal" kept "bhai" -> "brother" and invented "Sir").
        self._translate_kwargs = {"effort": "low"} if _reasoning_model(model) else {}

    def _complete(self, system: str, user: str, max_tokens: int, effort: str = "minimal") -> str:
        # Short internal tasks (restating a question): with a reasoning model the thinking would use up the small budget and
        # return nothing (measured with gpt-5-nano), so they think minimally.
        extra = {"reasoning_effort": effort} if _reasoning_model(self._model) else {}
        r = self._client.chat.completions.create(
            model=self._model, max_completion_tokens=max_tokens, **extra,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return (r.choices[0].message.content or "").strip()

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        extra = {"reasoning_effort": self._effort} if self._effort and _reasoning_model(self._model) else {}
        if self._model.startswith("gpt-5"):
            extra["verbosity"] = _verbosity(context, question)
        user = build_user_prompt(context, question)
        if context.images:                                     # owner 2026-10-24: pasted images go with the question
            user = [{"type": "text", "text": user}, *({"type": "image_url", "image_url": {"url": u}} for u in context.images)]
        r = self._client.chat.completions.create(
            model=self._model, **extra,
            messages=[{"role": "system", "content": system_prompt_for(context)}, {"role": "user", "content": user}])
        return (r.choices[0].message.content or "").strip()

    def generate_image(self, model: str, prompt: str, quality: str, size: str, references: list[bytes]) -> bytes:
        """Owner 2026-10-24: create an image (PNG bytes). With reference images the model edits / builds on them."""
        import base64
        import io
        if references:
            files = [("reference.png", io.BytesIO(b), "image/png") for b in references]
            r = self._client.images.edit(model=model, image=files, prompt=prompt, size=size, quality=quality, n=1)
        else:
            r = self._client.images.generate(model=model, prompt=prompt, size=size, quality=quality, n=1)
        return base64.b64decode(r.data[0].b64_json)


    def generate_web_answer(self, context: AnswerContext, question: str) -> tuple[str, list[dict]]:
        """Owner 2026-10-24 Web Search: OpenAI Responses API with the built-in web_search tool. Returns (text, [{title, url}])."""
        text_in = build_user_prompt(context, question)
        web_input = text_in if not context.images else [{"role": "user", "content": [
            {"type": "input_text", "text": text_in}, *({"type": "input_image", "image_url": u} for u in context.images)]}]
        r = self._client.responses.create(
            model=self._model, tools=[{"type": "web_search"}], instructions=system_prompt_for(context),
            input=web_input,
            **({"reasoning": {"effort": "low"}} if _reasoning_model(self._model) else {}),
            **({"text": {"verbosity": _verbosity(context, question)}} if self._model.startswith("gpt-5") else {}))
        sources, seen = [], set()
        for item in r.output or []:
            for part in getattr(item, "content", None) or []:
                for a in getattr(part, "annotations", None) or []:
                    url = (getattr(a, "url", "") or "").replace("?utm_source=openai", "").replace("&utm_source=openai", "")
                    if getattr(a, "type", "") == "url_citation" and url.startswith(("https://", "http://")) and url not in seen:
                        seen.add(url)
                        sources.append({"title": (getattr(a, "title", "") or url)[:120], "url": url})
        text = re.sub(r"\s*\(\[[^\]]+\]\([^)]+\)\)", "", r.output_text or "").strip()   # inline "([site](url))" -> chips below
        return text, sources[:6]


class DeepSeekGenerator(OpenAIGenerator):
    """PRD §8, §11: DeepSeek as the configurable answer LLM. DeepSeek serves an OpenAI-compatible API, so this reuses the
    OpenAI client pointed at DeepSeek's endpoint (implementation necessity, docs/PRD_GAPS.md). Key: DEEPSEEK_API_KEY."""
    BASE_URL = "https://api.deepseek.com"

    def __init__(self, model: str) -> None:
        import os
        from openai import OpenAI
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is not set")
        self._model, self._client = model, OpenAI(api_key=key, base_url=self.BASE_URL)

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        r = self._client.chat.completions.create(                  # DeepSeek takes `max_tokens`, not `max_completion_tokens`
            model=self._model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
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
            model=self._model, max_tokens=self._max, system=system_prompt_for(context),
            messages=[{"role": "user", "content": build_user_prompt(context, question)}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
