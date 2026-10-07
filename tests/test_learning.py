"""Learning from 👍 / 👎: the numbers are mild and bounded, style patterns need a contrast, nothing is invented."""
from backend.generation.prompt import SYSTEM_PROMPT, build_user_prompt
from backend.learning.feedback import MIN_VOTES, chunk_boost, reorder, style_hints
from backend.models import AnswerContext
from tests.fakes import cand


def test_boost_needs_enough_votes_and_is_shrunk_toward_zero():
    assert chunk_boost(2, 0) == 0 and chunk_boost(0, MIN_VOTES - 1) == 0          # too few ratings: no effect
    assert chunk_boost(3, 0) == 0.375 and chunk_boost(0, 3) == -0.375             # not +1 / -1 after three clicks
    assert chunk_boost(5, 5) == 0
    assert 0.9 < chunk_boost(100, 0) < 1 and chunk_boost(100, 0) > chunk_boost(10, 0) > chunk_boost(3, 0)


def test_reorder_is_a_nudge_not_an_override():
    cs = [cand(text=str(i)) for i in range(1, 9)]
    texts = lambda xs: [c.text for c in xs]
    assert reorder(cs, {}) is cs and reorder(cs, {cs[3].chunk_id: 0.0}) is cs         # nothing learned -> same list
    down = reorder(cs, {cs[0].chunk_id: -0.545})                                       # six thumbs-down on the first passage
    assert texts(down)[0] != "1" and texts(down).index("1") <= 3                       # it slips a couple of places...
    up = reorder(cs, {cs[3].chunk_id: 0.375})                                          # three thumbs-up on the fourth
    assert texts(up).index("4") < 3 and texts(up).index("4") > 0                       # ...a liked one rises, but not to the very top
    extreme = reorder(cs, {cs[7].chunk_id: 0.95})
    assert texts(extreme)[0] == "1" and texts(extreme).index("8") >= 3                 # even a near-unanimous history cannot jump the whole list
    assert sorted(texts(extreme)) == sorted(texts(cs))                                 # nothing is dropped or hidden


def rows(liked, disliked, reasons=()):
    return ([{"helpful": True, "answer": a, "reasons": []} for a in liked]
            + [{"helpful": False, "answer": a, "reasons": list(reasons)} for a in disliked])


SHORT_LIST = "- Ask about the concern\n- Explain the value\n- Offer payment options"
LONG_PROSE = " ".join(["You should begin by listening carefully to the customer and then explaining the value of the service in detail."] * 8)


def test_style_hints_find_a_contrast_between_liked_and_disliked_answers():
    h = style_hints(rows([SHORT_LIST] * 3, [LONG_PROSE] * 2))
    assert "short, to-the-point answers" in h and "bullet points or numbered steps" in h
    h = style_hints(rows([LONG_PROSE] * 3, [SHORT_LIST] * 2))
    assert "detailed, step-by-step answers" in h and "plain paragraphs without lists" in h


def test_style_hints_never_invent_a_preference():
    assert style_hints(rows([SHORT_LIST] * 10, [])) == []                              # only ever 👍: no contrast, no hint
    assert style_hints(rows([SHORT_LIST] * 3, [LONG_PROSE])) == []                    # one 👎 is not a pattern
    assert style_hints(rows([SHORT_LIST, LONG_PROSE, SHORT_LIST], [LONG_PROSE, SHORT_LIST])) == []   # mixed signals
    assert style_hints([]) == []


def test_reasons_count_even_without_enough_examples():
    assert style_hints(rows([], [LONG_PROSE] * 2, reasons=["too long"])) == ["short, to-the-point answers"]
    assert style_hints(rows([], [SHORT_LIST] * 2, reasons=["too short"])) == ["detailed, step-by-step answers"]
    assert style_hints(rows([], [LONG_PROSE], reasons=["too long"])) == []             # a single click is not a pattern


def test_prompt_marks_rejected_answers_and_carries_learned_style():
    ctx = AnswerContext(knowledge=[cand(text="Refunds take 7 days.")],
                        history=[("what is the refund time", "Refunds take 7 days.", "not helpful"), ("and for cards?", "", None)],
                        preferences={"learned_style": ["short, to-the-point answers", "bullet points or numbered steps"], "answer_style": "balanced"})
    p = build_user_prompt(ctx, "q")
    assert "assistant [not helpful]: Refunds take 7 days." in p
    assert "learned from their thumbs: short, to-the-point answers; bullet points or numbered steps" in p
    assert "[not helpful]" in SYSTEM_PROMPT and "thumbs" in SYSTEM_PROMPT
    two = build_user_prompt(AnswerContext(knowledge=[cand(text="a")], history=[("q", "a")]), "q")      # old two-item history still works
    assert "assistant: a" in two
