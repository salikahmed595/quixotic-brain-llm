"""AWS Bedrock provider (PRD §28, §44) using the Converse API."""
from __future__ import annotations

from typing import Optional

from ..models import AnswerContext
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .providers import _Interprets


class BedrockGenerator(_Interprets):
    def __init__(self, model_id: str, region: Optional[str] = None) -> None:
        import boto3
        self._model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def _converse(self, system: str, user: str, **extra) -> str:
        resp = self._client.converse(modelId=self._model_id, system=[{"text": system}],
                                     messages=[{"role": "user", "content": [{"text": user}]}], **extra)
        return "".join(b.get("text", "") for b in resp["output"]["message"]["content"]).strip()

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        return self._converse(system, user, inferenceConfig={"maxTokens": max_tokens})

    def generate_answer(self, context: AnswerContext, question: str) -> str:
        return self._converse(SYSTEM_PROMPT, build_user_prompt(context, question))
