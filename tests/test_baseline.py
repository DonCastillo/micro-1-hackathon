"""The baseline's parse layer, tested offline against prose models actually write.

The line this defends is EVAL.md 9: the parse layer may adapt to any shape,
but it must only *extract*. If it started inferring blockers the model never
mentioned, it would be doing the baseline's work and inflating the number
every iteration is measured against.
"""

import pytest

from src.baseline.run import PROMPT, build_prompt, parse_baseline_output
from src.llm import PRICING, cost_usd
from src.rules import load_profile, load_taxonomy
from src.schema import ParseError

IDS = sorted(b["id"] for b in load_taxonomy()["blockers"])
PROFILE = load_profile()


# ─── verdict extraction ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    [
        "You should not apply — they can't sponsor visas.",
        "I'd skip this one.",
        "Don't apply. The clearance requirement disqualifies you.",
        "This role is not eligible for you given your work authorization.",
        "Unfortunately this disqualifies you.",
    ],
)
def test_skip_phrasings(text):
    assert parse_baseline_output(text, IDS).verdict == "SKIP"


@pytest.mark.parametrize(
    "text",
    [
        "Yes, apply — nothing here disqualifies you.",
        "You should apply. It looks like a good match.",
        "This is worth applying to.",
        "No blockers that I can see. Go ahead and apply.",
    ],
)
def test_apply_phrasings(text):
    assert parse_baseline_output(text, IDS).verdict == "APPLY"


def test_negative_verdict_wins_over_the_bare_word_apply():
    """'Do not apply' contains 'apply'; specificity has to decide."""
    text = "I would not apply to this one. If you did apply, expect a rejection."
    assert parse_baseline_output(text, IDS).verdict == "SKIP"


def test_prose_with_no_verdict_is_a_parse_failure():
    with pytest.raises(ParseError, match="no verdict"):
        parse_baseline_output("This posting is for a backend role in fintech.", IDS)


# ─── blocker extraction ───────────────────────────────────────────────────

def test_named_label_is_claimed():
    text = "Skip it. The blocker is work_authorization."
    p = parse_baseline_output(text, IDS)
    assert [c.type for c in p.blockers] == ["work_authorization"]


def test_label_written_as_prose_is_recognised():
    """Models reformat ids: 'work authorization' rather than 'work_authorization'."""
    text = "Skip — this fails on work authorization grounds."
    assert [c.type for c in parse_baseline_output(text, IDS).blockers] == ["work_authorization"]


def test_several_labels_are_all_claimed():
    text = "Skip. Both security_clearance and citizenship_required apply here."
    assert set(c.type for c in parse_baseline_output(text, IDS).blockers) == {
        "security_clearance",
        "citizenship_required",
    }


def test_blockers_carry_no_evidence():
    """The baseline is never asked to quote, so it never does.

    This is why EVAL.md separates missing evidence from hallucination: the
    baseline will score 100% missing and 0% hallucinated, which is an accurate
    description of a system that was not asked for citations.
    """
    p = parse_baseline_output("Skip, work_authorization is the problem.", IDS)
    assert p.blockers[0].evidence == ""


def test_unmentioned_blockers_are_never_inferred():
    """The parse layer extracts; it does not reason.

    The posting here is plainly about sponsorship, but the model did not name
    a label, so no blocker is claimed. Inferring one would be the harness
    quietly playing the baseline's hand.
    """
    p = parse_baseline_output("Skip this — they won't sponsor a visa for you.", IDS)
    assert p.verdict == "SKIP"
    assert p.blockers == []


def test_a_verdict_with_no_labels_still_parses():
    p = parse_baseline_output("I'd apply.", IDS)
    assert p.verdict == "APPLY" and p.blockers == []


# ─── the prompt itself ────────────────────────────────────────────────────

def test_prompt_contains_posting_profile_and_labels():
    prompt = build_prompt("## Requirements\n- 5+ years", PROFILE, IDS)
    assert "5+ years" in prompt
    assert "requires_sponsorship" in prompt, "the profile must be present"
    assert all(f"- {i}" in prompt for i in IDS), "all 14 labels must be listed"


def test_prompt_withholds_everything_the_iterations_add():
    """EVAL.md 9: ids only. No descriptions, no phrasings, no schema, no
    evidence requirement, no per-category decomposition."""
    prompt = build_prompt("posting text", PROFILE, IDS).lower()
    for leaked in ("json", "evidence", "verbatim", "quote", "step by step", "category"):
        assert leaked not in prompt, f"the baseline prompt must not mention {leaked!r}"
    taxonomy = load_taxonomy()
    for blocker in taxonomy["blockers"]:
        assert blocker["description"].lower() not in prompt
        assert blocker["phrasings"]["explicit"].lower() not in prompt


def test_prompt_is_a_single_question():
    assert PROMPT.count("Should I apply?") == 1


# ─── cost ─────────────────────────────────────────────────────────────────

def test_cost_matches_published_pricing():
    assert cost_usd("claude-sonnet-5", 1_000_000, 0) == pytest.approx(2.00)
    assert cost_usd("claude-sonnet-5", 0, 1_000_000) == pytest.approx(10.00)
    assert cost_usd("claude-opus-5", 1_000_000, 1_000_000) == pytest.approx(30.00)


def test_unknown_model_refuses_rather_than_reporting_zero():
    """A silent 0.0 would put a free run in the cost-per-task column."""
    with pytest.raises(KeyError, match="no pricing"):
        cost_usd("claude-imaginary-9", 1000, 1000)


def test_pinned_model_is_priced():
    from src.llm import model_id

    assert model_id() in PRICING
