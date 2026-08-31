"""The user-facing output. Offline — rendering only, no API calls.

The design bar comes from the human-time measurement: scannable in about two
seconds, checkable in about ten. Concretely that means the posting's own
sentence appears beside every claim, and the profile detail it collides with
appears beside that. These tests hold those properties in place.
"""

import pytest

from src.check import WHY, Style, render, title_of
from src.rules import load_profile, load_taxonomy
from src.schema import Claim, Prediction

PROFILE = load_profile()
TAXONOMY = load_taxonomy()
PLAIN = Style(enabled=False)

POSTING = (
    "# Senior Backend Engineer, Payments\nRemote (United States)\n\n"
    "## Requirements\n- 5+ years\n"
)


def _render(prediction):
    return render(POSTING, prediction, PROFILE, TAXONOMY, elapsed=2.1, cost=0.0044, s=PLAIN)


# ─── the two verdicts ─────────────────────────────────────────────────────

def test_a_blocked_posting_shows_verdict_quote_and_reason():
    out = _render(Prediction(
        verdict="SKIP",
        blockers=[Claim("work_authorization", "We are unable to provide visa sponsorship.")],
    ))
    assert "SKIP" in out
    assert "Senior Backend Engineer, Payments" in out
    assert "Work authorization" in out, "the id must be shown as a readable label"
    assert '"We are unable to provide visa sponsorship."' in out, "the quote is the point"
    assert "You need visa sponsorship." in out, "and the half of the comparison it omits"


def test_a_clean_posting_says_so_plainly():
    out = _render(Prediction(verdict="APPLY"))
    assert "APPLY" in out
    assert "Nothing here disqualifies you." in out
    assert "14 conditions checked" in out, "an APPLY has to show its work to be trusted"


def test_every_claim_carries_its_own_quote():
    """Two blockers must not share one citation."""
    out = _render(Prediction(
        verdict="SKIP",
        blockers=[
            Claim("citizenship_required", "U.S. Persons only."),
            Claim("employment_type", "This is a W2 contract position."),
        ],
    ))
    assert '"U.S. Persons only."' in out
    assert '"This is a W2 contract position."' in out
    assert out.count("✗") == 2


def test_footer_reports_count_time_and_cost():
    out = _render(Prediction(verdict="SKIP", blockers=[Claim("work_authorization", "x")]))
    assert "1 blocker ·" in out and "2.1s" in out and "$0.0044" in out


def test_blocker_count_is_pluralised():
    one = _render(Prediction(verdict="SKIP", blockers=[Claim("work_authorization", "x")]))
    none = _render(Prediction(verdict="APPLY"))
    assert "1 blocker ·" in one and "0 blockers ·" in none


# ─── the explanations ─────────────────────────────────────────────────────

@pytest.mark.parametrize("blocker", TAXONOMY["blockers"], ids=lambda b: b["id"])
def test_every_blocker_has_a_profile_explanation(blocker):
    """A claim without one would show a quote and leave the reader to work out
    why it applies to them — which is the check that costs the ten seconds."""
    assert blocker["id"] in WHY, f"no explanation for {blocker['id']}"
    text = WHY[blocker["id"]](PROFILE)
    assert text and text.endswith("."), f"{blocker['id']} explanation is not a sentence"


def test_explanations_are_generated_from_the_profile_not_the_model():
    """They cannot hallucinate, because no model produces them."""
    assert "$140,000" in WHY["compensation_floor"](PROFILE)
    assert "6 years" in WHY["years_of_experience"](PROFILE)
    assert "Los Angeles" in WHY["onsite_location"](PROFILE)


def test_explanations_follow_the_profile_when_it_changes():
    changed = {**PROFILE, "comp_floor": 200000, "years_experience": 12}
    assert "$200,000" in WHY["compensation_floor"](changed)
    assert "12 years" in WHY["years_of_experience"](changed)


# ─── formatting ───────────────────────────────────────────────────────────

def test_title_and_location_come_from_the_posting():
    role, location = title_of(POSTING)
    assert role == "Senior Backend Engineer, Payments"
    assert location == "Remote (United States)"


def test_a_posting_without_a_location_line_still_renders():
    role, location = title_of("# Just A Role\n\n## Requirements\n- things\n")
    assert role == "Just A Role" and location == ""


def test_colour_is_suppressed_when_not_a_terminal():
    assert "\033[" not in _render(Prediction(verdict="APPLY"))


def test_colour_is_emitted_when_enabled():
    out = render(POSTING, Prediction(verdict="APPLY"), PROFILE, TAXONOMY, 1.0, 0.001,
                 Style(enabled=True))
    assert "\033[" in out


def test_verdict_badges_are_the_same_width():
    """Otherwise the title and the location line beneath it do not align."""
    skip = _render(Prediction(verdict="SKIP", blockers=[Claim("work_authorization", "x")]))
    apply_ = _render(Prediction(verdict="APPLY"))
    skip_title = next(ln for ln in skip.splitlines() if "Senior Backend" in ln)
    apply_title = next(ln for ln in apply_.splitlines() if "Senior Backend" in ln)
    assert skip_title.index("Senior") == apply_title.index("Senior")
