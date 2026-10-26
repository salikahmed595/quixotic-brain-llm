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

    def generate_web_answer(self, context: AnswerContext, question: str) -> tuple[str, list[dict]]:
        """Owner 2026-10-24 Web Search. Only providers with a web search tool support it (OpenAI)."""
        if self._inner is None:
            try:
                self._inner = self._factory()
            except Exception as exc:
                raise RuntimeError(f"The answer model is not configured: {exc}") from exc
        fn = getattr(self._inner, "generate_web_answer", None)
        if fn is None:
            raise RuntimeError("Web Search needs the OpenAI answer model.")
        try:
            return fn(context, question)
        except Exception as exc:
            log.exception("web search answer failed")
            raise RuntimeError("Web Search is not available right now. Please try again.") from exc

    def classify_task(self, question: str, history=(), has_images: bool = False):
        """Owner 2026-10-26 task routing. Any failure means 'no routing' (None): the general rules then apply as before."""
        try:
            if self._inner is None:
                self._inner = self._factory()
            fn = getattr(self._inner, "classify_task", None)
            return fn(question, history, has_images) if fn else None
        except Exception:
            log.exception("task classification failed; answering without routing")
            return None

    def direct_image(self, request: str, has_references: bool = False, concept: str = "") -> dict:
        """Owner 2026-10-25 art-director step; any failure falls back to the user's own words."""
        try:
            if self._inner is None:
                self._inner = self._factory()
            fn = getattr(self._inner, "direct_image", None)
            if fn is None:
                return {"prompt": request, "size": "1024x1024", "background": "opaque"}
            return fn(request, has_references, concept) if concept else fn(request, has_references)
        except Exception:
            log.exception("art-director step failed; using the request as it is")
            return {"prompt": request, "size": "1024x1024", "background": "opaque"}

    def generate_image(self, model: str, prompt: str, quality: str, size: str, references: list[bytes],
                       background: str = "auto") -> bytes:
        """Owner 2026-10-24 image creation (OpenAI image models)."""
        if self._inner is None:
            try:
                self._inner = self._factory()
            except Exception as exc:
                raise RuntimeError(f"The answer model is not configured: {exc}") from exc
        fn = getattr(self._inner, "generate_image", None)
        if fn is None:
            raise RuntimeError("Image creation needs the OpenAI provider.")
        try:
            return fn(model, prompt, quality, size, references, background)
        except Exception as exc:
            log.exception("image generation failed")
            msg = str(exc)
            if "safety" in msg.lower() or "moderation" in msg.lower():
                raise RuntimeError("That image request was blocked by the safety filter. Please rephrase it.") from exc
            raise RuntimeError("Image creation is not available right now. Please try again.") from exc

    def translate_for_client(self, text: str, target: str = "English", slang: bool = False) -> str:
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
            return fn(text, target, slang) if slang else fn(text, target)
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
