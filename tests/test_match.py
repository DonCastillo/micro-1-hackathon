"""The matcher decides every number in the report, so its edge cases are the
report's edge cases.

The normalization tests matter most: quotes are compared with whitespace
collapsed and case folded, but gold spans index the original text. An
off-by-a-few there would degrade evidence accuracy silently and look exactly
like an agent that cites badly.
"""

import pytest
import yaml
from pathlib import Path

from src.eval.match import locate, match_posting, overlaps
from src.schema import Claim, Prediction

CORPUS = Path(__file__).resolve().parent.parent / "data/corpus"
LABELS = yaml.safe_load((CORPUS / "labels.yaml").read_text())["postings"]

POSTING = (
    "# Senior Engineer\nRemote (United States)\n\n"
    "## Requirements\n- 5+ years of experience\n"
    "- Minimum of 12 years of professional experience required.\n\n"
    "## Benefits\n- Health cover\n"
)
SENTENCE = "Minimum of 12 years of professional experience required."
GOLD_SPAN = [POSTING.index(SENTENCE), POSTING.index(SENTENCE) + len(SENTENCE)]

GOLD = {
    "id": "jd_test",
    "expected_verdict": "SKIP",
    "blockers": [{"type": "years_of_experience", "evidence_span": GOLD_SPAN}],
}


def _pred(verdict="SKIP", blockers=(), caveats=()):
    return Prediction(
        verdict=verdict,
        blockers=[Claim(t, e) for t, e in blockers],
        caveats=[Claim(t, e) for t, e in caveats],
    )


# ─── locate: normalization must not corrupt offsets ───────────────────────

def test_locate_returns_original_text_offsets():
    assert locate(POSTING, SENTENCE) == tuple(GOLD_SPAN)


def test_locate_is_case_insensitive():
    assert locate(POSTING, SENTENCE.upper()) == tuple(GOLD_SPAN)


def test_locate_collapses_whitespace_in_the_quote():
    noisy = "Minimum of 12    years\n  of professional experience required."
    assert locate(POSTING, noisy) == tuple(GOLD_SPAN)


def test_locate_collapses_whitespace_in_the_posting():
    """A quote written on one line must match text wrapped across two."""
    wrapped = POSTING.replace("professional experience", "professional\n  experience")
    span = locate(wrapped, SENTENCE)
    assert span is not None
    assert " ".join(wrapped[span[0]:span[1]].split()) == SENTENCE


def test_locate_rejects_a_paraphrase():
    assert locate(POSTING, "They want at least twelve years of experience") is None


def test_locate_rejects_an_elided_quote():
    assert locate(POSTING, "Minimum of 12 years ... required.") is None


def test_locate_rejects_an_empty_quote():
    assert locate(POSTING, "   ") is None


def test_located_span_is_usable_as_a_slice():
    for record in LABELS:
        text = (CORPUS / f"{record['id']}.md").read_text()
        for mark in record["blockers"]:
            span = locate(text, mark["sentence"])
            assert span == tuple(mark["evidence_span"]), (
                f"{record['id']}: locate disagrees with the answer key"
            )


# ─── overlap ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "a,b,expected",
    [
        ((0, 10), (5, 15), True),
        ((5, 15), (0, 10), True),
        ((0, 10), (10, 20), False),  # touching, not overlapping
        ((0, 10), (3, 7), True),  # contained
        ((0, 1), (0, 1), True),
    ],
)
def test_overlap_semantics(a, b, expected):
    assert overlaps(a, b) is expected


# ─── detection ────────────────────────────────────────────────────────────

def test_exact_hit_is_a_true_positive():
    m = match_posting(_pred(blockers=[("years_of_experience", SENTENCE)]), GOLD, POSTING)
    assert len(m.true_positives) == 1
    assert not m.false_positives and not m.false_negatives


def test_missing_the_blocker_is_a_false_negative():
    m = match_posting(_pred(verdict="APPLY"), GOLD, POSTING)
    assert m.false_negatives == [0]
    assert not m.true_positives


def test_wrong_type_costs_twice():
    """A false positive for what was claimed, a false negative for what was not."""
    m = match_posting(_pred(blockers=[("degree_required", SENTENCE)]), GOLD, POSTING)
    assert m.false_positives == [0]
    assert m.false_negatives == [0]


def test_duplicate_claims_of_one_type_yield_one_true_positive():
    m = match_posting(
        _pred(blockers=[("years_of_experience", SENTENCE), ("years_of_experience", SENTENCE)]),
        GOLD,
        POSTING,
    )
    assert len(m.true_positives) == 1
    assert m.false_positives == [1]


def test_invented_type_is_a_false_positive():
    m = match_posting(_pred(blockers=[("vibes", SENTENCE)]), GOLD, POSTING)
    assert m.false_positives == [0]


def test_flagging_a_clean_posting_is_a_false_positive():
    clean = {"id": "jd_clean", "expected_verdict": "APPLY", "blockers": []}
    m = match_posting(_pred(blockers=[("work_authorization", SENTENCE)]), clean, POSTING)
    assert m.false_positives == [0]
    assert m.flagged_anything


def test_a_correct_clean_posting_flags_nothing():
    clean = {"id": "jd_clean", "expected_verdict": "APPLY", "blockers": []}
    m = match_posting(_pred(verdict="APPLY"), clean, POSTING)
    assert not m.flagged_anything
    assert m.verdict_correct


# ─── evidence, scored separately from detection ───────────────────────────

def test_right_type_wrong_quote_still_detects_but_fails_evidence():
    """The separation EVAL.md 3 insists on, pinned."""
    m = match_posting(
        _pred(blockers=[("years_of_experience", "5+ years of experience")]), GOLD, POSTING
    )
    assert len(m.true_positives) == 1, "detection is by type alone"
    assert m.evidence[0].found is True
    assert m.evidence[0].correct is False, "the quote points at the wrong line"


def test_fabricated_quote_is_hallucinated():
    m = match_posting(
        _pred(blockers=[("years_of_experience", "We require 20 years of tenure.")]),
        GOLD,
        POSTING,
    )
    assert m.hallucinated == [0]
    assert m.evidence[0].found is False and m.evidence[0].correct is False


def test_absent_quote_is_missing_not_hallucinated():
    """EVAL.md amendment 2026-08-30. The baseline is never asked for evidence,
    so counting silence as fabrication would overstate the agent's advantage."""
    m = match_posting(_pred(blockers=[("years_of_experience", "")]), GOLD, POSTING)
    assert m.missing_evidence == [0]
    assert m.hallucinated == []
    assert m.evidence[0].quoted is False


def test_hallucination_counted_inside_a_false_positive():
    """Fabrication must be caught even when the claim was wrong anyway."""
    m = match_posting(_pred(blockers=[("degree_required", "A PhD is required.")]), GOLD, POSTING)
    assert m.false_positives == [0]
    assert m.hallucinated == [0]


# ─── verdicts and parse failures ──────────────────────────────────────────

def test_caveat_verdict_scores_as_apply():
    clean = {"id": "jd_clean", "expected_verdict": "APPLY", "blockers": []}
    m = match_posting(_pred(verdict="APPLY_WITH_CAVEAT"), clean, POSTING)
    assert m.predicted_verdict == "APPLY" and m.verdict_correct


def test_unparseable_output_misses_everything():
    m = match_posting(Prediction.unparseable("no JSON"), GOLD, POSTING)
    assert m.false_negatives == [0]
    assert m.parse_error == "no JSON"
    assert not m.verdict_correct, "an unreadable answer must not score as SKIP"


# ─── against the real corpus ──────────────────────────────────────────────

def test_a_perfect_prediction_scores_perfectly_on_every_posting():
    """If the answer key cannot score itself, nothing downstream is trustworthy."""
    for record in LABELS:
        text = (CORPUS / f"{record['id']}.md").read_text()
        perfect = Prediction(
            verdict=record["expected_verdict"],
            blockers=[Claim(b["type"], b["sentence"]) for b in record["blockers"]],
        )
        m = match_posting(perfect, record, text)
        assert not m.false_positives, record["id"]
        assert not m.false_negatives, record["id"]
        assert not m.hallucinated, record["id"]
        assert all(e.correct for e in m.evidence), record["id"]
        assert m.verdict_correct, record["id"]
