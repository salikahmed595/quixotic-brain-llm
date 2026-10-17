"""LLM generation layer — PRD §28. The rest of the system calls only `generate_answer(context, question)`."""
from __future__ import annotations

from typing import Protocol

from ..config import Settings
from ..models import AnswerContext


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
        return self._inner.generate_answer(context, question)

    def interpret_query(self, question: str, history=()) -> str:
        """Optional English restatement of an Urdu / Roman Urdu question. Any failure just means 'no interpretation'."""
        try:
            if self._inner is None:
                self._inner = self._factory()
            fn = getattr(self._inner, "interpret_query", None)
            return fn(question, history) if fn else ""
        except Exception:
            return ""


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
        return OpenAIGenerator(model)
    if p == "claude":
        from .providers import ClaudeGenerator
        if not settings.generation_max_tokens:
            raise ValueError("QB_GENERATION_MAX_TOKENS is required for provider 'claude' (the API demands a limit)")
        return ClaudeGenerator(model, settings.generation_max_tokens)
    if p == "bedrock":                                  # "Bedrock model later"
        from .bedrock import BedrockGenerator
        return BedrockGenerator(model, settings.aws_region)
    raise NotImplementedError(f"generation provider {p!r}: choose one of {', '.join(PROVIDERS)}")
