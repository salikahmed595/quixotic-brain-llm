"""QA 2026-10-24: QAI-01 (selected target language honoured, never returned unchanged) and QAI-02 (no questions)."""
from backend.api.v1.translate import TARGET_LANGUAGES, _same
from backend.generation.prompt import TRANSLATE_PROMPT, build_translate_input


def test_target_language_reaches_the_model_and_prompt_forbids_untranslated_output_and_questions():
    assert build_translate_input("Hola", "Roman Urdu").startswith("TARGET language: Roman Urdu")
    flat = " ".join(TRANSLATE_PROMPT.split())
    assert "never return the source unchanged" in flat and "Never ask a question" in flat and "Latin" in flat
    assert {"English", "Roman Urdu", "Spanish", "German"} <= set(TARGET_LANGUAGES)


def test_unchanged_output_is_detected_ignoring_punctuation_and_case():
    assert _same("Aap ka logo ready hai", "aap ka logo ready hai.") and not _same("Aap ka logo", "Tu logo está listo")


def test_any_typed_language_name_is_accepted_and_junk_is_rejected():
    """Owner 2026-10-24: 'translate in any language'."""
    from backend.api.v1.translate import _LANGUAGE_NAME
    for ok in ("Japanese", "Swahili", "Brazilian Portuguese", "Chinese (Simplified)", "Roman Urdu"):
        assert _LANGUAGE_NAME.match(ok), ok
    for bad in ("x", "1234", "<script>", "a" * 50):
        assert not _LANGUAGE_NAME.match(bad), bad
