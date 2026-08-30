"""Contradiction cases must genuinely contradict, and still resolve to SKIP.

The risk specific to this bucket is a case that looks hard but isn't: an
onsite requirement injected into a posting that never claimed to be remote
is just an ordinary blocker filed under the wrong label, and the "hard case"
column of the report would be overstating what was tested.
"""

from pathlib import Path

import pytest

from src.injector.contradiction import (
    SCOPED_NEGATION,
    TITLE_BODY_BLOCKERS,
    build_scoped_negation,
    build_title_body_conflict,
    is_remote_base,
)
from src.injector.inject import binding_language
from src.rules import blocks, load_profile, load_taxonomy

BASE_DIR = Path(__file__).resolve().parent.parent / "src/injector/bases"
BASES = sorted(p for p in BASE_DIR.glob("*.md") if p.name != "README.md")
PROFILE = load_profile()
BLOCKERS = {b["id"]: b for b in load_taxonomy()["blockers"]}

REMOTE_BASES = [p for p in BASES if is_remote_base(p.read_text())]


def _value_for(blocker):
    return blocker["blocking_values"][0] if blocker["kind"] == "parametric" else None


# ─── title / body conflict ────────────────────────────────────────────────

def test_most_bases_are_remote_so_conflicts_are_buildable():
    assert len(REMOTE_BASES) >= 8, f"only {len(REMOTE_BASES)} remote bases available"


@pytest.mark.parametrize("bid", TITLE_BODY_BLOCKERS)
@pytest.mark.parametrize("base", REMOTE_BASES, ids=lambda p: p.stem[:12])
def test_title_body_conflict_span_is_exact(bid, base):
    blocker = BLOCKERS[bid]
    text = base.read_text()
    new_text, (start, end), sentence = build_title_body_conflict(
        text, blocker, PROFILE, _value_for(blocker)
    )
    assert new_text[start:end] == sentence


@pytest.mark.parametrize("bid", TITLE_BODY_BLOCKERS)
def test_the_header_still_says_remote_after_injection(bid):
    """Without the surviving header there is no contradiction, just a blocker."""
    blocker = BLOCKERS[bid]
    new_text, _, _ = build_title_body_conflict(
        REMOTE_BASES[0].read_text(), blocker, PROFILE, _value_for(blocker)
    )
    assert is_remote_base(new_text)


def test_refuses_a_base_that_never_claimed_remote():
    """base_04 is Los Angeles hybrid — nothing to contradict."""
    non_remote = [p for p in BASES if not is_remote_base(p.read_text())]
    assert non_remote, "expected at least one non-remote base"
    blocker = BLOCKERS["onsite_location"]
    with pytest.raises(ValueError, match="header says Remote"):
        build_title_body_conflict(
            non_remote[0].read_text(), blocker, PROFILE, _value_for(blocker)
        )


def test_refuses_a_blocker_that_does_not_contradict_remote():
    """A degree requirement does not conflict with a remote header."""
    blocker = BLOCKERS["degree_required"]
    with pytest.raises(ValueError, match="does not contradict"):
        build_title_body_conflict(
            REMOTE_BASES[0].read_text(), blocker, PROFILE, _value_for(blocker)
        )


# ─── scoped negation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("bid", sorted(SCOPED_NEGATION))
def test_scoped_negation_span_is_exact(bid):
    blocker = BLOCKERS[bid]
    text = REMOTE_BASES[0].read_text()
    new_text, (start, end), sentence = build_scoped_negation(
        text, blocker, PROFILE, _value_for(blocker)
    )
    assert new_text[start:end] == sentence


@pytest.mark.parametrize("bid", sorted(SCOPED_NEGATION))
def test_scoped_negation_still_blocks(bid):
    """The bait clause must not soften the verdict — these are all SKIP."""
    blocker = BLOCKERS[bid]
    assert blocks(blocker, PROFILE, _value_for(blocker))


@pytest.mark.parametrize("bid", sorted(SCOPED_NEGATION))
def test_scoped_negation_is_actually_binding(bid):
    """The second clause must impose a requirement, or it is a distractor.

    This is the inverse of the distractor guard: there, binding language is a
    defect; here, its absence is.
    """
    blocker = BLOCKERS[bid]
    _, _, sentence = build_scoped_negation(
        REMOTE_BASES[0].read_text(), blocker, PROFILE, _value_for(blocker)
    )
    assert binding_language(sentence), f"{bid} scoped negation imposes nothing: {sentence!r}"


@pytest.mark.parametrize("bid", sorted(SCOPED_NEGATION))
def test_scoped_negation_has_two_clauses(bid):
    """Grant, then withdraw. One sentence is not a scoped negation."""
    blocker = BLOCKERS[bid]
    _, _, sentence = build_scoped_negation(
        REMOTE_BASES[0].read_text(), blocker, PROFILE, _value_for(blocker)
    )
    assert sentence.count(". ") >= 1, f"{bid} has no grant clause: {sentence!r}"


@pytest.mark.parametrize("bid", sorted(SCOPED_NEGATION))
def test_scoped_negation_has_no_unfilled_placeholder(bid):
    blocker = BLOCKERS[bid]
    _, _, sentence = build_scoped_negation(
        REMOTE_BASES[0].read_text(), blocker, PROFILE, _value_for(blocker)
    )
    assert "{" not in sentence and "}" not in sentence


def test_refuses_a_blocker_with_no_template():
    blocker = BLOCKERS["professional_licensure"]
    with pytest.raises(ValueError, match="no scoped-negation template"):
        build_scoped_negation(REMOTE_BASES[0].read_text(), blocker, PROFILE)


def test_enough_hard_cases_for_the_bucket():
    """EVAL.md 2 calls for 4 contradiction postings."""
    available = len(TITLE_BODY_BLOCKERS) + len(SCOPED_NEGATION)
    assert available >= 4, f"only {available} contradiction variants available"
