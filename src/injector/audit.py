"""Render the corpus beside its answer key, for human review.

    python -m src.injector.audit            # compact: headers + injected spans
    python -m src.injector.audit --full     # whole postings, spans highlighted
    python -m src.injector.audit --id jd_14

Step 2.6 asks for a spot-read, and it is the only check in the pipeline that
is independent of the code. The tests verify that the labels are *consistent*
with the generator; only a person can verify they are *true* — that a sentence
labelled `security_clearance` is really about clearance, that a clean posting
really is one, that a contradiction really contradicts.

Cross-referencing two files by hand does not survive 24 postings, so this puts
them side by side.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from src.injector.contradiction import is_remote_base
from src.rules import load_profile

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "data/corpus"

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
MARK = "\033[7m"  # reverse video: works on light and dark terminals
RED, GREEN, YELLOW = "\033[31m", "\033[32m", "\033[33m"


def _highlight(text: str, spans: list[tuple[int, int]]) -> str:
    out, cursor = [], 0
    for start, end in sorted(spans):
        out.append(text[cursor:start])
        out.append(f"{MARK}{text[start:end]}{RESET}")
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _context(text: str, span: tuple[int, int], width: int = 90) -> str:
    start, end = span
    before = text[max(0, start - width) : start].replace("\n", " ").strip()
    after = text[end : end + 40].replace("\n", " ").strip()
    return f"{DIM}...{before}{RESET}\n      {MARK}{text[start:end]}{RESET}\n      {DIM}{after}...{RESET}"


def audit(record: dict, text: str, full: bool) -> list[str]:
    """Print one posting; return any warnings worth a second look."""
    warnings: list[str] = []
    verdict = record["expected_verdict"]
    colour = RED if verdict == "SKIP" else GREEN
    header = text.splitlines()[1]

    print(
        f"\n{BOLD}{record['id']}{RESET}  {colour}{verdict:5}{RESET}  "
        f"{record['bucket']:14} {DIM}{record['base']}{RESET}"
    )
    print(f"  header: {header}")

    for mark in record["blockers"]:
        value = f"  value={mark['value']!r}" if "value" in mark else ""
        print(f"  {RED}[BLOCKER]{RESET} {mark['type']} / {mark['phrasing']}{value}")
        print(f"      {_context(text, tuple(mark['evidence_span']))}")

    for mark in record["distractors"]:
        value = f"  value={mark['value']!r}" if "value" in mark else ""
        print(f"  {YELLOW}[near-miss]{RESET} {mark['type']} / {mark['phrasing']}{value}")
        print(f"      {_context(text, tuple(mark['evidence_span']))}")

    # A location blocker inside a posting headed "Remote" contradicts the
    # header whether or not it was built as a contradiction case. Worth
    # surfacing: it means the injected bucket contains hard cases too, so a
    # per-bucket difficulty comparison would understate the easy bucket.
    if record["bucket"] != "contradiction" and is_remote_base(text):
        for mark in record["blockers"]:
            if mark["type"] in ("onsite_location", "relocation_required", "timezone_overlap"):
                warnings.append(
                    f"{record['id']}: {mark['type']} contradicts the Remote header, "
                    f"but the bucket is '{record['bucket']}' not 'contradiction'"
                )

    if full:
        spans = [
            tuple(m["evidence_span"]) for m in record["blockers"] + record["distractors"]
        ]
        print(f"\n{DIM}{'-' * 78}{RESET}")
        print(_highlight(text, spans))
        print(f"{DIM}{'-' * 78}{RESET}")

    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="print whole postings")
    parser.add_argument("--id", help="audit a single posting, e.g. jd_14")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args()

    labels = yaml.safe_load((args.corpus / "labels.yaml").read_text())
    profile = load_profile()

    print(f"{BOLD}Corpus audit{RESET}  seed={labels['seed']}  "
          f"{labels['verdicts']['SKIP']} SKIP / {labels['verdicts']['APPLY']} APPLY")
    print(f"{DIM}profile: {profile['years_experience']}y exp, {profile['degree']}, "
          f"{profile['location']['city']}, work_auth={profile['work_auth']}, "
          f"comp_floor=${profile['comp_floor']:,}{RESET}")

    warnings: list[str] = []
    for record in labels["postings"]:
        if args.id and record["id"] != args.id:
            continue
        text = (args.corpus / f"{record['id']}.md").read_text()
        warnings.extend(audit(record, text, args.full))

    if warnings:
        print(f"\n{BOLD}{YELLOW}Worth a second look{RESET}")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print(f"\n{GREEN}No structural warnings.{RESET}")


if __name__ == "__main__":
    main()
