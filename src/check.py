"""Check a job posting against your profile.

    python -m src.check posting.txt
    python -m src.check data/corpus/jd_*.md
    cat posting.txt | python -m src.check -

The product. Everything else in this repository exists to make this output
trustworthy; this is the part a person reads.

Two design constraints, both taken from the human-time measurement (EVAL.md §7):
a verdict must be **scannable in about two seconds** and **checkable in about
ten**. That is why every blocker carries the posting's own sentence and a short
line saying which part of your profile it collides with — the reviewer in that
measurement never once reopened a posting to check, which is the only reason
the time saving is real rather than deferred.

The "why it applies to you" lines are generated from the profile, not by the
model. They cost nothing, cannot hallucinate, and say the half of the
comparison the quoted sentence does not.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from src import llm
from src.agent.variants import VARIANTS
from src.rules import load_profile, load_taxonomy
from src.schema import Prediction
from src.trajectory import Trajectory

ROOT = Path(__file__).resolve().parent.parent

# How each condition collides with *your* profile. The quoted sentence gives
# the posting's side of the comparison; this gives yours.
WHY: dict[str, Any] = {
    "work_authorization": lambda p: "You need visa sponsorship.",
    "citizenship_required": lambda p: f"You hold {p['citizenship']} citizenship, not US.",
    "security_clearance": lambda p: "You don't hold a security clearance.",
    "professional_licensure": lambda p: "You don't hold that licence.",
    "onsite_location": lambda p: (
        f"You're in {p['location']['city']} and not open to relocating."
        if not p["willing_to_relocate"]
        else f"You're in {p['location']['city']}."
    ),
    "relocation_required": lambda p: "You're not open to relocating.",
    "timezone_overlap": lambda p: f"You work from {p['timezone']}.",
    "travel_percentage": lambda p: f"You cap travel at {p['max_travel_pct']}%.",
    "shift_oncall": lambda p: "You don't take overnight or weekend shifts.",
    "degree_required": lambda p: f"Your highest degree is a {p['degree']}.",
    "certification_required": lambda p: "You don't hold that certification.",
    "years_of_experience": lambda p: f"You have {p['years_experience']} years.",
    "employment_type": lambda p: f"You're looking for {p['employment_types'][0].lower()} roles.",
    "compensation_floor": lambda p: f"Your minimum is ${p['comp_floor']:,}.",
}


class Style:
    """ANSI codes, disabled when output is piped."""

    def __init__(self, enabled: bool) -> None:
        self.on = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def bold(self, t): return self._wrap("1", t)
    def dim(self, t): return self._wrap("2", t)
    def red(self, t): return self._wrap("31", t)
    def green(self, t): return self._wrap("32", t)
    def yellow(self, t): return self._wrap("33", t)


def title_of(posting: str) -> tuple[str, str]:
    """Role and location from the posting's first two lines."""
    lines = [ln.strip() for ln in posting.strip().splitlines()]
    role = lines[0].lstrip("# ").strip() if lines else "Untitled role"
    location = lines[1] if len(lines) > 1 and not lines[1].startswith("#") else ""
    return role, location


def render(
    posting: str,
    prediction: Prediction,
    profile: dict[str, Any],
    taxonomy: dict[str, Any],
    elapsed: float,
    cost: float,
    s: Style,
) -> str:
    role, location = title_of(posting)
    n_conditions = len(taxonomy["blockers"])
    out: list[str] = []

    # Padded to a common width so the title and location align under both.
    if prediction.blockers:
        badge = s.red(s.bold(" SKIP  "))
    else:
        badge = s.green(s.bold(" APPLY "))

    out += ["", f"{badge}  {s.bold(role)}"]
    if location:
        out.append(f"{' ' * 9}{s.dim(location)}")
    out.append("")

    if prediction.blockers:
        for claim in prediction.blockers:
            label = claim.type.replace("_", " ").capitalize()
            out.append(f"  {s.red('✗')}  {s.bold(label)}")
            out.append(f'     {s.yellow(chr(34) + claim.evidence.strip() + chr(34))}')
            why = WHY.get(claim.type)
            if why:
                out.append(f"     {s.dim(why(profile))}")
            out.append("")
    else:
        out += [f"  {s.green('✓')}  Nothing here disqualifies you.", ""]

    found = len(prediction.blockers)
    summary = (
        f"{n_conditions} conditions checked · "
        f"{found} blocker{'' if found == 1 else 's'} · "
        f"{elapsed:.1f}s · ${cost:.4f}"
    )
    out += [s.dim(f"  {summary}"), ""]
    return "\n".join(out)


def check_one(posting: str, profile: dict, taxonomy: dict) -> tuple[Prediction, float, float]:
    traj = Trajectory(posting_id="check")
    began = time.monotonic()
    prediction = VARIANTS["final"].predict(posting, profile, taxonomy, traj)
    return prediction, time.monotonic() - began, traj.usage.cost_usd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postings", nargs="+", help="posting files, or - for stdin")
    parser.add_argument("--profile", type=Path, help="candidate profile YAML")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    profile = (
        yaml.safe_load(args.profile.read_text()) if args.profile else load_profile()
    )
    taxonomy = load_taxonomy()
    s = Style(enabled=sys.stdout.isatty() and not args.no_color and not args.json)

    results, total_cost, total_time = [], 0.0, 0.0
    for name in args.postings:
        posting = sys.stdin.read() if name == "-" else Path(name).read_text()
        prediction, elapsed, cost = check_one(posting, profile, taxonomy)
        total_cost += cost
        total_time += elapsed
        results.append((name, posting, prediction))

        if args.json:
            print(json.dumps({"source": name, **prediction.to_dict()}, indent=2))
        else:
            print(render(posting, prediction, profile, taxonomy, elapsed, cost, s))

    # A run over several postings ends with the thing you actually wanted:
    # which ones are worth your time.
    if len(results) > 1 and not args.json:
        worth_it = [r for r in results if not r[2].blockers]
        print(s.bold("  Summary"))
        print(f"  {s.dim('─' * 60)}")
        for name, posting, prediction in results:
            role, _ = title_of(posting)
            mark = s.red("SKIP ") if prediction.blockers else s.green("APPLY")
            reasons = ", ".join(c.type.replace("_", " ") for c in prediction.blockers)
            print(f"  {mark}  {role[:44]:44} {s.dim(reasons)}")
        print()
        print(
            f"  {s.bold(str(len(worth_it)))} of {len(results)} worth applying to · "
            f"{s.dim(f'{total_time:.0f}s · ${total_cost:.4f}')}"
        )
        print()


if __name__ == "__main__":
    main()
