"""The one output shape every system emits, and the parser that recovers it.

Baseline and agent variants alike produce a `Prediction`. The harness scores
that and nothing else, which is what makes EVAL.md 9's fairness invariant
enforceable: one scorer, one shape, no per-system special cases.

Parsing is deliberately tolerant. EVAL.md 9 forbids tuning the baseline's
*prompt* to make its output easier to read — that would inflate it — but
explicitly allows the *parse layer* to adapt. So this module digs a JSON
object out of fenced blocks, surrounding prose, or a bare object, and
normalizes casing and common verdict spellings.

What it does not do is repair meaning. An invented blocker type is kept
verbatim and scored as a false positive, because claiming a blocker that does
not exist is exactly what a false positive is. Output that cannot be parsed at
all becomes an empty prediction carrying the error, so a system that fails to
produce readable output is scored as having found nothing — not skipped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

VERDICTS = ("APPLY", "APPLY_WITH_CAVEAT", "SKIP")

# Never a gold verdict, so it can never be scored correct. See scored_verdict.
UNREADABLE = "UNREADABLE"

# Spellings models reach for that mean one of the three above. Normalizing
# these is parse-layer work, not prompt tuning.
_VERDICT_ALIASES = {
    "APPLY_WITH_CAVEATS": "APPLY_WITH_CAVEAT",
    "APPLYWITHCAVEAT": "APPLY_WITH_CAVEAT",
    "CAVEAT": "APPLY_WITH_CAVEAT",
    "DO_NOT_APPLY": "SKIP",
    "DONT_APPLY": "SKIP",
    "NO": "SKIP",
    "YES": "APPLY",
}

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class ParseError(ValueError):
    """Raised when no usable prediction can be recovered from model output."""


@dataclass
class Claim:
    """One blocker or caveat a system reported."""

    type: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "evidence": self.evidence}


@dataclass
class Prediction:
    verdict: str
    blockers: list[Claim] = field(default_factory=list)
    caveats: list[Claim] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def scored_verdict(self) -> str:
        """EVAL.md 5: APPLY_WITH_CAVEAT scores as APPLY.

        Gold verdicts are only ever APPLY or SKIP, so a three-way comparison
        would need someone to rule on when a caveat is deserved — the kind of
        judgment call the protocol exists to remove.

        An unreadable answer returns UNREADABLE, which matches no gold verdict.
        Any concrete fallback would hand out free credit: APPLY is right on the
        8 clean postings, SKIP on the 16 blocked ones. A system that emitted
        nothing legible did not decide anything, and scoring it as though it
        had is the one reading that cannot be defended.
        """
        if self.parse_error:
            return UNREADABLE
        return "SKIP" if self.verdict == "SKIP" else "APPLY"

    def unknown_types(self, known: set[str]) -> list[str]:
        """Reported blocker types that are not in the taxonomy."""
        return [c.type for c in self.blockers if c.type not in known]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "verdict": self.verdict,
            "blockers": [c.to_dict() for c in self.blockers],
            "caveats": [c.to_dict() for c in self.caveats],
        }
        if self.parse_error:
            out["parse_error"] = self.parse_error
        return out

    @classmethod
    def unparseable(cls, error: str) -> Prediction:
        """A system whose output could not be read found nothing.

        The stored verdict is APPLY so `to_dict` stays inside the declared
        enum, but `scored_verdict` reports UNREADABLE, which matches nothing.
        """
        return cls(verdict="APPLY", parse_error=error)


def _candidate_objects(raw: str) -> list[str]:
    """JSON-object substrings, best candidates first."""
    candidates = [block.strip() for block in _FENCE.findall(raw)]
    candidates.append(raw.strip())

    # Brace matching, for an object embedded in prose.
    depth, start = 0, None
    for i, char in enumerate(raw):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(raw[start : i + 1])
    return candidates


def _claims(value: Any) -> list[Claim]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, dict):
            kind = item.get("type") or item.get("blocker") or item.get("id")
            evidence = item.get("evidence") or item.get("quote") or item.get("text") or ""
            if kind:
                out.append(Claim(str(kind).strip(), str(evidence).strip()))
        elif isinstance(item, str) and item.strip():
            # Some outputs give a bare list of type names with no evidence.
            out.append(Claim(item.strip(), ""))
    return out


def _normalize_verdict(value: Any) -> str:
    text = re.sub(r"[^A-Z_]", "_", str(value).strip().upper()).strip("_")
    text = re.sub(r"_+", "_", text)
    if text in VERDICTS:
        return text
    if text in _VERDICT_ALIASES:
        return _VERDICT_ALIASES[text]
    raise ParseError(f"unrecognized verdict {value!r}")


def parse_claims_json(raw: str) -> list[Claim]:
    """Pull a `blockers` list out of a partial JSON reply.

    Used by variants whose individual steps report findings without a verdict —
    no single group check sees enough of the posting to decide one.
    """
    for candidate in _candidate_objects(raw):
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict) and "blockers" in payload:
            return _claims(payload["blockers"])
    return []


def parse_prediction(raw: str | dict[str, Any]) -> Prediction:
    """Recover a Prediction from model output. Raises ParseError if impossible."""
    if isinstance(raw, dict):
        payloads: list[Any] = [raw]
    else:
        payloads = []
        for candidate in _candidate_objects(raw):
            try:
                payloads.append(json.loads(candidate))
            except (json.JSONDecodeError, ValueError):
                continue

    for payload in payloads:
        if not isinstance(payload, dict) or "verdict" not in payload:
            continue
        return Prediction(
            verdict=_normalize_verdict(payload["verdict"]),
            blockers=_claims(payload.get("blockers")),
            caveats=_claims(payload.get("caveats")),
        )

    raise ParseError("no JSON object with a 'verdict' field found in output")


# Handed to the model when an iteration uses structured output. Kept beside
# the parser so the two cannot drift apart.
PREDICTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "blockers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["type", "evidence"],
                "additionalProperties": False,
            },
        },
        "caveats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["type", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "blockers", "caveats"],
    "additionalProperties": False,
}
