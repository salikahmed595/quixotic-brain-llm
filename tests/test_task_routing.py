"""Owner 2026-10-26 "CRITICAL QUALITY FIXES V2": permanent tests for the routing, translation direction and format checks.
The live behaviour (real model answers) is covered by evaluation/quality_v2 (cases.json + run.py)."""
from backend.generation.prompt import GENERAL_SYSTEM_PROMPT, IMAGE_DIRECTOR_PROMPT, TRANSLATE_PROMPT, build_user_prompt
from backend.generation.tasks import (AUTO, Task, format_problems, parse_task, run_translation, task_instructions,
                                      translation_problem, translation_target)
from backend.models import AnswerContext
from backend.retrieval.ask import AskService, _task_verbosity
from backend.retrieval.language import LanguageService
from tests.fakes import FakeStore
from tests.test_retrieval import DEPT, LV, build

DETECT = LanguageService(0.3).detect
EN = "Hey, I really like your artwork, but I need some time to think about it."
RU = "Bhai mujhe tumhara design acha laga lekin abhi mere paas budget nahi hai."


# ---------------- issue 1: translation ----------------
def test_auto_direction_english_to_roman_urdu_and_back():
    assert translation_target("auto", DETECT(EN)) == "Roman Urdu"
    assert translation_target("auto", DETECT(RU)) == "English"
    assert translation_target("English ↔ Roman Urdu", DETECT(RU)) == "English"
    assert translation_target("auto", DETECT("client ne bola the logo is too dark")) == AUTO     # mixed: the model decides


def test_asking_for_the_language_the_text_is_already_in_flips_instead_of_copying():
    """Root cause: target 'English' + English text returned the same text 'polished'."""
    assert translation_target("English", "english") == "Roman Urdu"
    assert translation_target("Roman Urdu", "roman_urdu") == "English"
    assert translation_target("Spanish", "roman_urdu") == "Spanish"
    assert "return it polished" not in TRANSLATE_PROMPT


def test_copies_and_wrong_language_outputs_are_rejected():
    assert translation_problem(EN, EN + " ", "Roman Urdu", DETECT) == "copied the input"
    assert translation_problem(EN, "Hey, I really love your art but I need time.", "Roman Urdu", DETECT) == "still English, not Roman Urdu"
    assert translation_problem(RU, "Bhai mujhe design acha laga lekin budget nahi hai", "English", DETECT) == "still Roman Urdu, not English"
    assert translation_problem(EN, "Hey, mujhe tumhara artwork bohat pasand aya, lekin thora time chahiye.", "Roman Urdu", DETECT) == ""


class _Tr:
    def __init__(self, *outs):
        self.outs, self.calls = list(outs), []

    def translate_for_client(self, text, target="English", slang=False):
        self.calls.append((text, target))
        return self.outs.pop(0)


def test_run_translation_retries_once_with_the_reason_then_reports_direction():
    gen = _Tr(EN, "Hey, mujhe tumhara artwork bohat pasand aya, lekin mujhe sochne ke liye thora time chahiye.")
    out, target, source = run_translation(gen, DETECT, EN, "auto")
    assert target == "Roman Urdu" and source == "English" and "pasand" in out
    assert len(gen.calls) == 2 and "copied the input" in gen.calls[1][0]


def test_run_translation_refuses_to_return_a_copy():
    import pytest
    with pytest.raises(RuntimeError, match="unchanged"):
        run_translation(_Tr(RU, RU), DETECT, RU, "auto")


class _Router:
    """Answer model fake with a router: returns the given Task, records prompts, answers with the given texts in order."""
    def __init__(self, task, *answers):
        self.task, self.answers, self.calls, self.translations = task, list(answers), [], []

    def classify_task(self, question, history=(), has_images=False):
        return self.task

    def generate_answer(self, context, question):
        self.calls.append((context, question))
        return self.answers.pop(0)

    def translate_for_client(self, text, target="English", slang=False):
        self.translations.append((text, target))
        return "Bro, I liked your design, but I don't have the budget right now."


def _svc():
    _, search, _ = build(FakeStore(vec=[]))
    object.__setattr__(search.settings, "general_assistant", True)
    return search


def test_translation_typed_in_chat_uses_the_checked_translation_not_the_chat_answer():
    search = _svc()
    gen = _Router(Task(task="translation", text_to_translate=RU, target_language="English"))
    r = AskService(search, gen, search.settings).ask(f"isko english mein translate karo: {RU}", DEPT, levels=LV)
    assert r.task == "translation" and r.answer.startswith("Bro, I liked") and gen.translations == [(RU, "English")] and not gen.calls


# ---------------- issues 3 and 4: one greeting, one reply, the requested length ----------------
def test_greeting_gets_only_its_own_rules_not_the_sales_or_options_format():
    rules = task_instructions(Task(task="greeting", count=1))
    assert "NOT a sales pitch" in rules and "streamer" in rules and "exactly 1 message" in rules
    assert "Option 1" not in rules and "move toward the sale" not in rules.lower()


def test_overall_reply_in_4_5_lines_is_one_message_with_a_word_target():
    t = Task(task="client_reply", count=1, lines=(4, 5))
    rules = task_instructions(t)
    assert "ONE reply" in rules and "never that it is already done" in rules and "48-95 words" in rules
    assert format_problems(t, ">> Got you! I'll make the background cleaner, the character bigger, a darker blue and move your "
                              "username to the bottom. Thanks for explaining everything so clearly, it really helps us get it "
                              "right for you and keep the whole design balanced.") == []
    probs = format_problems(t, "**Option 1 - A**\n>> Sure!\n**Option 2 - B**\n>> Okay!\nWhy: fine")
    assert any("exactly ONE reply" in p for p in probs) and any("words" in p for p in probs)


def test_what_should_i_reply_gets_options_and_write_a_reply_gets_one():
    """QA V2 RT2/RT3: the router said count 1 for 'what should I reply?', so the employee lost the options and the explanation."""
    from backend.generation.tasks import _strip_label, settle_task
    for q in ('A client wrote: "hey how much for an emote?" what should I reply?', "mujhe kya reply karna chahiye?",
              "Here is a client message, what should I reply?", "give me reply options"):
        assert settle_task(Task(task="client_reply", count=1), q).count is None, q
    for q in ("Write an overall reply in 4-5 lines.", "write a reply i can send", "write one short message to send him"):
        assert settle_task(Task(task="client_reply"), q).count == 1, q
    q = 'client ne English mein likha hai: "Can I get the logo by Friday?" mujhe kya reply karna chahiye?'
    assert not settle_task(Task(task="client_reply", count=1, one_paragraph=True), q).one_paragraph   # router said so (measured)
    assert settle_task(Task(task="artwork_ideas", one_paragraph=True), "one idea in one paragraph").one_paragraph
    assert _strip_label("Translate this into English: bro, reduce the price") == "bro, reduce the price"
    options = Task(task="client_reply")
    assert any("3 options" in p for p in format_problems(options, ">> I'll check with the team and confirm."))
    assert format_problems(options, "Be honest.\n**Option 1 - A**\n>> a\n**Option 2 - B**\n>> b\n**Option 3 - C**\n>> c\nWhy: clear") == []


def test_a_broken_format_is_rewritten_once_with_the_exact_problem():
    search = _svc()
    draft = "**Option 1 - Warm**\n>> hey!\n**Option 2 - Chill**\n>> yo\n**Option 3 - Pro**\n>> Hello\nWhy: variety"
    gen = _Router(Task(task="greeting", count=1), draft, ">> yo, how's it going?")
    r = AskService(search, gen, search.settings).ask("write a greeting message for someone new on discord", DEPT, levels=LV)
    assert r.answer == ">> yo, how's it going?" and r.task == "greeting"
    assert "exactly 1 message line" in gen.calls[1][1] and "<draft>" in gen.calls[1][1]
    assert "NOT a sales pitch" in build_user_prompt(gen.calls[0][0], "q")


def test_single_reply_keeps_one_message_when_a_promise_is_removed():
    search = _svc()
    gen = _Router(Task(task="client_reply", count=1), ">> Got it! I'll request priority for your order and fix the colours.",
                  ">> Got it! I'll fix the colours and check timing with the team.")
    r = AskService(search, gen, search.settings).ask("write one reply", DEPT, levels=LV)
    assert r.answer.count(">>") == 1


# ---------------- issues 2, 5, 6: ideas, explanations, console skins ----------------
def test_idea_rules_follow_the_requested_count_type_and_length():
    t = Task(task="artwork_ideas", count=1, artwork_type="mascot logo", lines=(5, 6), one_paragraph=True)
    rules = task_instructions(t)
    assert "Exactly 1 idea" in rules and "mascot logo" in rules and "60-114 words" in rules and "One continuous paragraph" in rules
    assert "So I was thinking" in " ".join(rules.split()) and "Do not force" in rules
    assert format_problems(t, "- one\n- two") and _task_verbosity(t) == "medium"


def test_console_skins_get_physical_product_rules():
    rules = task_instructions(Task(task="artwork_ideas", artwork_type="PS5 console skin"))
    assert "PHYSICAL product" in rules and "vents" in rules and "model and edition are needed" in rules
    assert "console_skin" in IMAGE_DIRECTOR_PROMPT


# ---------------- issue 7: images keep the approved concept ----------------
def test_image_of_this_concept_carries_the_concept_to_the_art_director():
    search = _svc()
    gen = _Router(Task(task="image", uses_previous=True))
    history = [("PS5 skin concept please", "So I was thinking: matte black panels with olive camo strips ...")]
    r = AskService(search, gen, search.settings).ask("now generate an image of this concept", DEPT, levels=LV, history=history)
    assert r.image_request and r.image_context.startswith("So I was thinking") and not gen.calls


def test_director_input_marks_the_approved_concept_as_data():
    from backend.generation.prompt import build_image_director_input
    s = build_image_director_input("draw it", False, "camo PS5 skin")
    assert "<approved_concept>\ncamo PS5 skin\n</approved_concept>" in s and "<approved_concept> (when given)" in IMAGE_DIRECTOR_PROMPT


# ---------------- system-wide ----------------
def test_router_output_is_validated():
    t = parse_task('{"task": "nonsense", "count": 99, "lines": [6, 5], "words": [10, 50]}')
    assert t.task == "other" and t.count is None and t.lines is None and t.words == (10, 50)
    assert parse_task("not json").task == "other"


def test_priority_order_and_no_routing_fallback():
    flat = " ".join(GENERAL_SYSTEM_PROMPT.split())
    assert "1. these safety and application rules; 2. the ACTIVE TASK block" in flat
    assert task_instructions(Task(task="other")) == ""
    assert build_user_prompt(AnswerContext(general_mode=True), "hi").endswith("Question:\nhi")
