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


LABELS = {"twitch_emote": "Twitch emote", "twitch_badge": "Twitch sub badge", "discord_emote": "Discord emote", "sticker": "sticker",
          "logo": "logo", "twitch_banner": "Twitch profile banner", "twitch_offline": "Twitch offline screen",
          "stream_screen": "stream screen", "youtube_banner": "YouTube banner", "youtube_thumbnail": "YouTube thumbnail"}
FAN_ART_NOTE = ("This is fan art of an existing character: use it for internal reference only, not for client or commercial "
                "delivery. I can make an original character in the same style instead.")
# Words the user wants in the picture, when the art director left "text" empty: "called NightOwl", "with the text FOXX", "..."
_NAMED = re.compile(r"[\"“]([^\"”]{1,40})[\"”]|\b(?:called|named|text|saying|says)\s+([A-Z0-9][\w'-]{0,29})")
KEEP_IN_FRAME = (" IMPORTANT: the whole subject must be completely inside the frame with wide empty margin on every side; "
                 "nothing may touch or be cut off by the image edges.")


def _url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _caption(asset: str, info: dict, files: list, fan_art: bool, language: str) -> str:
    """QA 2026-10-25: the reply states only what was really delivered (measured size and transparency), in the user's language."""
    dims = f"{info['width']}×{info['height']}" + (", transparent background" if info["transparent"] else "")
    what = LABELS.get(asset, "image")
    if language in ("roman_urdu", "mixed"):
        text = f"Yeh rahi aap ki {what} ({dims})."
        if files:
            text += " Download sizes: " + ", ".join(n.replace("x", "×") for n, _ in files) + "."
    elif language == "urdu":
        text = f"یہ رہی آپ کی تصویر ({dims})."
        if files:
            text += " ڈاؤن لوڈ سائز: " + "، ".join(n.replace("x", "×") for n, _ in files)
    else:
        text = f"Here's your {what} ({dims})."
        if files:
            text += " Download sizes: " + ", ".join(n.replace("x", "×") for n, _ in files) + "."
    return text + ("\n" + FAN_ART_NOTE if fan_art else "")


def make_image(svc, request: str, references: list[str], size: str = "auto", final: bool = False, language: str = "") -> dict:
    """Art director (expand + canvas + background + asset type), then the image model, then the checks and delivery files an art
    director would make (QA 2026-10-25). Shared by /v1/images and image requests in chat."""
    from ...generation import image_post
    s = svc.settings
    if not s.image_model:
        raise HTTPException(403, "Image creation is not enabled on this server.")
    refs = [base64.b64decode(_DATA_URL.match(u).group(2)) for u in references]
    gen = svc.ask.generator
    plan = gen.direct_image(request, bool(refs))
    named = _NAMED.search(request)
    text = plan.get("text") or (next(g for g in named.groups() if g) if named else "")
    if text and f'"{text}"' not in plan["prompt"]:       # QA 2026-10-25: banner said "USERNAME" instead of the name asked for
        plan["prompt"] += (f' The image must show the text "{text}" with exactly this spelling and capitalisation, as solid opaque '
                           f'lettering with a contrasting outline; no other words.')
    use_size, background = plan["size"], plan["background"]
    if plan.get("edit") and refs:                        # an edit keeps the source's framing and background
        use_size = image_post.size_like(refs[0])
        background = "transparent" if image_post.inspect(refs[0])["transparent"] else "opaque"
    if size in SIZES and size != "auto":
        use_size = size
    quality = "high" if final else s.image_quality
    try:
        png = gen.generate_image(s.image_model, plan["prompt"], quality, use_size, refs, background)
        info = image_post.inspect(png)
        if info["touches_edge"] and not plan.get("edit"):    # QA G4: a sticker cut off at the frame cannot be die-cut
            png = gen.generate_image(s.image_model, plan["prompt"] + KEEP_IN_FRAME, quality, use_size, refs, background)
            info = image_post.inspect(png)
            if info["touches_edge"]:
                png = image_post.pad(png)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
    asset = plan.get("asset", "other")
    files = []
    if asset in image_post.EXACT and not plan.get("edit"):   # QA G3: deliver the platform's exact size
        png = image_post.fit_exact(png, *image_post.EXACT[asset])
    elif asset in image_post.PACKS:                          # QA G2: emote / badge pack in the platform sizes
        files = image_post.pack(png, image_post.PACKS[asset])
    info = image_post.inspect(png)
    return {"image": _url(png), "prompt": plan["prompt"], "size": f"{info['width']}x{info['height']}",
            "background": "transparent" if info["transparent"] else "opaque", "asset": asset, "fan_art": plan.get("fan_art", False),
            "files": [{"name": n, "image": _url(b)} for n, b in files], "quality": quality,
            "caption": _caption(asset, info, files, plan.get("fan_art", False), language)}


class ImageIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    size: str = "auto"                       # auto = the art director chooses
    references: list[str] = Field(default_factory=list, max_length=4)
    final: bool = False                      # QA 2026-10-25: "Final quality" = quality "high" (cleaner text and lines, slower)

    @field_validator("references")
    @classmethod
    def _refs(cls, v: list[str]) -> list[str]:
        return [check_data_url(u) for u in v]


@router.post("/images")
def create_image(body: ImageIn, p: Principal = Depends(require(P.ASK)), svc: Services = Depends(get_services)):
    if body.size not in SIZES:
        raise HTTPException(422, f"size must be one of {', '.join(SIZES)}")
    language = svc.search.language.detect(body.prompt) if hasattr(svc.search, "language") else ""
    out = make_image(svc, body.prompt.strip(), body.references, body.size, body.final, language)
    audit.record(svc.ops, audit.IMAGE_GENERATION, p.user_id, p.employee_id, chars=len(body.prompt), references=len(body.references),
                 final=body.final)
    return out
