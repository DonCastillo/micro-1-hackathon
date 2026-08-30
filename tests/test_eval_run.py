"""Step 3.4: the scorer sanity check, run end to end from files on disk.

A harness that has never been checked against a known answer will report a
wrong number with complete confidence, and every result downstream inherits
it. These three fixtures are the check, and they are committed so a judge can
rerun them:

    python -m src.eval.run --predictions tests/fixtures/sanity_perfect.json

Expected, from EVAL.md 4-5:
  perfect         F1 1.000, recall 1.000, no false alarms
  silent          recall 0, precision 1.000 (claimed nothing, so nothing wrong)
  flag_everything recall 1.000, F1 0.102, every clean posting flagged
"""

import json
from pathlib import Path

import pytest

from src.eval.metrics import metrics_from_dict, metrics_to_dict
from src.eval.run import CORPUS, load_labels, load_predictions, score, write_results
from src.schema import Prediction

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LABELS = load_labels(CORPUS)
N_BLOCKERS = sum(len(r["blockers"]) for r in LABELS)


def _score(name):
    predictions, meta = load_predictions(FIXTURES / f"{name}.json")
    return score(predictions, LABELS, CORPUS, meta.get("usage"))


# ─── the three reference fixtures ─────────────────────────────────────────

def test_perfect_prediction_scores_one():
    """If the answer key cannot score itself, nothing downstream is trustworthy."""
    m, _ = _score("sanity_perfect")
    assert m.f1 == 1.0
    assert m.recall == 1.0 and m.precision == 1.0
    assert m.tp == N_BLOCKERS and m.fp == 0 and m.fn == 0
    assert m.decision_accuracy == 1.0
    assert m.clean_false_alarm_rate == 0.0
    assert m.evidence_correct_rate == 1.0
    assert m.hallucination_rate == 0.0


def test_silent_prediction_scores_zero_recall_but_full_precision():
    m, _ = _score("sanity_silent")
    assert m.recall == 0.0 and m.f1 == 0.0
    assert m.precision == 1.0, "claiming nothing means nothing was claimed wrongly"
    assert m.fn == N_BLOCKERS
    assert m.clean_false_alarm_rate == 0.0
    assert m.decision_accuracy == pytest.approx(8 / 24)
    assert m.evidence_correct_rate is None


def test_flag_everything_earns_perfect_recall_and_a_terrible_f1():
    """The concrete reason the primary metric is F1 and not recall.

    Note the decision accuracy: 66.7%, earned purely by always saying SKIP on
    a corpus that is two-thirds SKIP. Verdict accuracy alone would make this
    look like a working tool.
    """
    m, _ = _score("sanity_flag_everything")
    assert m.recall == 1.0
    assert m.f1 < 0.2
    assert m.clean_false_alarm_rate == 1.0
    assert m.decision_accuracy == pytest.approx(16 / 24)
    assert m.missing_evidence_rate == 1.0, "it cites nothing"


def test_the_three_fixtures_are_ordered_as_expected():
    perfect, _ = _score("sanity_perfect")
    flag, _ = _score("sanity_flag_everything")
    silent, _ = _score("sanity_silent")
    assert perfect.f1 > flag.f1 > silent.f1


# ─── missing predictions must not shrink the denominator ──────────────────

def test_a_missing_prediction_on_a_blocked_posting_costs_recall():
    """Dropping it would inflate every rate.

    A system that crashed on the eight hardest postings would otherwise score
    beautifully on the sixteen it survived.
    """
    predictions, _ = load_predictions(FIXTURES / "sanity_perfect.json")
    dropped = next(r["id"] for r in LABELS if r["blockers"])
    del predictions[dropped]

    m, matches = score(predictions, LABELS, CORPUS)
    assert m.n_postings == 24, "the denominator must not shrink"
    assert next(x for x in matches if x.posting_id == dropped).parse_error
    assert m.parse_failure_rate == pytest.approx(1 / 24)
    assert m.f1 < 1.0, "its blockers must count as missed"


def test_an_unreadable_answer_is_never_a_correct_verdict():
    """Found by a failing test: dropping a *clean* posting left F1 untouched
    and still scored a correct verdict, because the fallback happened to be
    APPLY and APPLY was right. Free credit for emitting nothing legible."""
    predictions, _ = load_predictions(FIXTURES / "sanity_perfect.json")
    clean = next(r["id"] for r in LABELS if not r["blockers"])
    del predictions[clean]

    m, matches = score(predictions, LABELS, CORPUS)
    assert m.f1 == 1.0, "a clean posting has no blockers, so detection is unaffected"
    assert not next(x for x in matches if x.posting_id == clean).verdict_correct
    assert m.decision_accuracy == pytest.approx(23 / 24)


def test_unparseable_prediction_text_is_recorded_not_crashed(tmp_path):
    path = tmp_path / "garbage.json"
    path.write_text(json.dumps({"predictions": {"jd_01": "I think you should apply, honestly"}}))
    predictions, _ = load_predictions(path)
    assert predictions["jd_01"].parse_error
    assert predictions["jd_01"].blockers == []


def test_predictions_file_without_a_wrapper_key_still_loads(tmp_path):
    path = tmp_path / "bare.json"
    path.write_text(json.dumps({"jd_01": {"verdict": "SKIP", "blockers": [], "caveats": []}}))
    predictions, _ = load_predictions(path)
    assert predictions["jd_01"].verdict == "SKIP"


# ─── outputs ──────────────────────────────────────────────────────────────

def test_write_results_emits_the_three_artifacts(tmp_path):
    m, matches = _score("sanity_perfect")
    write_results(tmp_path, m, matches, LABELS, "Sanity", {"model": "none"})

    assert (tmp_path / "metrics.md").exists()
    assert "Detection F1" in (tmp_path / "metrics.md").read_text()

    saved = json.loads((tmp_path / "metrics.json").read_text())
    assert saved["metrics"]["f1"] == 1.0

    rows = json.loads((tmp_path / "per_posting.json").read_text())
    assert len(rows) == 24
    assert all(row["verdict_correct"] for row in rows)


def test_per_posting_names_the_missed_blocker_types():
    """A surprising aggregate has to be traceable to the postings that caused it."""
    predictions, _ = load_predictions(FIXTURES / "sanity_silent.json")
    _, matches = score(predictions, LABELS, CORPUS)
    from src.eval.run import _per_posting

    rows = _per_posting(matches, LABELS)
    blocked = [r for r in rows if r["gold_verdict"] == "SKIP"]
    assert all(row["missed_types"] for row in blocked)


def test_metrics_survive_a_json_round_trip():
    """The comparison step reads these back rather than rerunning."""
    m, _ = _score("sanity_perfect")
    again = metrics_from_dict(json.loads(json.dumps(metrics_to_dict(m))))
    assert again.f1 == m.f1
    assert again.recall_by_style == m.recall_by_style
