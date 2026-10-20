"""LLM generation layer — PRD §28. The rest of the system calls only `generate_answer(context, question)`."""
from __future__ import annotations

import logging
from typing import Protocol

from ..config import Settings
from ..models import AnswerContext

log = logging.getLogger(__name__)


class GenerationProvider(Protocol):
    def generate_answer(self, context: AnswerContext, question: str) -> str: ...


class LazyGenerator:
    """Builds the real provider on first use, so the app (login, knowledge, admin pages) starts before an API key exists.
    A missing key then surfaces as a clear error on the first question instead of a crash at start-up."""

    def __init__(self, factory) -> None:
        self._factory, self._inner = factory, None

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        if self._inner is None:
            try:
                self._inner = self._factory()
            except Exception as exc:
                raise RuntimeError(f"The answer model is not configured: {exc}") from exc
        try:
            return self._inner.generate_answer(context, question)
        except Exception as exc:
            # PRD §6 FR-CHAT-07 "unavailable service": a provider outage or a rejected key becomes a clear 503, never a 500.
            # The provider's own message stays in the server log only (it can name the key or account).
            log.exception("answer model call failed")
            raise RuntimeError("The answer service is unavailable right now. Please try again in a moment.") from exc

    def interpret_query(self, question: str, history=()) -> str:
        """Optional English restatement of an Urdu / Roman Urdu question. Any failure just means 'no interpretation'."""
        try:
            if self._inner is None:
                self._inner = self._factory()
            fn = getattr(self._inner, "interpret_query", None)
            return fn(question, history) if fn else ""
        except Exception:
            return ""

    def translate_for_client(self, text: str) -> str:
        """Owner-approved addition (docs/PRD_GAPS.md §0). Errors become a clear message; provider details stay in the log."""
        if self._inner is None:
            try:
                self._inner = self._factory()
            except Exception as exc:
                raise RuntimeError(f"The answer model is not configured: {exc}") from exc
        fn = getattr(self._inner, "translate_for_client", None)
        if fn is None:
            raise RuntimeError("The configured answer model does not support translation.")
        try:
            return fn(text)
        except Exception as exc:
            log.exception("translation call failed")
            raise RuntimeError("Translation is not available right now. Please try again.") from exc


# PRD §8, §11: DeepSeek is the default answer LLM, configurable. Owner (2026-10-17): OpenAI until the DeepSeek key is added.
PROVIDERS = ("deepseek", "openai", "gemini", "claude", "bedrock")


def get_generator(settings: Settings) -> GenerationProvider:
    p = settings.generation_provider
    if p not in PROVIDERS:
        raise NotImplementedError(f"generation provider {p!r}: choose one of {', '.join(PROVIDERS)}")
    return LazyGenerator(lambda: _build_generator(settings))


def _build_generator(settings: Settings) -> GenerationProvider:
    """Stack decision: Gemini / OpenAI / Claude initially, a Bedrock model later. The model id is required
    (nothing names one); API keys come from the provider SDKs' standard environment variables
    (DEEPSEEK_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY), injected on the server from AWS Secrets Manager (PRD §10)."""
    p, model = settings.generation_provider, settings.generation_model_id
    if not model:
        raise ValueError("QB_GENERATION_MODEL_ID is required (no model is named by the PRD or the stack)")
    if p == "gemini":
        from .providers import GeminiGenerator
        return GeminiGenerator(model)
    if p == "deepseek":
        from .providers import DeepSeekGenerator
        return DeepSeekGenerator(model)
    if p == "openai":
        from .providers import OpenAIGenerator
        return OpenAIGenerator(model, settings.generation_reasoning_effort)
    if p == "claude":
        from .providers import ClaudeGenerator
        if not settings.generation_max_tokens:
            raise ValueError("QB_GENERATION_MAX_TOKENS is required for provider 'claude' (the API demands a limit)")
        return ClaudeGenerator(model, settings.generation_max_tokens)
    if p == "bedrock":                                  # "Bedrock model later"
        from .bedrock import BedrockGenerator
        return BedrockGenerator(model, settings.aws_region)
    raise NotImplementedError(f"generation provider {p!r}: choose one of {', '.join(PROVIDERS)}")
