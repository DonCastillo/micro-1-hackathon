"""Insert a blocker into a base posting and report exactly where it landed.

The returned character span is the ground truth: it is what `labels.yaml`
records and what the eval harness checks a cited quote against. If a span is
off by even a character, evidence scoring silently degrades — so `insert`
asserts that the span it returns actually contains the sentence it inserted.

`steps.md` 2.2 describes one function per blocker type. The taxonomy already
holds every phrasing, so fourteen near-identical functions would duplicate
that YAML and give fourteen places for a placement bug to hide. This module
is parameterized instead: one insertion primitive, one renderer, one guard.
"""

from __future__ import annotations

import re
from typing import Any

from src.rules import blocks

# Where each phrasing style lands. The point of `footer` is displacement: it
# sits after the equal-opportunity boilerplate, as far from the requirements
# list as the document allows, because that is where real postings bury the
# disqualifying sentence and where readers stop looking.
STYLES = ("explicit", "indirect", "footer")

_HEADING = re.compile(r"^##\s+(.+)$", re.M)


def _section_body(text: str, starts_with: str) -> tuple[int, int]:
    """Character bounds of a '## <starts_with>...' section body."""
    headings = list(_HEADING.finditer(text))
    for i, m in enumerate(headings):
        if m.group(1).strip().lower().startswith(starts_with.lower()):
            body_start = m.end() + 1
            body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            return body_start, body_end
    raise ValueError(f"no '## {starts_with}' section; base postings must have one")


def insert(text: str, sentence: str, style: str) -> tuple[str, tuple[int, int]]:
    """Insert `sentence` per `style`. Returns the new text and the exact span.

    The span covers the sentence only — not the bullet marker or the
    surrounding newlines — because that is what an agent would quote.
    """
    if style == "explicit":
        # A new bullet at the end of the requirements list, stated plainly.
        body_start, body_end = _section_body(text, "Requirements")
        at = body_start + len(text[body_start:body_end].rstrip())
        prefix = "\n- "
    elif style == "indirect":
        # Prose at the end of the opening section, where it reads as context
        # rather than as a requirement.
        body_start, body_end = _section_body(text, "About")
        at = body_start + len(text[body_start:body_end].rstrip())
        prefix = "\n\n"
    elif style == "footer":
        # After the equal-opportunity paragraph, at the very end.
        at = len(text.rstrip())
        prefix = "\n\n"
    else:
        raise ValueError(f"unknown style {style!r}; expected one of {STYLES}")

    new_text = text[:at] + prefix + sentence + text[at:]
    start = at + len(prefix)
    end = start + len(sentence)

    assert new_text[start:end] == sentence, "span does not contain the inserted sentence"
    return new_text, (start, end)


def render(blocker: dict[str, Any], style: str, value: Any = None) -> str:
    """Fill a phrasing template with its sampled parameter value."""
    phrasing = blocker["phrasings"][style]
    if blocker["kind"] != "parametric":
        return phrasing

    parameter = blocker["parameter"]
    if value is None:
        raise ValueError(f"{blocker['id']} is parametric and needs a value")
    # Salary reads as $115,000, not $115000. Years and percentages stay bare.
    shown = f"{value:,}" if parameter == "band_max" else value
    rendered = phrasing.format(**{parameter: shown})

    if "{" in rendered or "}" in rendered:
        raise ValueError(f"unfilled placeholder in {blocker['id']}/{style}: {rendered!r}")
    return rendered


# Language that makes a requirement binding. A distractor containing any of
# these is not a near-miss any more — it is a blocker, and labelling it APPLY
# would invert the case. `blocks()` cannot catch this: the rule engine answers
# "would a requirement of this kind disqualify the candidate", which is about
# the profile, not about whether the sentence actually imposes a requirement.
# For distractors the modality is the whole difference, so it is checked here.
# Matched on word boundaries: a bare substring test would flag "only" inside
# "commonly" and reject a perfectly good distractor.
MANDATORY_LANGUAGE = (
    "required",
    "must",
    "will not be considered",
    "not eligible",
    "restricted to",
    "is a condition of",
    "prior to their start date",
    "non-negotiable",
    "only",
)


def binding_language(sentence: str) -> list[str]:
    """Mandatory-requirement phrases present in `sentence`, if any."""
    lowered = sentence.lower()
    return [p for p in MANDATORY_LANGUAGE if re.search(rf"\b{re.escape(p)}\b", lowered)]


def render_distractor(blocker: dict[str, Any], index: int, value: Any = None) -> str:
    """Render one of a blocker's near-miss distractors."""
    try:
        text = blocker["distractors"][index]
    except IndexError as exc:
        raise IndexError(
            f"{blocker['id']} has {len(blocker['distractors'])} distractors, asked for {index}"
        ) from exc

    if "{" in text:
        parameter = blocker["parameter"]
        if value is None:
            raise ValueError(f"{blocker['id']} distractor {index} needs a {parameter} value")
        shown = f"{value:,}" if parameter == "band_max" else value
        text = text.format(**{parameter: shown})

    if "{" in text or "}" in text:
        raise ValueError(f"unfilled placeholder in {blocker['id']} distractor: {text!r}")
    return text


def inject_distractor(
    text: str,
    blocker: dict[str, Any],
    style: str,
    index: int = 0,
    value: Any = None,
) -> tuple[str, tuple[int, int], str]:
    """Inject a near-miss: same topic as a blocker, but not binding.

    Flagging one of these is a false alarm, which is how the false-alarm rate
    becomes measurable at all. The guard here refuses any distractor phrased as
    a hard requirement, since that would make it a genuine blocker sitting in a
    posting labelled APPLY.
    """
    sentence = render_distractor(blocker, index, value)

    binding = binding_language(sentence)
    if binding:
        raise ValueError(
            f"{blocker['id']} distractor {index} uses mandatory language {binding}; "
            f"that makes it a real blocker, not a near-miss: {sentence!r}"
        )

    new_text, span = insert(text, sentence, style)
    return new_text, span, sentence


def inject_blocker(
    text: str,
    blocker: dict[str, Any],
    style: str,
    profile: dict[str, Any],
    value: Any = None,
) -> tuple[str, tuple[int, int], str]:
    """Inject a blocker, refusing to inject one that does not actually block.

    The refusal is the point. A blocker that does not disqualify this profile
    would be labelled SKIP while the true verdict is APPLY, and an agent that
    read the posting correctly would be scored wrong. Catching it here means
    the corpus cannot be generated in that state at all.
    """
    if not blocks(blocker, profile, value):
        raise ValueError(
            f"{blocker['id']} with value {value!r} does not block this profile; "
            f"injecting it would invert the label for this posting"
        )
    sentence = render(blocker, style, value)
    new_text, span = insert(text, sentence, style)
    return new_text, span, sentence
