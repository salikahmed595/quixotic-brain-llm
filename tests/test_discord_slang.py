"""Owner 2026-10-24: Discord Slang Mode - saved per user, default OFF, applied to every AI-written message, rules unchanged."""
from backend.api.v1.auth import clean_preferences
from backend.generation.prompt import DISCORD_SLANG_NOTE, build_translate_input, build_user_prompt
from backend.generation.providers import _verbosity
from backend.models import AnswerContext


def test_default_off_and_only_true_turns_it_on():
    assert clean_preferences({})["discord_slang"] is False
    assert clean_preferences({"discord_slang": "yes"})["discord_slang"] is False
    assert clean_preferences({"discord_slang": True})["discord_slang"] is True


def test_on_adds_the_style_note_short_verbosity_and_slang_translations_off_changes_nothing():
    on = AnswerContext(general_mode=True, preferences={"discord_slang": True})
    off = AnswerContext(general_mode=True, preferences={"discord_slang": False})
    assert DISCORD_SLANG_NOTE in build_user_prompt(on, "client says wsg") and DISCORD_SLANG_NOTE not in build_user_prompt(off, "hi")
    assert "every sales rule and company fact still applies" in " ".join(DISCORD_SLANG_NOTE.split())
    assert _verbosity(on, "explain in detail") == "low"
    assert "Discord slang" in build_translate_input("hello", "English", slang=True)
    assert "Discord" not in build_translate_input("hello", "English")
