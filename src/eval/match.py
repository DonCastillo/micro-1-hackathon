"""Match one system's prediction against the answer key. EVAL.md 3 is the spec.

Two things here are subtler than they look.

**Normalization moves the goalposts.** Quotes are compared with whitespace
collapsed and case folded, but gold spans are offsets into the *original*
posting. Searching the normalized text yields a normalized offset, which is
not the same number. So normalization carries an index map back to the
original, and every span this module reports is an original-text span.

**Detection and evidence are scored separately.** Detection matches on `type`
alone; whether the quote is any good is a second, independent question. That
separation is deliberate (EVAL.md 3): iteration 3 is expected to leave
detection flat and move evidence accuracy, and one combined number would show
"no change" and get the work discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.schema import Prediction

Span = tuple[int, int]


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Case-folded, whitespace-collapsed text plus a map back to original offsets.

    `index_map[i]` is the original index of normalized character `i`, so a hit
    at normalized position `n` can be reported as an original-text span.
    """
    chars: list[str] = []
    index_map: list[int] = []
    previous_was_space = False

    for i, char in enumerate(text):
        if char.isspace():
            if previous_was_space:
                continue
            chars.append(" ")
            previous_was_space = True
        else:
            chars.append(char.lower())
            previous_was_space = False
        index_map.append(i)

    return "".join(chars), index_map


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def locate(posting: str, evidence: str) -> Span | None:
    """Find a quote in the posting, returning an original-text span.

    Contiguous matches only: a paraphrase or an elided quote does not count,
    and the prompt tells the system to quote verbatim. Stripping the posting
    (EVAL.md 3) is a no-op for substring search, so only the quote is stripped.
    """
    needle = _normalize(evidence)
    if not needle:
        return None

    haystack, index_map = _normalize_with_map(posting)
    at = haystack.find(needle)
    if at == -1:
        return None

    start = index_map[at]
    end = index_map[at + len(needle) - 1] + 1
    return start, end


def overlaps(a: Span, b: Span) -> bool:
    """EVAL.md 3: [a, b) overlaps [c, d) iff a < d and c < b."""
    return a[0] < b[1] and b[0] < a[1]


@dataclass
class EvidenceCheck:
    """How a true positive's citation held up."""

    claim_index: int
    gold_index: int
    quoted: bool  # did the system supply a quote at all?
    found: bool  # was that quote present in the posting?
    correct: bool  # did it overlap the gold span?
    located: Span | None = None


@dataclass
class PostingMatch:
    posting_id: str
    true_positives: list[tuple[int, int]] = field(default_factory=list)
    false_positives: list[int] = field(default_factory=list)
    false_negatives: list[int] = field(default_factory=list)
    evidence: list[EvidenceCheck] = field(default_factory=list)

    # Over every predicted blocker, not just true positives, so a fabricated
    # quote inside a false positive is still counted (EVAL.md 5).
    hallucinated: list[int] = field(default_factory=list)
    missing_evidence: list[int] = field(default_factory=list)

    predicted_verdict: str = "APPLY"
    gold_verdict: str = "APPLY"
    parse_error: str | None = None

    @property
    def verdict_correct(self) -> bool:
        return self.predicted_verdict == self.gold_verdict

    @property
    def flagged_anything(self) -> bool:
        """Used for the clean-posting false-alarm rate."""
        return bool(self.true_positives or self.false_positives)


def match_posting(
    prediction: Prediction,
    gold: dict[str, Any],
    posting_text: str,
) -> PostingMatch:
    """Score one prediction against one labelled posting."""
    gold_blockers = gold.get("blockers") or []

    result = PostingMatch(
        posting_id=gold["id"],
        predicted_verdict=prediction.scored_verdict,
        gold_verdict=gold["expected_verdict"],
        parse_error=prediction.parse_error,
    )

    # Detection: type only, one-to-one, in prediction order (EVAL.md 3).
    claimed: set[int] = set()
    for claim_index, claim in enumerate(prediction.blockers):
        for gold_index, gold_blocker in enumerate(gold_blockers):
            if gold_index in claimed or gold_blocker["type"] != claim.type:
                continue
            claimed.add(gold_index)
            result.true_positives.append((claim_index, gold_index))
            break
        else:
            # Wrong type, a duplicate of a type already matched, or a blocker
            # claimed on a clean posting. An invented type lands here too.
            result.false_positives.append(claim_index)

    result.false_negatives = [i for i in range(len(gold_blockers)) if i not in claimed]

    # Evidence, over every prediction for the hallucination counters and over
    # true positives for the accuracy rates.
    truthful = dict(result.true_positives)
    for claim_index, claim in enumerate(prediction.blockers):
        quoted = bool(claim.evidence.strip())
        located = locate(posting_text, claim.evidence) if quoted else None

        if not quoted:
            result.missing_evidence.append(claim_index)
        elif located is None:
            result.hallucinated.append(claim_index)

        if claim_index in truthful:
            gold_index = truthful[claim_index]
            gold_span = tuple(gold_blockers[gold_index]["evidence_span"])
            result.evidence.append(
                EvidenceCheck(
                    claim_index=claim_index,
                    gold_index=gold_index,
                    quoted=quoted,
                    found=located is not None,
                    correct=located is not None and overlaps(located, gold_span),
                    located=located,
                )
            )

    return result
