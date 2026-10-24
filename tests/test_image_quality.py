"""QA 2026-10-25 image audit: delivery sizes, edge checks, edits, honest captions, follow-ups and unbacked claims."""
import base64
import io
from types import SimpleNamespace

from PIL import Image

from backend.api.v1.images import FAN_ART_NOTE, make_image
from backend.generation import image_post
from backend.generation.prompt import GENERAL_SYSTEM_PROMPT, IMAGE_DIRECTOR_PROMPT, build_user_prompt
from backend.models import AnswerContext
from backend.retrieval.ask import AskService
from tests.fakes import FakeStore
from tests.test_retrieval import DEPT, LV, _Says, build


def _png(size=(1024, 1024), box=None, mode="RGBA") -> bytes:
    """A transparent canvas with an opaque rectangle `box`, or a fully opaque image when box is None."""
    im = Image.new(mode, size, (0, 0, 0, 0) if box else (200, 80, 20, 255))
    if box:
        im.paste((255, 120, 0, 255), box)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def test_edge_check_finds_artwork_cut_off_at_the_frame_and_padding_fixes_it():
    cut = _png(box=(100, 0, 900, 1024))                         # touches top and bottom (QA G4 sticker)
    assert image_post.inspect(cut)["touches_edge"]
    padded = image_post.pad(cut)
    assert not image_post.inspect(padded)["touches_edge"] and image_post.inspect(padded)["transparent"]
    assert not image_post.inspect(_png(box=(200, 200, 800, 800)))["touches_edge"]


def test_banner_is_delivered_at_the_platforms_exact_size():
    out = image_post.fit_exact(_png((1536, 1024)), 1200, 480)   # QA G3: was 1536x1024 while claiming 1200x480
    assert Image.open(io.BytesIO(out)).size == (1200, 480)


def test_emote_pack_has_the_twitch_sizes():
    names = [n for n, _ in image_post.pack(_png(box=(200, 200, 800, 800)), image_post.PACKS["twitch_emote"])]
    assert names == ["112x112", "56x56", "28x28"]


class _Gen:
    def __init__(self, plan, pngs):
        self.plan, self.pngs, self.calls = plan, list(pngs), []

    def direct_image(self, request, has_references=False):
        return dict(self.plan)

    def generate_image(self, model, prompt, quality, size, refs, background):
        self.calls.append({"prompt": prompt, "quality": quality, "size": size, "background": background, "refs": len(refs)})
        return self.pngs.pop(0)


def _svc(gen):
    return SimpleNamespace(settings=SimpleNamespace(image_model="gpt-image-1-mini", image_quality="medium"),
                           ask=SimpleNamespace(generator=gen))


PLAN = {"prompt": "p", "size": "1024x1024", "background": "transparent", "asset": "twitch_emote", "edit": False,
        "fan_art": False, "text": ""}


def test_caption_states_only_what_was_delivered_and_emote_sizes_are_real_files():
    out = make_image(_svc(_Gen(PLAN, [_png(box=(200, 200, 800, 800))])), "chibi cat emote", [])
    assert [f["name"] for f in out["files"]] == ["112x112", "56x56", "28x28"]
    assert out["caption"].startswith("Here's your Twitch emote (1024×1024, transparent background).")
    assert "p" != out["caption"] and out["quality"] == "medium"


def test_cut_off_sticker_is_redrawn_once_then_padded():
    gen = _Gen(PLAN | {"asset": "sticker"}, [_png(box=(0, 0, 1024, 900)), _png(box=(0, 0, 1024, 900))])
    out = make_image(_svc(gen), "naruto chibi sticker", [])
    assert len(gen.calls) == 2 and "completely inside the frame" in gen.calls[1]["prompt"]
    png = base64.b64decode(out["image"].split(",", 1)[1])
    assert not image_post.inspect(png)["touches_edge"]


def test_edit_keeps_the_source_framing_and_background():
    gen = _Gen(PLAN | {"edit": True, "asset": "other", "size": "1024x1024", "background": "transparent"}, [_png((1536, 1024))])
    make_image(_svc(gen), "add a red scarf", [_url(_png((1536, 1024)))])
    assert gen.calls[0]["size"] == "1536x1024" and gen.calls[0]["background"] == "opaque" and gen.calls[0]["refs"] == 1


def test_final_quality_fan_art_note_and_roman_urdu_caption():
    gen = _Gen(PLAN | {"asset": "illustration", "fan_art": True, "background": "opaque"}, [_png()])
    out = make_image(_svc(gen), "naruto", [], final=True, language="roman_urdu")
    assert gen.calls[0]["quality"] == "high" and out["caption"].startswith("Yeh rahi aap ki image") and FAN_ART_NOTE in out["caption"]


def test_director_rules_cover_edits_opaque_lettering_and_safe_areas():
    flat = " ".join(IMAGE_DIRECTOR_PROMPT.split())
    assert "Change only:" in flat and "never cut-out, knocked-out" in flat and "central safe area" in flat
    assert "exactly this spelling and capitalisation" in flat and '"fan_art": true' in flat


def test_unbacked_worked_in_past_chats_claim_is_removed():
    _, search, _ = build(FakeStore(vec=[]))
    object.__setattr__(search.settings, "general_assistant", True)
    reply = "**Option 1 - Direct**\n>> Sure, orange works!\nWhy: quick and clear (worked in past chats)"
    r = AskService(search, _Says(reply), search.settings).ask("what should I reply?", DEPT, levels=LV)
    assert "past chats" not in r.answer and r.answer.endswith("quick and clear")


def test_follow_up_marks_images_as_shared_earlier():
    _, search, _ = build(FakeStore(vec=[]))
    object.__setattr__(search.settings, "general_assistant", True)
    gen = _Says("The second line says 'Bitte bestätigen'.")
    AskService(search, gen, search.settings).ask("and the second line?", DEPT, levels=LV, images=[_url(_png())], images_earlier=True)
    ctx = gen.calls[0][0]
    assert ctx.images_earlier and "shared earlier in this chat" in build_user_prompt(ctx, "and the second line?")


def test_several_images_are_numbered_and_reading_rules_exist():
    ctx = AnswerContext(general_mode=True, images=["a", "b"])
    assert "Image 1 to Image 2" in build_user_prompt(ctx, "compare")
    flat = " ".join(GENERAL_SYSTEM_PROMPT.split())
    assert "[unclear]" in flat and "no \"I'll make a quick mockup now\"" in flat and "**What they're asking**" in flat


def test_the_name_asked_for_is_always_in_the_image_prompt():
    """QA 2026-10-25: the Twitch banner for 'NightOwl' came out saying 'USERNAME'."""
    gen = _Gen(PLAN | {"asset": "twitch_banner", "background": "opaque", "prompt": "banner with name lettering"}, [_png((1536, 1024))])
    make_image(_svc(gen), "Create a Twitch banner for a streamer called NightOwl, purple neon", [])
    assert '"NightOwl" with exactly this spelling and capitalisation' in gen.calls[0]["prompt"]


def test_a_dropped_offer_takes_its_bold_option_heading_with_it():
    from backend.retrieval.ask import _drop_term_offers
    text = ("**Option 1 - Value**\n>> Happy to explain what's included.\n**Option 2 - Ask**\n>> Which parts matter most to you?\n"
            "**Option 3 - Deal**\n>> I can give you a discount today.\nWhy: honest and helpful")
    out = _drop_term_offers(text, [], "")
    assert "Option 3" not in out and "discount" not in out and out.count(">>") == 2


def test_what_they_are_asking_bullets_are_not_rewritten_by_the_offer_guard():
    from backend.retrieval.ask import _drop_term_offers
    text = ("**What they're asking**\n- A discount on the logo.\n\n**Option 1 - Budget**\n>> What budget did you have in mind?\n"
            "**Option 2 - Deal**\n>> I can give you a discount today.\n**Option 3 - Scope**\n>> Which parts could we skip?\nWhy: honest")
    out = _drop_term_offers(text, [], "")
    assert "- A discount on the logo." in out and "give you a discount" not in out and "Option 3" not in out


def test_create_image_mode_lets_the_model_decide_and_client_replies_mirror_the_client():
    """Owner 2026-10-25: image mode decides draw vs answer; replies use the client's language and tone and aim to sell."""
    _, search, _ = build(FakeStore(vec=[]))
    object.__setattr__(search.settings, "general_assistant", True)
    gen = _Says("**What they're asking**\n- A cheaper logo.")
    AskService(search, gen, search.settings).ask("what should I reply?", DEPT, levels=LV, images=[_url(_png())], prefer_image=True)
    assert "CREATE IMAGE mode on" in build_user_prompt(gen.calls[0][0], "what should I reply?")
    flat = " ".join(GENERAL_SYSTEM_PROMPT.split())
    assert "in the CLIENT's language and script" in flat and "moves the sale forward" in flat
    assert "pasted message from a client or prospect is always in scope" in flat
