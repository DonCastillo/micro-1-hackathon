"""Injection must be exact: the span it reports is the ground truth.

Every assertion here defends one of two things — that the reported span
really contains the inserted sentence, and that the sentence landed in the
section its style promises. Both feed labels.yaml directly.
"""

from pathlib import Path

import pytest

from src.injector.inject import STYLES, _section_body, inject_blocker, insert, render
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
    """The original posting must survive intact — nothing deleted or mangled."""
    blocker, value = case
    text = BASES[0].read_text()
    new_text, _, sentence = inject_blocker(text, blocker, style, PROFILE, value)
    assert len(new_text) > len(text)
    for line in text.splitlines():
        if line.strip():
            assert line in new_text, f"injection destroyed the line {line!r}"


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
