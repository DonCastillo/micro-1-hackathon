"""Score a predictions file against the corpus. EVAL.md end to end.

    python -m src.eval.run --predictions runs/baseline/predictions.json --out results/baseline
    python -m src.eval.run --compare results/baseline results/final

Every system's output reaches this the same way — a JSON file of predictions
keyed by posting id — so the baseline and every agent variant are scored by
identical code, which is EVAL.md 9's fairness invariant made structural rather
than promised.

A posting with no prediction is scored as an unreadable answer, not skipped.
Dropping it would quietly shrink the denominator and inflate every rate: a
system that crashed on the eight hardest postings would score beautifully on
the sixteen it survived.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from src.eval.match import PostingMatch, match_posting
from src.eval.metrics import (
    Metrics,
    aggregate,
    comparison_markdown,
    diagnostics_markdown,
    metrics_from_dict,
    metrics_to_dict,
    to_markdown,
)
from src.schema import ParseError, Prediction, parse_prediction

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "data/corpus"


def load_labels(corpus: Path) -> list[dict[str, Any]]:
    return yaml.safe_load((corpus / "labels.yaml").read_text())["postings"]


def load_predictions(path: Path) -> tuple[dict[str, Prediction], dict[str, Any]]:
    """Read a predictions file, tolerating whatever shape the system emitted."""
    payload = json.loads(path.read_text())
    raw = payload.get("predictions", payload)

    predictions: dict[str, Prediction] = {}
    for posting_id, value in raw.items():
        try:
            predictions[posting_id] = parse_prediction(value)
        except ParseError as exc:
            predictions[posting_id] = Prediction.unparseable(str(exc))

    meta = {k: v for k, v in payload.items() if k != "predictions"}
    return predictions, meta


def score(
    predictions: dict[str, Prediction],
    labels: list[dict[str, Any]],
    corpus: Path,
    usage: dict[str, Any] | None = None,
) -> tuple[Metrics, list[PostingMatch]]:
    usage = usage or {}
    matches = []
    for record in labels:
        prediction = predictions.get(
            record["id"], Prediction.unparseable("no prediction recorded for this posting")
        )
        text = (corpus / f"{record['id']}.md").read_text()
        matches.append(match_posting(prediction, record, text))

    metrics = aggregate(
        matches,
        {r["id"]: r for r in labels},
        cost_usd=usage.get("cost_usd"),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )
    return metrics, matches


def _per_posting(matches: list[PostingMatch], labels: list[dict[str, Any]]) -> list[dict]:
    """Row per posting, so a surprising aggregate can be traced to its source."""
    gold = {r["id"]: r for r in labels}
    rows = []
    for m in matches:
        rows.append(
            {
                "id": m.posting_id,
                "bucket": gold[m.posting_id].get("bucket"),
                "gold_verdict": m.gold_verdict,
                "predicted_verdict": m.predicted_verdict,
                "verdict_correct": m.verdict_correct,
                "tp": len(m.true_positives),
                "fp": len(m.false_positives),
                "fn": len(m.false_negatives),
                "missed_types": [
                    gold[m.posting_id]["blockers"][i]["type"] for i in m.false_negatives
                ],
                "hallucinated": len(m.hallucinated),
                "missing_evidence": len(m.missing_evidence),
                "parse_error": m.parse_error,
            }
        )
    return rows


def write_results(
    out_dir: Path,
    metrics: Metrics,
    matches: list[PostingMatch],
    labels: list[dict[str, Any]],
    label: str,
    meta: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = to_markdown(metrics, title=label) + "\n\n" + diagnostics_markdown(metrics) + "\n"
    (out_dir / "metrics.md").write_text(report)
    (out_dir / "metrics.json").write_text(
        json.dumps({"label": label, "meta": meta, "metrics": metrics_to_dict(metrics)}, indent=2)
    )
    (out_dir / "per_posting.json").write_text(
        json.dumps(_per_posting(matches, labels), indent=2)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, help="predictions JSON to score")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, help="directory for metrics.md / .json")
    parser.add_argument("--label", default=None, help="title for the report table")
    parser.add_argument(
        "--compare", nargs=2, type=Path, metavar=("BASELINE", "FINAL"),
        help="two results directories to compare",
    )
    args = parser.parse_args()

    if args.compare:
        before, after = (
            json.loads((d / "metrics.json").read_text()) for d in args.compare
        )
        print(
            comparison_markdown(
                metrics_from_dict(before["metrics"]),
                metrics_from_dict(after["metrics"]),
                baseline_label=before.get("label", "Baseline"),
                final_label=after.get("label", "Final"),
            )
        )
        return

    if not args.predictions:
        parser.error("--predictions is required unless --compare is given")

    labels = load_labels(args.corpus)
    predictions, meta = load_predictions(args.predictions)
    label = args.label or meta.get("system") or args.predictions.stem

    missing = [r["id"] for r in labels if r["id"] not in predictions]
    if missing:
        print(f"warning: {len(missing)} postings have no prediction: {' '.join(missing)}")

    metrics, matches = score(predictions, labels, args.corpus, meta.get("usage"))

    print(to_markdown(metrics, title=label))
    print()
    print(diagnostics_markdown(metrics))

    if args.out:
        write_results(args.out, metrics, matches, labels, label, meta)
        print(f"\nwrote {args.out}/metrics.md, metrics.json, per_posting.json")


if __name__ == "__main__":
    main()
