"""Images — owner-approved additions 2026-10-24 (not in the PRD; docs/PRD_GAPS.md §0).

- Pasted images in chat questions: validated here (type and size), sent to the answer model with the question, never stored.
- POST /v1/images: create an image from a prompt (optionally building on reference images) with the configured OpenAI image
  model. The image is returned to the browser and not stored; only an audit entry with the prompt length is kept."""
from __future__ import annotations

import base64
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ...analytics import audit
from ...permissions.access import Principal
from ...permissions.roles import P
from ..deps import get_services, require
from ..services import Services

router = APIRouter(prefix="/v1", tags=["images"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024           # implementation limits (docs/PRD_GAPS.md): per pasted image
_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=]+)$")
SIZES = ("1024x1024", "1536x1024", "1024x1536", "auto")


def check_data_url(url: str) -> str:
    m = _DATA_URL.match(url or "")
    if not m:
        raise ValueError("images must be PNG, JPEG, WEBP or GIF")
    if len(m.group(2)) * 3 // 4 > MAX_IMAGE_BYTES:
        raise ValueError("each image must be 8 MB or smaller")
    return url


class ImageIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    size: str = "1024x1024"
    references: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("references")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return [check_data_url(u) for u in v]


@router.post("/images")
def create_image(body: ImageIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    s = svc.settings
    if not s.image_model:
        raise HTTPException(403, "Image creation is not enabled on this server.")
    if body.size not in SIZES:
        raise HTTPException(422, f"size must be one of {', '.join(SIZES)}")
    refs = [base64.b64decode(_DATA_URL.match(u).group(2)) for u in body.references]
    try:
        png = svc.ask.generator.generate_image(s.image_model, body.prompt.strip(), s.image_quality, body.size, refs)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
    audit.record(svc.ops, audit.IMAGE_GENERATION, p.user_id, p.employee_id, chars=len(body.prompt), references=len(refs))
    return {"image": "data:image/png;base64," + base64.b64encode(png).decode(), "prompt": body.prompt.strip()}
