"""Run an agent variant over the corpus.

    python -m src.agent.run --variant iter1 --dry-run
    python -m src.agent.run --variant iter1 --out results/iter1

Deliberately the same shape as `src.baseline.run`: same corpus, same profile,
same trajectory recorder, same predictions.json, scored by the same harness.
The only thing that differs between the baseline and any variant is the
variant itself, which is what EVAL.md 9 requires.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from src import llm
from src.agent.variants import VARIANTS
from src.rules import load_profile, load_taxonomy
from src.trajectory import Recorder

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "data/corpus"


def load_corpus(corpus: Path) -> list[tuple[str, str]]:
    labels = yaml.safe_load((corpus / "labels.yaml").read_text())["postings"]
    return [(r["id"], (corpus / f"{r['id']}.md").read_text()) for r in labels]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, help="directory for predictions.json")
    parser.add_argument("--runs", type=Path, help="where to write trajectories")
    parser.add_argument("--dry-run", action="store_true", help="print one prompt, call nothing")
    parser.add_argument("--limit", type=int, help="only the first N postings (smoke runs)")
    args = parser.parse_args()

    variant = VARIANTS[args.variant]
    profile = load_profile()
    taxonomy = load_taxonomy()
    postings = load_corpus(args.corpus)
    if args.limit:
        postings = postings[: args.limit]

    if args.dry_run:
        from src.trajectory import Trajectory

        class _Dry(Trajectory):
            def call(self, name, system, user, **kw):  # type: ignore[override]
                print(f"=== step: {name} ===\n{user}\n")
                raise SystemExit(0)

        print(f"=== variant: {variant.name} — {variant.description} ===")
        print(f"=== model: {llm.model_id()}  effort: {llm.effort()} ===\n")
        variant.predict(postings[0][1], profile, taxonomy, _Dry(posting_id=postings[0][0]))
        return

    recorder = Recorder(variant.name, corpus=args.corpus, root=args.runs)
    predictions: dict[str, Any] = {}

    for posting_id, text in postings:
        traj = recorder.trajectory(posting_id)
        prediction = variant.predict(text, profile, taxonomy, traj)
        predictions[posting_id] = prediction.to_dict()
        recorder.finish(traj, prediction.to_dict())

        flag = "!" if prediction.parse_error else " "
        print(f"{flag} {posting_id}  {prediction.verdict:6} "
              f"{len(prediction.blockers)} blockers  ${recorder.total.cost_usd:.4f}")

    recorder.write_manifest({"variant": variant.name, "description": variant.description})
    print(f"\ntrajectories: {recorder.dir}")

    payload = {
        "system": variant.name,
        "description": variant.description,
        "model": llm.model_id(),
        "effort": llm.effort(),
        "usage": recorder.total.to_dict(),
        "trajectories": str(recorder.dir),
        "predictions": predictions,
    }

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "predictions.json").write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote {args.out}/predictions.json  total ${recorder.total.cost_usd:.4f}")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
