"""The parser sits between every system and the scorer, so its failures are
indistinguishable from agent failures unless they are tested directly.

The cases below are shapes models actually emit: fenced blocks, an object
buried in prose, a bare list of type names, lowercase verdicts, trailing
commentary. EVAL.md 9 allows the parse layer to absorb all of it — what it
forbids is changing a prompt to make output easier to read.
"""

import json

import pytest

from src.schema import (
    PREDICTION_JSON_SCHEMA,
    VERDICTS,
    Claim,
    ParseError,
    Prediction,
    parse_prediction,
)
from src.rules import load_taxonomy

KNOWN = {b["id"] for b in load_taxonomy()["blockers"]}

CLEAN = {
    "verdict": "SKIP",
    "blockers": [
        {"type": "work_authorization", "evidence": "We are unable to provide visa sponsorship."}
    ],
    "caveats": [],
}


# ─── shapes that must parse ───────────────────────────────────────────────

def test_plain_json():
    p = parse_prediction(json.dumps(CLEAN))
    assert p.verdict == "SKIP"
    assert p.blockers[0].type == "work_authorization"


def test_dict_passes_through():
    assert parse_prediction(CLEAN).verdict == "SKIP"


def test_fenced_json():
    raw = f"Here is my analysis:\n\n```json\n{json.dumps(CLEAN)}\n```\n\nHope that helps."
    assert parse_prediction(raw).blockers[0].type == "work_authorization"


def test_unfenced_json_surrounded_by_prose():
    raw = f"After reviewing the posting I concluded:\n{json.dumps(CLEAN)}\nLet me know."
    assert parse_prediction(raw).verdict == "SKIP"


def test_nested_braces_do_not_break_extraction():
    payload = dict(CLEAN, caveats=[{"type": "years_of_experience", "evidence": "8+ preferred"}])
    raw = f"text {{not json}} more text\n{json.dumps(payload)}\ntrailing"
    p = parse_prediction(raw)
    assert len(p.blockers) == 1 and len(p.caveats) == 1


@pytest.mark.parametrize(
    "given,expected",
    [
        ("skip", "SKIP"),
        ("Skip", "SKIP"),
        ("APPLY_WITH_CAVEATS", "APPLY_WITH_CAVEAT"),
        ("apply with caveat", "APPLY_WITH_CAVEAT"),
        ("do not apply", "SKIP"),
        ("  APPLY  ", "APPLY"),
    ],
)
def test_verdict_spellings_normalize(given, expected):
    assert parse_prediction({**CLEAN, "verdict": given}).verdict == expected


def test_alternate_field_names():
    """Models reach for 'quote' as often as 'evidence'."""
    raw = {"verdict": "SKIP", "blockers": [{"blocker": "security_clearance", "quote": "TS/SCI"}]}
    claim = parse_prediction(raw).blockers[0]
    assert claim.type == "security_clearance" and claim.evidence == "TS/SCI"


def test_bare_type_names_without_evidence():
    """A baseline may name blockers without quoting anything."""
    p = parse_prediction({"verdict": "SKIP", "blockers": ["work_authorization"]})
    assert p.blockers[0].type == "work_authorization"
    assert p.blockers[0].evidence == ""


def test_missing_lists_default_to_empty():
    p = parse_prediction({"verdict": "APPLY"})
    assert p.blockers == [] and p.caveats == []


# ─── shapes that must fail ────────────────────────────────────────────────

def test_prose_with_no_json_raises():
    with pytest.raises(ParseError, match="no JSON object"):
        parse_prediction("I think you should probably skip this one, honestly.")


def test_json_without_a_verdict_raises():
    with pytest.raises(ParseError):
        parse_prediction(json.dumps({"blockers": [], "caveats": []}))


def test_unrecognized_verdict_raises():
    with pytest.raises(ParseError, match="unrecognized verdict"):
        parse_prediction({"verdict": "MAYBE_LATER"})


# ─── scoring contract ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "verdict,scored", [("APPLY", "APPLY"), ("APPLY_WITH_CAVEAT", "APPLY"), ("SKIP", "SKIP")]
)
def test_caveat_scores_as_apply(verdict, scored):
    assert Prediction(verdict=verdict).scored_verdict == scored


def test_unparseable_output_is_scored_as_finding_nothing():
    """Not as SKIP — that would hand it the 16 blocked postings for free."""
    p = Prediction.unparseable("no JSON found")
    assert p.scored_verdict == "APPLY"
    assert p.blockers == []
    assert p.parse_error


def test_invented_types_are_kept_for_the_scorer_to_reject():
    """An invented blocker is a false positive, which is exactly correct.

    Dropping it here would quietly forgive the claim instead of penalising it.
    """
    p = parse_prediction({"verdict": "SKIP", "blockers": [{"type": "vibes", "evidence": "x"}]})
    assert p.blockers[0].type == "vibes"
    assert p.unknown_types(KNOWN) == ["vibes"]


def test_known_types_are_not_flagged():
    assert parse_prediction(CLEAN).unknown_types(KNOWN) == []


# ─── serialization ────────────────────────────────────────────────────────

def test_round_trips_through_dict():
    p = parse_prediction(CLEAN)
    assert parse_prediction(p.to_dict()).to_dict() == p.to_dict()


def test_parse_error_is_recorded_in_output():
    assert Prediction.unparseable("boom").to_dict()["parse_error"] == "boom"


def test_json_schema_matches_the_dataclass():
    """The schema is handed to the model; drift would silently break parsing."""
    assert PREDICTION_JSON_SCHEMA["properties"]["verdict"]["enum"] == list(VERDICTS)
    assert set(PREDICTION_JSON_SCHEMA["required"]) == {"verdict", "blockers", "caveats"}
    fields = set(PREDICTION_JSON_SCHEMA["properties"]["blockers"]["items"]["properties"])
    assert fields == {"type", "evidence"} == set(Claim("a", "b").to_dict())
