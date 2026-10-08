"""Sales memory record — field names and example values follow PRD §16.2 exactly."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SalesMemoryRecord(BaseModel):
    conversation_id: Optional[str] = None
    channel: Optional[str] = None            # e.g. "discord"
    scenario: Optional[str] = None           # e.g. "price objection"
    customer_intent: Optional[str] = None    # e.g. "interested_but_expensive"
    customer_message: Optional[str] = None
    agent_response: Optional[str] = None
    sales_stage: Optional[str] = None        # e.g. "negotiation"
    product: Optional[str] = None            # e.g. "custom_artwork"
    outcome: Optional[str] = None            # e.g. "closed"
    sale_value: Optional[float] = None
    discount_given: Optional[float] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    quality_score: Optional[float] = None    # "quality signals" are not defined in the PRD -> may be None
    customer_objection: Optional[str] = None # PRD §17.2 "Extract Objection" (not in the §16.2 example; stored when given)

    def embedding_text(self) -> str:
        """Text that is embedded. PRD §17.2 says 'Generate Embeddings' without naming the text;
        the customer's message is used so similar customer situations are found (docs/PRD_GAPS.md)."""
        return (self.customer_message or self.scenario or "").strip()
