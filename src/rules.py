"""Evaluate a taxonomy `blocks_when` rule against the candidate profile.

Shared by the injector (which must only emit values that genuinely block) and
by the eval harness (which needs to know the correct verdict for a posting).
Keeping one implementation means the labels and the scoring can never drift
apart — if this module is wrong, it is wrong in both places and the tests
catch it, rather than being wrong in one place and silently mislabelling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DATA = Path(__file__).resolve().parent.parent / "data"

# Ordering matters: a Bachelor's does not satisfy a Master's requirement.
DEGREE_ORDER = ["none", "Associate's", "Bachelor's", "Master's", "Ph.D."]

# UTC offsets for the time zones the taxonomy can require. A posting that
# demands sustained overlap with a zone this far from the candidate cannot be
# worked without night shifts.
ZONE_OFFSETS = {
    "Central European Time": 1,
    "Singapore Standard Time": 8,
    "Greenwich Mean Time": 0,
}

# Below this many hours of clock separation, a normal working day still
# overlaps enough to satisfy a "6 hours of overlap" style requirement.
MAX_WORKABLE_OFFSET_HOURS = 6


def load_taxonomy(path: Path | None = None) -> dict[str, Any]:
    return yaml.safe_load((path or DATA / "taxonomy.yaml").read_text())


def load_profile(path: Path | None = None) -> dict[str, Any]:
    return yaml.safe_load((path or DATA / "profile" / "candidate.yaml").read_text())


def _degree_rank(degree: str) -> int:
    try:
        return DEGREE_ORDER.index(degree)
    except ValueError as exc:
        raise ValueError(f"unknown degree {degree!r}; expected one of {DEGREE_ORDER}") from exc


def _zone_gap(profile_offset: int, zone: str) -> int:
    """Hours of clock separation, taking the shorter way around the dial."""
    if zone not in ZONE_OFFSETS:
        raise ValueError(f"unknown time zone {zone!r}; expected one of {sorted(ZONE_OFFSETS)}")
    raw = abs(ZONE_OFFSETS[zone] - profile_offset)
    return min(raw, 24 - raw)


def blocks(blocker: dict[str, Any], profile: dict[str, Any], value: Any = None) -> bool:
    """Does this blocker disqualify the candidate?

    `value` is the sampled parameter for parametric blockers (the years figure,
    the city, the salary band maximum) and is ignored for absolute ones.
    """
    op = blocker["blocks_when"]["op"]
    expected = blocker["blocks_when"].get("value")
    field = blocker["profile_field"]
    actual = profile[field]

    if op == "equals":
        return actual == expected
    if op == "not_equals":
        return actual != expected
    if op == "not_contains":
        return expected not in actual
    if op == "not_contains_parameter":
        return value not in actual
    if op == "greater_than_profile":
        return value > actual
    if op == "less_than_profile":
        return value < actual
    if op == "degree_below_required":
        return _degree_rank(actual) < _degree_rank(value)
    if op == "city_mismatch_and_no_relocation":
        posting_city = value.split(",")[0].strip()
        return posting_city != actual["city"] and not profile["willing_to_relocate"]
    if op == "insufficient_overlap":
        return _zone_gap(profile["utc_offset"], value) >= MAX_WORKABLE_OFFSET_HOURS

    raise ValueError(f"unknown op {op!r} on blocker {blocker['id']!r}")
