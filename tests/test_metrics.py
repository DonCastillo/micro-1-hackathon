"""Aggregation is where a plausible-looking wrong number comes from.

Every arithmetic rule in EVAL.md 4-5 is pinned here against a hand-computed
expectation, because a metric that is merely self-consistent will still be
reported with total confidence.
"""

import pytest
import yaml
from pathlib import Path

from src.eval.match import match_posting
from src.eval.metrics import aggregate, comparison_markdown, diagnostics_markdown, to_markdown
from src.schema import Claim, Prediction

CORPUS = Path(__file__).resolve().parent.parent / "data/corpus"
LABELS = yaml.safe_load((CORPUS / "labels.yaml").read_text())["postings"]
GOLD_BY_ID = {record["id"]: record for record in LABELS}


def _run(build_prediction) -> "tuple":
    """Score a whole-corpus strategy. `build_prediction(record) -> Prediction`."""
    matches = []
    for record in LABELS:
        text = (CORPUS / f"{record['id']}.md").read_text()
        matches.append(match_posting(build_prediction(record), record, text))
    return aggregate(matches, GOLD_BY_ID)


def _perfect(record):
    return Prediction(
        verdict=record["expected_verdict"],
        blockers=[Claim(b["type"], b["sentence"]) for b in record["blockers"]],
    )


def _silent(record):
    return Prediction(verdict="APPLY")


def _flag_everything(record):
    """Names every blocker type on every posting: perfect recall, useless."""
    types = sorted({b["type"] for r in LABELS for b in r["blockers"]})
    return Prediction(verdict="SKIP", blockers=[Claim(t, "") for t in types])


# ─── the three reference strategies ───────────────────────────────────────

def test_perfect_prediction_scores_perfectly():
    m = _run(_perfect)
    assert m.f1 == 1.0
    assert m.recall == 1.0 and m.precision == 1.0
    assert m.decision_accuracy == 1.0
    assert m.clean_false_alarm_rate == 0.0
    assert m.evidence_correct_rate == 1.0
    assert m.hallucination_rate == 0.0
    assert m.fn == 0 and m.fp == 0


def test_silent_prediction_finds_nothing():
    m = _run(_silent)
    assert m.recall == 0.0
    assert m.tp == 0
    assert m.precision == 1.0, "claiming nothing means nothing was wrongly claimed"
    assert m.f1 == 0.0
    assert m.clean_false_alarm_rate == 0.0, "it also never cried wolf"
    # 8 clean postings correct, 16 blocked ones wrong.
    assert m.decision_accuracy == pytest.approx(8 / 24)
    assert m.evidence_correct_rate is None, "no true positives to judge citations on"


def test_flag_everything_gets_perfect_recall_and_is_still_bad():
    """The reason F1 is the primary metric and recall is not."""
    m = _run(_flag_everything)
    assert m.recall == 1.0
    assert m.clean_false_alarm_rate == 1.0, "every clean posting flagged"
    assert m.precision < 0.1
    assert m.f1 < 0.2, "F1 must punish what recall alone rewards"


# ─── arithmetic, hand-checked ─────────────────────────────────────────────

def test_micro_averaging_pools_across_postings():
    """One posting's blocker found, another's missed: 1 TP + 1 FN overall."""
    blocked = [r for r in LABELS if r["blockers"]][:2]
    matches = []
    for i, record in enumerate(blocked):
        text = (CORPUS / f"{record['id']}.md").read_text()
        blockers = (
            [Claim(record["blockers"][0]["type"], record["blockers"][0]["sentence"])]
            if i == 0
            else []
        )
        matches.append(
            match_posting(Prediction(verdict="SKIP", blockers=blockers), record, text)
        )
    m = aggregate(matches, GOLD_BY_ID)
    assert m.tp == 1
    assert m.fn == len(blocked[1]["blockers"])
    assert m.recall == pytest.approx(1 / (1 + m.fn))


def test_f1_is_the_harmonic_mean():
    m = _run(_flag_everything)
    expected = 2 * m.precision * m.recall / (m.precision + m.recall)
    assert m.f1 == pytest.approx(expected)


def test_denominators_are_reported_for_checking():
    m = _run(_perfect)
    assert m.n_postings == 24
    assert m.n_clean == 8
    assert m.tp + m.fn == sum(len(r["blockers"]) for r in LABELS)


def test_empty_aggregate_is_refused_rather_than_scored():
    """EVAL.md 4's zero-denominator conventions compose to F1 = 1.0 on an empty
    run, so a crash before scoring would report a perfect result. Refusing is
    the only safe reading: no postings scored is a failure, not a score."""
    with pytest.raises(ValueError, match="zero matches"):
        aggregate([], {})


def test_cost_per_task_divides_by_postings():
    matches = [match_posting(_perfect(r), r, (CORPUS / f"{r['id']}.md").read_text())
               for r in LABELS]
    m = aggregate(matches, GOLD_BY_ID, cost_usd=2.40, input_tokens=1000, output_tokens=200)
    assert m.cost_per_task == pytest.approx(0.10)


def test_parse_failures_are_counted():
    matches = [
        match_posting(Prediction.unparseable("bad"), r, (CORPUS / f"{r['id']}.md").read_text())
        for r in LABELS
    ]
    m = aggregate(matches, GOLD_BY_ID)
    assert m.parse_failure_rate == 1.0
    assert m.recall == 0.0


# ─── diagnostics ──────────────────────────────────────────────────────────

def test_diagnostics_cover_every_style_and_bucket():
    m = _run(_perfect)
    assert set(m.recall_by_style) >= {"explicit", "indirect", "footer"}
    assert set(m.recall_by_bucket) == {"injected", "contradiction", "multi"}
    assert "clean" not in m.recall_by_bucket, "clean postings have no blockers to recall"


def test_diagnostics_isolate_a_targeted_weakness():
    """Miss only footer-phrased blockers; the breakdown must say so."""

    def footer_blind(record):
        return Prediction(
            verdict=record["expected_verdict"],
            blockers=[
                Claim(b["type"], b["sentence"])
                for b in record["blockers"]
                if b["phrasing"] != "footer"
            ],
        )

    m = _run(footer_blind)
    assert m.recall_by_style["footer"][0] == 0, "no footer blockers found"
    assert m.recall_by_style["explicit"][0] == m.recall_by_style["explicit"][1]


# ─── rendering ────────────────────────────────────────────────────────────

def test_markdown_table_is_well_formed():
    out = to_markdown(_run(_perfect), title="Baseline")
    assert out.startswith("### Baseline")
    assert "| **Detection F1** | **1.000** |" in out
    assert out.count("\n|") >= 10


def test_markdown_renders_undefined_rates_as_na():
    out = to_markdown(_run(_silent))
    assert "n/a" in out, "evidence rates are undefined with zero true positives"


def test_comparison_table_shows_direction_of_change():
    baseline, final = _run(_silent), _run(_perfect)
    out = comparison_markdown(baseline, final)
    assert "| Detection F1 (primary) | 0.000 | 1.000 | +1.000 |" in out
    assert "Simple baseline" in out and "Agent solution" in out


def test_comparison_marks_a_regression_with_a_minus():
    out = comparison_markdown(_run(_perfect), _run(_silent))
    assert "-1.000" in out


def test_diagnostics_sort_worst_first():
    """The top row should be the next thing to work on."""

    def footer_blind(record):
        return Prediction(
            verdict=record["expected_verdict"],
            blockers=[
                Claim(b["type"], b["sentence"])
                for b in record["blockers"]
                if b["phrasing"] != "footer"
            ],
        )

    out = diagnostics_markdown(_run(footer_blind))
    style_section = out.split("| Phrasing style |")[1]
    assert style_section.splitlines()[2].startswith("| footer |")
