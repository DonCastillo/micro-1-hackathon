"""The corpus is the answer key. These tests check it against reality.

The two failures that matter most are silent ones: a span that no longer
points at its sentence (evidence scoring degrades and looks like an agent
problem), and a verdict that disagrees with the rules engine (the agent is
graded against the wrong answer).
"""

from pathlib import Path

import pytest
import yaml

from src.injector.generate import BUCKETS, TOTAL, build_corpus, write_corpus
from src.rules import blocks, load_profile, load_taxonomy

PROFILE = load_profile()
BLOCKERS = {b["id"]: b for b in load_taxonomy()["blockers"]}
CORPUS = build_corpus(42)


def _ids(p):
    return p.id


# ─── determinism ──────────────────────────────────────────────────────────

def test_same_seed_produces_an_identical_corpus():
    again = build_corpus(42)
    assert [p.text for p in CORPUS] == [p.text for p in again]
    assert [p.id for p in CORPUS] == [p.id for p in again]
    assert [[(m.type, m.span) for m in p.blockers] for p in CORPUS] == [
        [(m.type, m.span) for m in p.blockers] for p in again
    ]


def test_a_different_seed_produces_a_different_corpus():
    assert [p.text for p in build_corpus(99)] != [p.text for p in CORPUS]


# ─── composition ──────────────────────────────────────────────────────────

def test_corpus_matches_the_frozen_composition():
    assert len(CORPUS) == TOTAL == 24
    for name, expected in BUCKETS.items():
        assert sum(p.bucket == name for p in CORPUS) == expected


def test_verdict_split_matches_eval_md():
    assert sum(p.verdict == "SKIP" for p in CORPUS) == 16
    assert sum(p.verdict == "APPLY" for p in CORPUS) == 8


def test_timing_decades_are_comparable():
    """EVAL.md 7 times jd_01-10 manually and jd_11-20 assisted.

    If one decade is much easier, the measured time difference is a property
    of the corpus rather than of the tool.
    """
    first = sum(p.verdict == "APPLY" for p in CORPUS[:10])
    second = sum(p.verdict == "APPLY" for p in CORPUS[10:20])
    assert abs(first - second) <= 2, (
        f"decade imbalance: {first} vs {second} APPLY postings makes the "
        f"human-time comparison meaningless"
    )


def test_every_base_is_used_twice():
    used = [p.base for p in CORPUS]
    assert len(set(used)) == 12
    assert all(used.count(b) == 2 for b in set(used))


# ─── spans and labels ─────────────────────────────────────────────────────

@pytest.mark.parametrize("posting", CORPUS, ids=_ids)
def test_every_span_contains_its_sentence(posting):
    for mark in posting.blockers + posting.distractors:
        start, end = mark.span
        assert posting.text[start:end] == mark.sentence, (
            f"{posting.id}: span {mark.span} does not contain {mark.type}"
        )


@pytest.mark.parametrize("posting", CORPUS, ids=_ids)
def test_each_injected_sentence_appears_exactly_once(posting):
    """Two copies would make the span ambiguous and the evidence check unsound."""
    for mark in posting.blockers + posting.distractors:
        assert posting.text.count(mark.sentence) == 1


@pytest.mark.parametrize("posting", CORPUS, ids=_ids)
def test_verdict_agrees_with_the_rules_engine(posting):
    """Re-derive the answer instead of trusting the bucket label."""
    expected = "SKIP" if posting.blockers else "APPLY"
    assert posting.verdict == expected
    for mark in posting.blockers:
        assert blocks(BLOCKERS[mark.type], PROFILE, mark.value), (
            f"{posting.id}: {mark.type} does not block the profile, "
            f"so SKIP is the wrong answer"
        )


@pytest.mark.parametrize("posting", [p for p in CORPUS if p.bucket == "clean"], ids=_ids)
def test_clean_postings_carry_distractors_and_no_blockers(posting):
    assert not posting.blockers
    assert posting.distractors, "a clean posting with no distractor tests nothing"
    assert posting.verdict == "APPLY"


@pytest.mark.parametrize("posting", [p for p in CORPUS if p.bucket == "multi"], ids=_ids)
def test_multi_postings_have_two_distinct_blockers(posting):
    assert len(posting.blockers) == 2
    assert len({m.type for m in posting.blockers}) == 2


def test_contradiction_bucket_has_both_patterns():
    styles = [m.style for p in CORPUS if p.bucket == "contradiction" for m in p.blockers]
    assert styles.count("title_body_conflict") == 2
    assert styles.count("scoped_negation") == 2


def test_injected_bucket_covers_distinct_blocker_types():
    types = [m.type for p in CORPUS if p.bucket == "injected" for m in p.blockers]
    assert len(set(types)) == len(types) == 10


def test_all_three_phrasing_styles_appear():
    styles = {m.style for p in CORPUS if p.bucket == "injected" for m in p.blockers}
    assert styles == {"explicit", "indirect", "footer"}


# ─── on-disk output ───────────────────────────────────────────────────────

def test_written_labels_match_the_written_postings(tmp_path):
    write_corpus(CORPUS, tmp_path, 42)
    labels = yaml.safe_load((tmp_path / "labels.yaml").read_text())

    assert labels["seed"] == 42
    assert labels["counts"] == BUCKETS
    assert len(labels["postings"]) == TOTAL

    for record in labels["postings"]:
        text = (tmp_path / f"{record['id']}.md").read_text()
        for mark in record["blockers"] + record["distractors"]:
            start, end = mark["evidence_span"]
            assert text[start:end] == mark["sentence"], (
                f"{record['id']}: on-disk span does not match on-disk text"
            )


def test_regenerating_removes_stale_postings(tmp_path):
    write_corpus(CORPUS, tmp_path, 42)
    (tmp_path / "jd_99.md").write_text("left over from an older run")
    write_corpus(CORPUS, tmp_path, 42)
    assert not (tmp_path / "jd_99.md").exists()
    assert len(list(tmp_path.glob("jd_*.md"))) == TOTAL


def test_committed_corpus_is_current():
    """The checked-in corpus must be what seed 42 produces today."""
    corpus_dir = Path(__file__).resolve().parent.parent / "data/corpus"
    labels_path = corpus_dir / "labels.yaml"
    if not labels_path.exists():
        pytest.skip("corpus not generated yet")
    labels = yaml.safe_load(labels_path.read_text())
    for record, posting in zip(labels["postings"], CORPUS):
        assert record["id"] == posting.id
        assert (corpus_dir / f"{posting.id}.md").read_text() == posting.text, (
            f"{posting.id} on disk differs from seed 42; regenerate the corpus"
        )


@pytest.mark.parametrize("posting", CORPUS, ids=_ids)
def test_a_recorded_value_was_actually_used(posting):
    """No value in the answer key unless the sentence consumed it.

    Distractor templates are mostly fixed strings. Sampling a blocking value
    for them anyway produced labels like `value: 120000` beside a sentence
    reading "$160,000 - $195,000" — not wrong in the verdict, but misleading
    to anyone auditing the corpus, which is the whole point of the key.
    """
    for mark in posting.blockers + posting.distractors:
        if mark.value is None:
            continue
        shown = f"{mark.value:,}" if isinstance(mark.value, int) else str(mark.value)
        assert shown in mark.sentence, (
            f"{posting.id}: {mark.type} records value {mark.value!r} "
            f"but it does not appear in {mark.sentence!r}"
        )


@pytest.mark.parametrize("posting", CORPUS, ids=_ids)
def test_no_posting_states_two_conflicting_years_requirements(posting):
    """A base's own years line must be removed when a years blocker is injected.

    Otherwise the posting reads "3+ years" and "Minimum of 12 years required"
    in the same list — incoherent, and an agent hesitating over it would be
    scored as missing a blocker rather than as spotting a corpus defect.
    """
    import re

    if not any(m.type == "years_of_experience" for m in posting.blockers):
        return
    figures = set(re.findall(r"(\d+)\+?\s*years", posting.text, re.I))
    assert len(figures) == 1, (
        f"{posting.id} states conflicting years requirements: {sorted(figures)}"
    )
