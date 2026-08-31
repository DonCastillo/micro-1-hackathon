"""The baseline: one direct prompt, one pass, no help.

    python -m src.baseline.run --dry-run          # print the prompt, spend nothing
    python -m src.baseline.run --out runs/baseline

This is what a person would actually type into a chat window, and it is
deliberately not improved. EVAL.md 9 allows the *parse layer* to adapt to
whatever comes back but forbids touching the prompt to make output easier to
read — tuning the baseline's reasoning would inflate the number every later
iteration is measured against.

What it gets: the posting, the profile, and the 14 blocker ids as bare names
(EVAL.md amendment 2026-08-30 — without them it cannot name a blocker the
scorer recognises, and its recall would be zero before the first call).

What it does not get: what those ids mean, how they relate to the profile,
per-category decomposition, a verification pass, a structured output schema,
or any instruction to quote evidence. Those are the iterations.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from src import llm
from src.rules import load_profile, load_taxonomy
from src.schema import Claim, ParseError, Prediction
from src.trajectory import Recorder

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "data/corpus"

SYSTEM = "You are helping someone decide which jobs are worth applying to."

PROMPT = """\
Here is my background:

{profile}

Here is a job posting:

{posting}

Should I apply? If anything in this posting disqualifies me, tell me what.

End your answer with two lines exactly:

VERDICT: APPLY or SKIP
BLOCKERS: comma-separated labels from the list below, or NONE

The labels:
{labels}
"""

_VERDICT_LINE = re.compile(r"^\s*\**verdict\**\s*[:\-]\s*\**\s*(apply|skip)\b", re.I | re.M)
_BLOCKERS_LINE = re.compile(r"^\s*\**blockers?\**\s*[:\-]\s*(.+)$", re.I | re.M)

# Fallback only, for answers that ignore the format. Ordered most specific
# first: "do not apply" must win before the bare word "apply" is considered.
_SKIP_PATTERNS = (
    r"\bdo not apply\b",
    r"\bdon'?t apply\b",
    r"\bshould not apply\b",
    r"\bnot worth applying\b",
    r"\bwould not apply\b",
    r"\bskip\b",
    r"\bnot eligible\b",
    r"\bdisqualif",
)
_APPLY_PATTERNS = (
    r"\byou (?:should|can) apply\b",
    r"\bworth applying\b",
    r"\bgo ahead and apply\b",
    r"\bnothing (?:here )?disqualif",
    r"\bno (?:hard )?blockers?\b",
    r"\byes,? apply\b",
    r"\bapply\b",
)


def build_prompt(posting: str, profile: dict[str, Any], labels: list[str]) -> str:
    return PROMPT.format(
        profile=yaml.safe_dump(profile, sort_keys=False).strip(),
        posting=posting.strip(),
        labels="\n".join(f"- {label}" for label in labels),
    )


def parse_baseline_output(text: str, known_types: list[str]) -> Prediction:
    """Map freeform prose onto the shared schema.

    Extraction only. It finds the verdict the model stated and the labels the
    model named; it never infers a blocker the model did not mention, which
    would be the parse layer doing the baseline's work for it.
    """
    # Prefer the declared lines. Scanning the whole answer misreads it badly:
    # "No hard disqualifiers found" parsed as SKIP because a skip pattern
    # matched under a negation, and "your 6 years of experience clears the 5+
    # requirement" claimed a years_of_experience blocker from a sentence saying
    # the requirement was *satisfied*.
    verdict_match = _VERDICT_LINE.search(text)
    blockers_match = _BLOCKERS_LINE.search(text)

    if verdict_match:
        verdict = verdict_match.group(1).upper()
    else:
        verdict = _verdict_from_prose(text)

    # Only the declared BLOCKERS line counts as a claim. A label discussed in
    # the body ("worth verifying their sponsorship policy") is commentary, not
    # a claim, and counting it would invent findings the model never made.
    source = blockers_match.group(1) if blockers_match else ""
    if re.search(r"\bnone\b", source, re.I):
        source = ""

    named = []
    for blocker_id in known_types:
        pattern = re.escape(blocker_id).replace("_", r"[\s_-]")
        if re.search(rf"\b{pattern}\b", source, re.I):
            named.append(Claim(blocker_id, ""))

    return Prediction(verdict=verdict, blockers=named)


def _verdict_from_prose(text: str) -> str:
    """Used only when the answer ignored the requested format.

    Earliest signal wins rather than SKIP taking precedence, so a negated
    mention ("nothing here disqualifies you") does not flip the verdict.
    """
    lowered = text.lower()
    skip_at = min(
        (m.start() for p in _SKIP_PATTERNS if (m := re.search(p, lowered))), default=None
    )
    apply_at = min(
        (m.start() for p in _APPLY_PATTERNS if (m := re.search(p, lowered))), default=None
    )
    if skip_at is None and apply_at is None:
        raise ParseError("no verdict found in baseline output")
    if apply_at is None:
        return "SKIP"
    if skip_at is None:
        return "APPLY"
    return "SKIP" if skip_at <= apply_at else "APPLY"


def load_corpus(corpus: Path) -> list[tuple[str, str]]:
    labels = yaml.safe_load((corpus / "labels.yaml").read_text())["postings"]
    return [(r["id"], (corpus / f"{r['id']}.md").read_text()) for r in labels]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, help="directory for predictions.json")
    parser.add_argument("--dry-run", action="store_true", help="print one prompt, call nothing")
    parser.add_argument("--limit", type=int, help="only the first N postings (smoke runs)")
    parser.add_argument("--runs", type=Path, help="where to write trajectories (default runs/)")
    args = parser.parse_args()

    profile = load_profile()
    blocker_ids = sorted(b["id"] for b in load_taxonomy()["blockers"])
    postings = load_corpus(args.corpus)
    if args.limit:
        postings = postings[: args.limit]

    if args.dry_run:
        posting_id, text = postings[0]
        print(f"=== system ===\n{SYSTEM}\n")
        print(f"=== user ({posting_id}) ===")
        print(build_prompt(text, profile, blocker_ids))
        print(f"=== model: {llm.model_id()}  effort: {llm.effort()} ===")
        return

    recorder = Recorder("baseline", corpus=args.corpus, root=args.runs)
    predictions: dict[str, Any] = {}

    for posting_id, text in postings:
        traj = recorder.trajectory(posting_id)
        response = traj.call("ask", SYSTEM, build_prompt(text, profile, blocker_ids))
        try:
            prediction = parse_baseline_output(response.text, blocker_ids)
        except ParseError as exc:
            prediction = Prediction.unparseable(str(exc))
            traj.note("parse_failure", f"could not read a verdict: {exc}")

        predictions[posting_id] = prediction.to_dict()
        recorder.finish(traj, prediction.to_dict())

        flag = "!" if prediction.parse_error else " "
        print(f"{flag} {posting_id}  {prediction.verdict:6} "
              f"{len(prediction.blockers)} blockers  ${recorder.total.cost_usd:.4f}")

    recorder.write_manifest()
    print(f"\ntrajectories: {recorder.dir}")

    payload = {
        "system": "baseline",
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
