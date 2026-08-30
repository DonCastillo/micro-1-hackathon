"""Turn per-posting matches into the numbers the report quotes. EVAL.md 4-5.

Micro-averaged: TP/FP/FN are pooled across all 24 postings and the rates
computed once from the pool, rather than averaging 24 per-posting rates. With
one or two blockers per posting, per-posting averaging would let a single
posting with one blocker weigh as heavily as one with two, and a miss on a
multi-blocker posting would cost less than a miss on a single.

Zero-denominator conventions come from EVAL.md 4 for precision/recall/F1. The
evidence rates report None when there were no true positives to score, and
render as "n/a" — a system that detected nothing has no citation quality,
and printing 0.0 there would read as "cites badly" rather than "never cited".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.eval.match import PostingMatch


def _rate(numerator: int, denominator: int, empty: float | None = None) -> float | None:
    return empty if denominator == 0 else numerator / denominator


@dataclass
class Metrics:
    # Detection, pooled over every blocker instance in the corpus.
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 1.0
    recall: float = 1.0
    f1: float = 0.0

    # Secondary (EVAL.md 5).
    clean_false_alarm_rate: float | None = None
    decision_accuracy: float = 0.0
    evidence_found_rate: float | None = None
    evidence_correct_rate: float | None = None
    hallucination_rate: float | None = None
    missing_evidence_rate: float | None = None
    parse_failure_rate: float = 0.0

    # Denominators, so a reader can check the arithmetic.
    n_postings: int = 0
    n_clean: int = 0
    n_claims: int = 0
    n_clean_flagged: int = 0

    # Diagnostics: not headline numbers, but they say which iteration to write.
    recall_by_type: dict[str, tuple[int, int]] = field(default_factory=dict)
    recall_by_style: dict[str, tuple[int, int]] = field(default_factory=dict)
    recall_by_bucket: dict[str, tuple[int, int]] = field(default_factory=dict)

    cost_usd: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_per_task(self) -> float | None:
        if self.cost_usd is None or not self.n_postings:
            return None
        return self.cost_usd / self.n_postings


def aggregate(
    matches: list[PostingMatch],
    gold_by_id: dict[str, dict[str, Any]],
    cost_usd: float | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> Metrics:
    if not matches:
        # EVAL.md 4's conventions (precision 1.0 and recall 1.0 when their
        # denominators are zero) compose to F1 = 1.0 here, so a run that
        # crashed before scoring anything would report a perfect score. An
        # empty aggregate is a failure upstream, not a result.
        raise ValueError("cannot aggregate zero matches; the run produced no scored postings")

    m = Metrics(
        n_postings=len(matches),
        cost_usd=cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    hit_by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    hit_by_style: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    hit_by_bucket: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    correct_verdicts = parse_failures = 0
    found = correct = hallucinated = missing = 0

    for match in matches:
        gold = gold_by_id[match.posting_id]
        gold_blockers = gold.get("blockers") or []
        bucket = gold.get("bucket", "unknown")

        m.tp += len(match.true_positives)
        m.fp += len(match.false_positives)
        m.fn += len(match.false_negatives)
        m.n_claims += len(match.true_positives) + len(match.false_positives)

        correct_verdicts += match.verdict_correct
        parse_failures += match.parse_error is not None

        if not gold_blockers:
            m.n_clean += 1
            m.n_clean_flagged += match.flagged_anything

        # Per-gold-blocker outcome, for the diagnostics.
        caught = {gold_index for _, gold_index in match.true_positives}
        for gold_index, gold_blocker in enumerate(gold_blockers):
            was_caught = int(gold_index in caught)
            for table, key in (
                (hit_by_type, gold_blocker["type"]),
                (hit_by_style, gold_blocker["phrasing"]),
                (hit_by_bucket, bucket),
            ):
                table[key][0] += was_caught
                table[key][1] += 1

        for check in match.evidence:
            found += check.found
            correct += check.correct
        hallucinated += len(match.hallucinated)
        missing += len(match.missing_evidence)

    m.precision = _rate(m.tp, m.tp + m.fp, empty=1.0)
    m.recall = _rate(m.tp, m.tp + m.fn, empty=1.0)
    m.f1 = (
        0.0
        if (m.precision + m.recall) == 0
        else 2 * m.precision * m.recall / (m.precision + m.recall)
    )

    m.decision_accuracy = _rate(correct_verdicts, m.n_postings, empty=0.0)
    m.parse_failure_rate = _rate(parse_failures, m.n_postings, empty=0.0)
    m.clean_false_alarm_rate = _rate(m.n_clean_flagged, m.n_clean)
    m.evidence_found_rate = _rate(found, m.tp)
    m.evidence_correct_rate = _rate(correct, m.tp)
    m.hallucination_rate = _rate(hallucinated, m.n_claims)
    m.missing_evidence_rate = _rate(missing, m.n_claims)

    m.recall_by_type = {k: tuple(v) for k, v in sorted(hit_by_type.items())}
    m.recall_by_style = {k: tuple(v) for k, v in sorted(hit_by_style.items())}
    m.recall_by_bucket = {k: tuple(v) for k, v in sorted(hit_by_bucket.items())}
    return m


# ─── rendering ────────────────────────────────────────────────────────────

def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def to_markdown(m: Metrics, title: str = "Results") -> str:
    """A single run, as a table the changelog can take verbatim."""
    lines = [
        f"### {title}",
        "",
        "| Metric | Value | Basis |",
        "|---|---|---|",
        f"| **Detection F1** | **{_num(m.f1)}** | {m.tp} TP, {m.fp} FP, {m.fn} FN |",
        f"| Recall | {_num(m.recall)} | {m.tp}/{m.tp + m.fn} blockers found |",
        f"| Precision | {_num(m.precision)} | {m.tp}/{m.tp + m.fp} claims correct |",
        f"| Clean-posting false alarms | {_pct(m.clean_false_alarm_rate)} | "
        f"{m.n_clean_flagged}/{m.n_clean} clean postings flagged |",
        f"| Decision accuracy | {_pct(m.decision_accuracy)} | over {m.n_postings} postings |",
        f"| Evidence found | {_pct(m.evidence_found_rate)} | of {m.tp} true positives |",
        f"| Evidence correct | {_pct(m.evidence_correct_rate)} | of {m.tp} true positives |",
        f"| Hallucinated quotes | {_pct(m.hallucination_rate)} | of {m.n_claims} claims |",
        f"| Missing evidence | {_pct(m.missing_evidence_rate)} | of {m.n_claims} claims |",
        f"| Parse failures | {_pct(m.parse_failure_rate)} | of {m.n_postings} postings |",
    ]
    if m.cost_per_task is not None:
        lines.append(
            f"| Cost per task | ${m.cost_per_task:.4f} | "
            f"${m.cost_usd:.2f} total, {m.input_tokens:,} in / {m.output_tokens:,} out |"
        )
    return "\n".join(lines)


def _breakdown(table: dict[str, tuple[int, int]], heading: str) -> str:
    rows = [f"| {heading} | Recall | Found |", "|---|---|---|"]
    for key, (hit, total) in sorted(table.items(), key=lambda kv: (kv[1][0] / kv[1][1], kv[0])):
        rows.append(f"| {key} | {hit / total:.0%} | {hit}/{total} |")
    return "\n".join(rows)


def diagnostics_markdown(m: Metrics) -> str:
    """Not headline numbers — this is what tells you which iteration to write."""
    return "\n\n".join(
        [
            "### Diagnostics",
            "_Sorted worst first: the top row is the next thing to fix._",
            _breakdown(m.recall_by_style, "Phrasing style"),
            _breakdown(m.recall_by_bucket, "Bucket"),
            _breakdown(m.recall_by_type, "Blocker type"),
        ]
    )


def _delta(before: float | None, after: float | None, as_pct: bool) -> str:
    if before is None or after is None:
        return "n/a"
    change = after - before
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1%}" if as_pct else f"{sign}{change:.3f}"


def comparison_markdown(
    baseline: Metrics,
    final: Metrics,
    baseline_label: str = "Simple baseline",
    final_label: str = "Agent solution",
) -> str:
    """Baseline vs final, in the format the brief asks for."""
    rows: list[tuple[str, Any, Any, bool]] = [
        ("Detection F1 (primary)", baseline.f1, final.f1, False),
        ("Recall", baseline.recall, final.recall, False),
        ("Precision", baseline.precision, final.precision, False),
        ("Clean-posting false alarms", baseline.clean_false_alarm_rate,
         final.clean_false_alarm_rate, True),
        ("Decision accuracy", baseline.decision_accuracy, final.decision_accuracy, True),
        ("Evidence correct", baseline.evidence_correct_rate, final.evidence_correct_rate, True),
        ("Hallucinated quotes", baseline.hallucination_rate, final.hallucination_rate, True),
        ("Parse failures", baseline.parse_failure_rate, final.parse_failure_rate, True),
    ]

    lines = [f"| Metric | {baseline_label} | {final_label} | Change |", "|---|---|---|---|"]
    for label, before, after, as_pct in rows:
        render = _pct if as_pct else _num
        lines.append(f"| {label} | {render(before)} | {render(after)} | {_delta(before, after, as_pct)} |")

    if baseline.cost_per_task is not None and final.cost_per_task is not None:
        lines.append(
            f"| Cost per task | ${baseline.cost_per_task:.4f} | "
            f"${final.cost_per_task:.4f} | "
            f"{'+' if final.cost_per_task >= baseline.cost_per_task else ''}"
            f"${final.cost_per_task - baseline.cost_per_task:.4f} |"
        )
    return "\n".join(lines)


def metrics_to_dict(m: Metrics) -> dict[str, Any]:
    """JSON-safe form, so a run's numbers can be compared later without rerunning."""
    from dataclasses import asdict

    out = asdict(m)
    out["cost_per_task"] = m.cost_per_task
    for key in ("recall_by_type", "recall_by_style", "recall_by_bucket"):
        out[key] = {k: list(v) for k, v in getattr(m, key).items()}
    return out


def metrics_from_dict(data: dict[str, Any]) -> Metrics:
    fields = {f for f in Metrics.__dataclass_fields__}
    m = Metrics(**{k: v for k, v in data.items() if k in fields})
    for key in ("recall_by_type", "recall_by_style", "recall_by_bucket"):
        setattr(m, key, {k: tuple(v) for k, v in getattr(m, key).items()})
    return m
