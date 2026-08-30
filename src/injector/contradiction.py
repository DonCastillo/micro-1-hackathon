"""The hard cases: postings that contradict themselves.

Both patterns here punish the same failure — reading part of a posting and
stopping. They are the cases the brief asks for ("include one challenging
case and explain what it revealed"), and the ones a single-pass prompt is
expected to fail.

**Title/body conflict.** The header says `Remote (United States)`; the body
says you must be in Austin. The header is the part a reader trusts, so the
blocker is genuinely easy to miss. The correct verdict is SKIP: a specific
requirement in the body overrides a general header.

**Scoped negation.** A sentence that grants something and then withdraws it
for this role: "We sponsor visas for a number of roles. This position is not
eligible." An agent that keys on "we sponsor visas" concludes the opposite of
the truth. This is nastier than a plain blocker, because the disqualifying
half is preceded by text that argues against it.

These live outside `taxonomy.yaml` deliberately. All 14 blockers carry the
same three phrasing styles there; adding a fourth that only eight of them
support would make the schema ragged for the sake of four postings.
"""

from __future__ import annotations

from typing import Any

from src.injector.inject import drop_existing_years_requirement, insert
from src.rules import blocks

# A title/body conflict needs a header that promises the opposite. Only
# location- and hours-shaped blockers actually contradict "Remote".
TITLE_BODY_BLOCKERS = ("onsite_location", "relocation_required", "timezone_overlap")

REMOTE_HEADER = "remote (united states)"

# Grant-then-withdraw constructions. The first clause is the bait.
SCOPED_NEGATION = {
    "work_authorization": (
        "We are able to sponsor visas for a number of our engineering roles. "
        "This particular position is not eligible for sponsorship."
    ),
    "security_clearance": (
        "Many roles on our team are open to candidates without a clearance. "
        "This one requires an active Secret clearance before your start date."
    ),
    "onsite_location": (
        "Most of our engineering team works remotely. This role is an exception: "
        "you must work from our {city} office five days a week."
    ),
    "relocation_required": (
        "Relocation is not expected for the majority of our openings. For this "
        "role, relocating to {city} is a condition of employment."
    ),
    "employment_type": (
        "We engage contractors across several teams. This opening, however, is "
        "{type} only."
    ),
    "certification_required": (
        "Certification is optional for most of our engineering roles. For this "
        "position, an active {cert} certification is required."
    ),
    "years_of_experience": (
        "We hire engineers at a range of levels. This particular opening requires "
        "a minimum of {years} years of professional experience."
    ),
    "compensation_floor": (
        "Compensation varies widely across our teams. For this role specifically, "
        "the range is capped at ${band_max} and is non-negotiable."
    ),
}


def is_remote_base(text: str) -> bool:
    """Does the header promise remote work? Line 2 is the location line."""
    lines = text.splitlines()
    return len(lines) > 1 and REMOTE_HEADER in lines[1].lower()


def _render(template: str, blocker: dict[str, Any], value: Any) -> str:
    if "{" not in template:
        return template
    parameter = blocker["parameter"]
    if value is None:
        raise ValueError(f"{blocker['id']} needs a {parameter} value")
    shown = f"{value:,}" if parameter == "band_max" else value
    rendered = template.format(**{parameter: shown})
    if "{" in rendered or "}" in rendered:
        raise ValueError(f"unfilled placeholder: {rendered!r}")
    return rendered


def _guard(blocker: dict[str, Any], profile: dict[str, Any], value: Any) -> None:
    if not blocks(blocker, profile, value):
        raise ValueError(
            f"{blocker['id']} with value {value!r} does not block this profile; "
            f"a contradiction case must still resolve to SKIP"
        )


def build_title_body_conflict(
    text: str,
    blocker: dict[str, Any],
    profile: dict[str, Any],
    value: Any = None,
) -> tuple[str, tuple[int, int], str]:
    """Put an onsite requirement in the body of a posting headed Remote."""
    if not is_remote_base(text):
        raise ValueError(
            "title/body conflict needs a base whose header says Remote; "
            "this one does not, so there would be nothing to contradict"
        )
    if blocker["id"] not in TITLE_BODY_BLOCKERS:
        raise ValueError(
            f"{blocker['id']} does not contradict a remote header; "
            f"expected one of {TITLE_BODY_BLOCKERS}"
        )
    _guard(blocker, profile, value)

    sentence = _render(blocker["phrasings"]["indirect"], blocker, value)
    new_text, span = insert(text, sentence, "indirect")
    return new_text, span, sentence


def build_scoped_negation(
    text: str,
    blocker: dict[str, Any],
    profile: dict[str, Any],
    value: Any = None,
    style: str = "indirect",
) -> tuple[str, tuple[int, int], str]:
    """Grant the thing, then withdraw it for this role.

    The span covers both clauses. Overlap matching makes that forgiving in the
    right direction: an agent quoting only the binding half still scores, and
    so does one quoting the whole construction.
    """
    if blocker["id"] not in SCOPED_NEGATION:
        raise ValueError(
            f"no scoped-negation template for {blocker['id']}; "
            f"available: {sorted(SCOPED_NEGATION)}"
        )
    _guard(blocker, profile, value)

    if blocker["id"] == "years_of_experience":
        text = drop_existing_years_requirement(text)
    sentence = _render(SCOPED_NEGATION[blocker["id"]], blocker, value)
    new_text, span = insert(text, sentence, style)
    return new_text, span, sentence
