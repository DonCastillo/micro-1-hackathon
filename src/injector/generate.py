"""Assemble the 24-posting corpus and its answer key, deterministically.

    python -m src.injector.generate --seed 42 --out data/corpus

Two things here are easy to get wrong and both are guarded.

**Span drift.** Injecting a second sentence into a posting shifts the offsets
of the first. Recording spans as we inject would leave every multi-injection
posting with a stale first span, and evidence scoring would degrade on exactly
the hardest cases. So spans are resolved once, against the finished text.

**Bucket ordering.** EVAL.md 7 times manual triage on jd_01-jd_10 and assisted
triage on jd_11-jd_20, so those decades must be comparable in difficulty or the
comparison measures the corpus rather than the tool. A plain shuffle is not
enough — it preserves the counts but not the layout, and at seed 42 it put 7 of
the 8 clean postings in the first decade. Buckets are dealt at an even stride
instead (see `_stratified_buckets`).
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.injector.contradiction import (
    SCOPED_NEGATION,
    TITLE_BODY_BLOCKERS,
    build_scoped_negation,
    build_title_body_conflict,
    is_remote_base,
)
from src.injector.inject import STYLES, inject_blocker, inject_distractor
from src.rules import load_profile, load_taxonomy

ROOT = Path(__file__).resolve().parent.parent.parent
BASES_DIR = ROOT / "src/injector/bases"

# EVAL.md section 2. Changing these changes the benchmark.
BUCKETS = {"injected": 10, "clean": 8, "contradiction": 4, "multi": 2}
TOTAL = sum(BUCKETS.values())


@dataclass
class Mark:
    """One injected sentence and where it ended up."""

    type: str
    sentence: str
    style: str
    value: Any = None
    span: tuple[int, int] | None = None


@dataclass
class Posting:
    id: str
    bucket: str
    base: str
    text: str
    verdict: str
    blockers: list[Mark] = field(default_factory=list)
    distractors: list[Mark] = field(default_factory=list)


def load_bases() -> list[Path]:
    return sorted(p for p in BASES_DIR.glob("*.md") if p.name != "README.md")


def _value_for(blocker: dict[str, Any], rng: random.Random) -> Any:
    if blocker["kind"] != "parametric":
        return None
    return rng.choice(blocker["blocking_values"])


def _stratified_buckets(rng: random.Random) -> list[str]:
    """Bucket order that spreads each kind evenly across the 24 slots.

    A plain shuffle preserves the counts but not the layout: seed 42 put 7 of
    the 8 clean postings in jd_01-jd_10 and one in jd_11-jd_20. EVAL.md 7 times
    manual triage on the first decade and assisted triage on the second, so
    that split would have measured which decade was easier, not whether the
    tool helps.

    Each bucket is dealt at its own even stride with a random phase, so the
    order is still seed-dependent but every decade sees a representative mix.
    """
    placed: list[tuple[float, float, str]] = []
    for name, count in BUCKETS.items():
        stride = TOTAL / count
        phase = rng.random() * stride
        for k in range(count):
            placed.append((phase + k * stride, rng.random(), name))
    placed.sort()
    return [name for _, _, name in placed]


def _balanced_styles(n: int, rng: random.Random) -> list[str]:
    """Roughly equal counts per style, so the per-style diagnostic is readable."""
    styles = [STYLES[i % len(STYLES)] for i in range(n)]
    rng.shuffle(styles)
    return styles


def _assign_bases(buckets: list[str], bases: list[Path], rng: random.Random) -> list[Path]:
    """Each base used twice, with contradiction slots guaranteed a remote base."""
    pool = bases * (TOTAL // len(bases))
    rng.shuffle(pool)

    for i, bucket in enumerate(buckets):
        if bucket != "contradiction" or is_remote_base(pool[i].read_text()):
            continue
        # Swap in a remote base from a slot that does not need one.
        for j, other in enumerate(buckets):
            if other != "contradiction" and is_remote_base(pool[j].read_text()):
                pool[i], pool[j] = pool[j], pool[i]
                break
        else:
            raise RuntimeError("no remote base available to satisfy a contradiction slot")
    return pool


def _resolve_spans(posting: Posting) -> None:
    """Locate every injected sentence in the finished text.

    Done after all injections precisely because earlier spans move when later
    text is inserted ahead of them.
    """
    for mark in posting.blockers + posting.distractors:
        occurrences = posting.text.count(mark.sentence)
        if occurrences != 1:
            raise RuntimeError(
                f"{posting.id}: expected exactly one occurrence of {mark.sentence[:50]!r}, "
                f"found {occurrences}; spans would be ambiguous"
            )
        start = posting.text.index(mark.sentence)
        mark.span = (start, start + len(mark.sentence))


def build_corpus(seed: int) -> list[Posting]:
    rng = random.Random(seed)
    taxonomy = load_taxonomy()
    profile = load_profile()
    blockers = {b["id"]: b for b in taxonomy["blockers"]}
    ids = sorted(blockers)

    buckets = _stratified_buckets(rng)
    assigned = _assign_bases(buckets, load_bases(), rng)

    single_types = rng.sample(ids, BUCKETS["injected"])
    single_styles = _balanced_styles(BUCKETS["injected"], rng)
    title_body = rng.sample(list(TITLE_BODY_BLOCKERS), 2)
    scoped = rng.sample(sorted(SCOPED_NEGATION), 2)

    postings: list[Posting] = []
    n_single = n_contra = 0

    for i, (bucket, base) in enumerate(zip(buckets, assigned), start=1):
        posting = Posting(
            id=f"jd_{i:02d}",
            bucket=bucket,
            base=base.stem,
            text=base.read_text(),
            verdict="APPLY" if bucket == "clean" else "SKIP",
        )

        if bucket == "injected":
            blocker = blockers[single_types[n_single]]
            style = single_styles[n_single]
            n_single += 1
            value = _value_for(blocker, rng)
            posting.text, _, sentence = inject_blocker(
                posting.text, blocker, style, profile, value
            )
            posting.blockers.append(Mark(blocker["id"], sentence, style, value))

        elif bucket == "multi":
            for blocker_id, style in zip(rng.sample(ids, 2), rng.sample(STYLES, 2)):
                blocker = blockers[blocker_id]
                value = _value_for(blocker, rng)
                posting.text, _, sentence = inject_blocker(
                    posting.text, blocker, style, profile, value
                )
                posting.blockers.append(Mark(blocker_id, sentence, style, value))

        elif bucket == "contradiction":
            if n_contra < 2:
                blocker = blockers[title_body[n_contra]]
                value = _value_for(blocker, rng)
                posting.text, _, sentence = build_title_body_conflict(
                    posting.text, blocker, profile, value
                )
                style = "title_body_conflict"
            else:
                blocker = blockers[scoped[n_contra - 2]]
                value = _value_for(blocker, rng)
                posting.text, _, sentence = build_scoped_negation(
                    posting.text, blocker, profile, value
                )
                style = "scoped_negation"
            n_contra += 1
            posting.blockers.append(Mark(blocker["id"], sentence, style, value))

        elif bucket == "clean":
            for blocker_id in rng.sample(ids, rng.randint(1, 2)):
                blocker = blockers[blocker_id]
                index = rng.randrange(len(blocker["distractors"]))
                style = rng.choice(STYLES)
                # Only sample a value when the distractor template consumes
                # one. Most distractors are fixed strings, and recording an
                # unused value made the answer key actively misleading — a
                # compensation distractor reading "$160,000 - $195,000" was
                # labelled `value: 120000`, which reads like a broken label.
                needs_value = "{" in blocker["distractors"][index]
                value = _value_for(blocker, rng) if needs_value else None
                posting.text, _, sentence = inject_distractor(
                    posting.text, blocker, style, index, value
                )
                posting.distractors.append(Mark(blocker_id, sentence, style, value))

        _resolve_spans(posting)
        postings.append(posting)

    return postings


def _mark_dict(mark: Mark) -> dict[str, Any]:
    out: dict[str, Any] = {"type": mark.type, "phrasing": mark.style}
    if mark.value is not None:
        out["value"] = mark.value
    out["evidence_span"] = list(mark.span)
    out["sentence"] = mark.sentence
    return out


def write_corpus(postings: list[Posting], out_dir: Path, seed: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("jd_*.md"):
        stale.unlink()

    for posting in postings:
        (out_dir / f"{posting.id}.md").write_text(posting.text)

    labels = {
        "seed": seed,
        "counts": {name: sum(p.bucket == name for p in postings) for name in BUCKETS},
        "verdicts": {
            "SKIP": sum(p.verdict == "SKIP" for p in postings),
            "APPLY": sum(p.verdict == "APPLY" for p in postings),
        },
        "postings": [
            {
                "id": p.id,
                "bucket": p.bucket,
                "base": p.base,
                "expected_verdict": p.verdict,
                "blockers": [_mark_dict(m) for m in p.blockers],
                "distractors": [_mark_dict(m) for m in p.distractors],
            }
            for p in postings
        ],
    }
    (out_dir / "labels.yaml").write_text(
        yaml.safe_dump(labels, sort_keys=False, width=100, allow_unicode=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "data/corpus")
    args = parser.parse_args()

    postings = build_corpus(args.seed)
    write_corpus(postings, args.out, args.seed)

    print(f"seed {args.seed} -> {len(postings)} postings in {args.out}")
    for name in BUCKETS:
        members = [p.id for p in postings if p.bucket == name]
        print(f"  {name:14} {len(members):2}  {' '.join(members)}")
    print(f"  {'SKIP':14} {sum(p.verdict == 'SKIP' for p in postings):2}")
    print(f"  {'APPLY':14} {sum(p.verdict == 'APPLY' for p in postings):2}")


if __name__ == "__main__":
    main()
