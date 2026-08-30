"""Base postings must contain zero blockers and zero distractors.

Everything present in a base appears in every posting derived from it. An
accidental blocker there is worse than a bug: the injector labels the posting
APPLY (it injected nothing), the true verdict is SKIP, and the agent is
penalised for being right. An accidental *distractor* is milder but still
wrong — the clean bucket is supposed to contain only what step 2.3 put there.

The rule for authoring bases: they may mention taxonomy-adjacent facts only
where those facts clearly do not block (years at or below the candidate's
experience, remote or Los Angeles locations). Everything else the taxonomy
touches — sponsorship, citizenship, clearance, licensure, relocation, travel,
shift work, degrees, certifications, employment type, salary — is omitted
entirely, so the injector has sole control over what a posting claims.
"""

import re
from pathlib import Path

import pytest

from src.rules import load_profile, load_taxonomy

_BASE_DIR = Path(__file__).resolve().parent.parent / "src/injector/bases"
BASES = sorted(p for p in _BASE_DIR.glob("*.md") if p.name != "README.md")
PROFILE = load_profile()
TAXONOMY = load_taxonomy()

# Substrings that imply a topic the injector owns. Matched case-insensitively.
FORBIDDEN = [
    "sponsor", "visa", "immigration", "work authorization", "authorized to work",
    "citizen", "itar", "u.s. person", "us person", "green card",
    "clearance", "ts/sci", "secret",
    "licensure", "licensed", "pe license",
    "relocat",
    "% travel", "travel to client", "travel requirement",
    "on-call", "on call", "overnight", "night shift", "weekend rotation", "24/7",
    "bachelor", "master's", "masters degree", "ph.d", "phd", "degree required", "advanced degree",
    "certification", "certified", "cissp", "ckad",
    "corp-to-corp", "corp to corp", "c2c", "w2", "1099", "contract position", "no agencies",
]

assert BASES, "no base postings found"


def _ids(p):
    return p.name


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_no_forbidden_topic(path):
    text = path.read_text().lower()
    hits = [w for w in FORBIDDEN if w in text]
    assert not hits, f"{path.name} mentions injector-owned topics: {hits}"


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_years_requirements_are_satisfiable(path):
    """A years figure above the candidate's experience is a real blocker."""
    limit = PROFILE["years_experience"]
    found = [int(m) for m in re.findall(r"(\d+)\+?\s*years", path.read_text(), re.I)]
    over = [y for y in found if y > limit]
    assert not over, (
        f"{path.name} requires {over} years but the candidate has {limit}; "
        f"that is an accidental years_of_experience blocker"
    )


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_no_salary_figures(path):
    """A posted band below the comp floor blocks; bases omit salary entirely."""
    assert not re.search(r"\$\s?\d", path.read_text()), (
        f"{path.name} names a dollar figure; salary belongs to the injector"
    )


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_location_is_safe(path):
    """Only remote-US or Los Angeles; any other city is an onsite blocker."""
    location = path.read_text().splitlines()[1].lower()
    assert "remote (united states)" in location or "los angeles" in location, (
        f"{path.name} location line is {location!r}; must be remote-US or Los Angeles"
    )


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_has_the_sections_the_injector_targets(path):
    """explicit -> Requirements, footer -> Equal opportunity, indirect -> body."""
    text = path.read_text()
    for section in ("## Requirements", "## Benefits", "## Equal opportunity"):
        assert section in text, f"{path.name} is missing {section!r}, an injection target"


@pytest.mark.parametrize("path", BASES, ids=_ids)
def test_contains_no_taxonomy_text_verbatim(path):
    """Nothing the injector will later insert may already be present."""
    text = path.read_text().lower()
    for blocker in TAXONOMY["blockers"]:
        for style, phrasing in blocker["phrasings"].items():
            stem = re.split(r"\{", phrasing)[0].strip().lower()
            if len(stem) > 25:
                assert stem not in text, f"{path.name} already contains {blocker['id']}/{style}"
        for distractor in blocker["distractors"]:
            stem = re.split(r"\{", distractor)[0].strip().lower()
            if len(stem) > 25:
                assert stem not in text, f"{path.name} already contains a {blocker['id']} distractor"


def test_twelve_bases_exist():
    assert len(BASES) == 12, f"expected 12 base postings, found {len(BASES)}"
