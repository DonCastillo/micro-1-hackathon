"""Injection must be exact: the span it reports is the ground truth.

Every assertion here defends one of two things — that the reported span
really contains the inserted sentence, and that the sentence landed in the
section its style promises. Both feed labels.yaml directly.
"""

from pathlib import Path

import pytest

from src.injector.inject import (
    binding_language,
    STYLES,
    _section_body,
    inject_blocker,
    inject_distractor,
    insert,
    render,
    render_distractor,
)
from src.rules import blocks, load_profile, load_taxonomy

BASE_DIR = Path(__file__).resolve().parent.parent / "src/injector/bases"
BASES = sorted(p for p in BASE_DIR.glob("*.md") if p.name != "README.md")
PROFILE = load_profile()
BLOCKERS = load_taxonomy()["blockers"]

# Every blocker paired with a value that genuinely blocks the profile.
CASES = [(b, b["blocking_values"][0] if b["kind"] == "parametric" else None) for b in BLOCKERS]


def _case_id(case):
    return case[0]["id"]


@pytest.mark.parametrize("case", CASES, ids=_case_id)
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("base", BASES, ids=lambda p: p.stem[:12])
def test_span_contains_exactly_the_inserted_sentence(case, style, base):
    blocker, value = case
    text = base.read_text()
    new_text, (start, end), sentence = inject_blocker(text, blocker, style, PROFILE, value)
    assert new_text[start:end] == sentence


@pytest.mark.parametrize("case", CASES, ids=_case_id)
@pytest.mark.parametrize("style", STYLES)
def test_injection_only_adds_text(case, style):
    """The original posting survives intact, with one deliberate exception.

    A years blocker replaces the base's own years line rather than sitting
    beneath it — see `drop_existing_years_requirement`. Every other line must
    still be present.
    """
    import re

    blocker, value = case
    text = BASES[0].read_text()
    new_text, _, sentence = inject_blocker(text, blocker, style, PROFILE, value)

    replaces_years = blocker["id"] == "years_of_experience"
    for line in text.splitlines():
        if not line.strip():
            continue
        if replaces_years and re.match(r"^- \d+\+?\s*years", line):
            assert line not in new_text, "the stale years requirement should be gone"
            continue
        assert line in new_text, f"injection destroyed the line {line!r}"


@pytest.mark.parametrize("style", STYLES)
def test_years_injection_leaves_exactly_one_years_figure(style):
    import re

    yoe = next(b for b in BLOCKERS if b["id"] == "years_of_experience")
    new_text, _, _ = inject_blocker(BASES[0].read_text(), yoe, style, PROFILE, 12)
    assert set(re.findall(r"(\d+)\+?\s*years", new_text, re.I)) == {"12"}


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_explicit_lands_in_requirements(case):
    blocker, value = case
    text = BASES[0].read_text()
    new_text, (start, _), _ = inject_blocker(text, blocker, "explicit", PROFILE, value)
    body_start, body_end = _section_body(new_text, "Requirements")
    assert body_start <= start < body_end, "explicit phrasing must land in Requirements"


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_footer_lands_after_equal_opportunity(case):
    """Displacement is the point: as far from Requirements as possible."""
    blocker, value = case
    text = BASES[0].read_text()
    new_text, (start, _), _ = inject_blocker(text, blocker, "footer", PROFILE, value)
    eo_start, _ = _section_body(new_text, "Equal opportunity")
    req_start, req_end = _section_body(new_text, "Requirements")
    assert start > eo_start, "footer phrasing must sit after the EEO paragraph"
    assert start > req_end, "footer phrasing must be well clear of Requirements"


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_indirect_lands_before_requirements(case):
    blocker, value = case
    text = BASES[0].read_text()
    new_text, (start, _), _ = inject_blocker(text, blocker, "indirect", PROFILE, value)
    req_start, _ = _section_body(new_text, "Requirements")
    assert start < req_start, "indirect phrasing must read as body prose, not a requirement"


@pytest.mark.parametrize("case", CASES, ids=_case_id)
@pytest.mark.parametrize("style", STYLES)
def test_no_unfilled_placeholders(case, style):
    blocker, value = case
    sentence = render(blocker, style, value)
    assert "{" not in sentence and "}" not in sentence


def test_salary_is_formatted_with_separators():
    comp = next(b for b in BLOCKERS if b["id"] == "compensation_floor")
    assert "$115,000" in render(comp, "indirect", 115000)


def test_refuses_a_value_that_does_not_block():
    """The guard that makes a label inversion impossible to generate."""
    yoe = next(b for b in BLOCKERS if b["id"] == "years_of_experience")
    assert not blocks(yoe, PROFILE, 3), "3 years does not block a 6-year candidate"
    with pytest.raises(ValueError, match="does not block"):
        inject_blocker(BASES[0].read_text(), yoe, "explicit", PROFILE, 3)


def test_rejects_unknown_style():
    with pytest.raises(ValueError, match="unknown style"):
        insert(BASES[0].read_text(), "anything", "sidebar")


def test_every_blocking_value_is_injectable():
    """Not just the first value — generate.py samples the whole list."""
    text = BASES[0].read_text()
    for blocker in BLOCKERS:
        values = blocker.get("blocking_values") or [None]
        for value in values:
            for style in STYLES:
                new_text, (start, end), sentence = inject_blocker(
                    text, blocker, style, PROFILE, value
                )
                assert new_text[start:end] == sentence


# ─── distractors (step 2.3) ───────────────────────────────────────────────

DISTRACTOR_CASES = [
    (b, i, (b["blocking_values"][0] if b["kind"] == "parametric" else None))
    for b in BLOCKERS
    for i in range(len(b["distractors"]))
]


def _distractor_id(case):
    return f"{case[0]['id']}#{case[1]}"


@pytest.mark.parametrize("case", DISTRACTOR_CASES, ids=_distractor_id)
@pytest.mark.parametrize("style", STYLES)
def test_distractor_span_is_exact(case, style):
    blocker, index, value = case
    text = BASES[0].read_text()
    new_text, (start, end), sentence = inject_distractor(text, blocker, style, index, value)
    assert new_text[start:end] == sentence


@pytest.mark.parametrize("case", DISTRACTOR_CASES, ids=_distractor_id)
def test_no_distractor_uses_mandatory_language(case):
    """The whole distinction is modality: 'preferred' is not 'required'.

    A distractor phrased as binding would be a genuine blocker sitting in a
    posting labelled APPLY — the same label inversion the blocker guard
    prevents, arriving from the opposite direction.
    """
    blocker, index, value = case
    sentence = render_distractor(blocker, index, value)
    binding = binding_language(sentence)
    assert not binding, f"{blocker['id']} distractor {index} is binding: {binding}"


@pytest.mark.parametrize("case", DISTRACTOR_CASES, ids=_distractor_id)
def test_distractor_has_no_unfilled_placeholder(case):
    blocker, index, value = case
    sentence = render_distractor(blocker, index, value)
    assert "{" not in sentence and "}" not in sentence


def test_every_blocker_has_at_least_one_distractor():
    """Without one, that blocker's topic never appears in a clean posting and
    the agent is never tested on distinguishing it."""
    for blocker in BLOCKERS:
        assert blocker["distractors"], f"{blocker['id']} has no distractor"


def test_distractor_guard_rejects_binding_language():
    """Prove the guard fires rather than being decorative."""
    fake = {
        "id": "fake",
        "kind": "absolute",
        "distractors": ["An active CISSP certification is required."],
    }
    with pytest.raises(ValueError, match="mandatory language"):
        inject_distractor(BASES[0].read_text(), fake, "explicit", 0)


def test_the_years_distractor_is_the_critical_trap():
    """Names a figure the candidate does not meet, but only as a preference."""
    yoe = next(b for b in BLOCKERS if b["id"] == "years_of_experience")
    sentence = render_distractor(yoe, 0)
    assert "8+" in sentence and "preferred" in sentence
    assert PROFILE["years_experience"] < 8
    # And it must survive the guard: it is a near-miss, not a requirement.
    inject_distractor(BASES[0].read_text(), yoe, "explicit", 0)
