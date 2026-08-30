"""The invariant the whole benchmark rests on.

Every blocker in the taxonomy must actually disqualify the candidate in
data/profile/candidate.yaml, and every distractor must not. If that stops
being true, the injector will happily produce a posting labelled SKIP whose
correct verdict is APPLY — the corpus still generates, the eval still runs,
and every number downstream is quietly wrong.
"""

import pytest

from src.rules import blocks, load_profile, load_taxonomy

TAXONOMY = load_taxonomy()
PROFILE = load_profile()
BLOCKERS = TAXONOMY["blockers"]


def _ids(blocker):
    return blocker["id"]


@pytest.mark.parametrize("blocker", [b for b in BLOCKERS if b["kind"] == "absolute"], ids=_ids)
def test_absolute_blocker_blocks_the_candidate(blocker):
    assert blocks(blocker, PROFILE), (
        f"{blocker['id']} does not block the profile, so any posting injected with it "
        f"would be mislabelled SKIP when the correct verdict is APPLY"
    )


@pytest.mark.parametrize("blocker", [b for b in BLOCKERS if b["kind"] == "parametric"], ids=_ids)
def test_every_blocking_value_blocks_the_candidate(blocker):
    """Not just one value — the injector samples freely from this list."""
    for value in blocker["blocking_values"]:
        assert blocks(blocker, PROFILE, value), (
            f"{blocker['id']} with {blocker['parameter']}={value!r} does not block the "
            f"profile; remove it from blocking_values or adjust the profile"
        )


def test_profile_defines_every_field_the_taxonomy_reads():
    missing = {b["profile_field"] for b in BLOCKERS} - set(PROFILE)
    assert not missing, f"profile is missing fields referenced by the taxonomy: {sorted(missing)}"


def test_years_distractor_is_not_a_blocker():
    """The dominant false-alarm mode, pinned as a test.

    'preferred' is not 'required'. The distractor names a figure above the
    candidate's experience precisely so that a system keying on the number
    rather than the modality gets it wrong.
    """
    yoe = next(b for b in BLOCKERS if b["id"] == "years_of_experience")
    assert "8+ years of experience preferred." in yoe["distractors"]
    assert PROFILE["years_experience"] < 8, (
        "the years distractor only works as a trap if its figure exceeds the "
        "candidate's actual experience"
    )


def test_comp_distractor_clears_the_floor():
    comp = next(b for b in BLOCKERS if b["id"] == "compensation_floor")
    assert not blocks(comp, PROFILE, 195000), "the comp distractor band must not block"
    assert all(blocks(comp, PROFILE, v) for v in comp["blocking_values"])
