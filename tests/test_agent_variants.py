"""Variant prompts, checked for the one failure that would invalidate everything.

`data/taxonomy.yaml` holds the exact sentences the injector plants in the
corpus. Showing them to a variant would let it string-match its way to a high
score that measures nothing — the agent would be answering an exam it had been
handed the answers to, and no amount of careful scoring downstream would
detect it.

These tests are the guard, and they run against every variant automatically,
so a future iteration that pastes the taxonomy wholesale fails the suite.
"""

import pytest
import yaml

from src.agent.variants import ITER1_PROMPT, VARIANTS, blocker_definitions
from src.rules import load_profile, load_taxonomy

TAXONOMY = load_taxonomy()
PROFILE = load_profile()
BLOCKERS = TAXONOMY["blockers"]


def _prompt_for(variant_name: str) -> str:
    """Every prompt a variant would send for a representative posting."""
    from src.trajectory import Trajectory

    captured: list[str] = []

    class _Capture(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            captured.append(system + "\n" + user)
            raise _Stop

    class _Stop(Exception):
        pass

    variant = VARIANTS[variant_name]
    posting = "# Role\nRemote (United States)\n\n## Requirements\n- 5+ years\n"
    try:
        variant.predict(posting, PROFILE, TAXONOMY, _Capture(posting_id="jd_test"))
    except _Stop:
        pass
    return "\n".join(captured)


# ─── leakage: the test that protects the whole result ─────────────────────

@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_no_variant_leaks_injected_phrasings(name):
    """The exact sentences planted in the corpus must never reach the model."""
    prompt = _prompt_for(name).lower()
    for blocker in BLOCKERS:
        for style, phrasing in blocker["phrasings"].items():
            stem = phrasing.split("{")[0].strip().lower()
            if len(stem) > 25:
                assert stem not in prompt, (
                    f"{name} leaks {blocker['id']}/{style} — the model would be "
                    f"string-matching the answer key"
                )


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_no_variant_leaks_distractors(name):
    prompt = _prompt_for(name).lower()
    for blocker in BLOCKERS:
        for distractor in blocker["distractors"]:
            stem = distractor.split("{")[0].strip().lower()
            if len(stem) > 25:
                assert stem not in prompt, f"{name} leaks a {blocker['id']} distractor"


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_no_variant_leaks_blocking_values(name):
    """The sampled values are corpus content too — "10 years", "Austin, TX"."""
    prompt = _prompt_for(name)
    for blocker in BLOCKERS:
        for value in blocker.get("blocking_values") or []:
            if isinstance(value, str) and len(value) > 6:
                assert value not in prompt, f"{name} leaks blocking value {value!r}"


def test_definitions_exclude_the_answer_key_but_keep_the_meaning():
    text = blocker_definitions(TAXONOMY)
    for blocker in BLOCKERS:
        assert blocker["id"] in text
        assert blocker["description"] in text
        assert blocker["profile_field"] in text
        assert blocker["phrasings"]["explicit"] not in text


# ─── iteration 1 targets the measured failure ─────────────────────────────

def test_definitions_distinguish_the_confusable_pairs():
    """The baseline conflated these 15 times across 3 runs.

    What separates them is which profile field decides them, so the
    definitions must carry that.
    """
    text = blocker_definitions(TAXONOMY)
    assert "citizenship_required" in text and "`citizenship`" in text
    assert "work_authorization" in text and "`work_auth`" in text
    assert "onsite_location" in text and "`location`" in text
    assert "relocation_required" in text and "`willing_to_relocate`" in text


def test_iteration1_keeps_the_baseline_output_contract():
    """Only one thing changes per iteration. The format is not it."""
    assert "VERDICT: APPLY or SKIP" in ITER1_PROMPT
    assert "BLOCKERS:" in ITER1_PROMPT
    assert "json" not in ITER1_PROMPT.lower(), "structured output is a later iteration"


def test_iteration1_withholds_what_later_iterations_add():
    prompt = _prompt_for("iter1").lower()
    for later in ("verbatim", "quote the", "json schema", "step by step", "verify each"):
        assert later not in prompt, f"iter1 must not include {later!r}"


def test_iteration1_states_the_preference_rule_without_naming_a_distractor():
    """Naming "8+ years preferred" would be handing over a specific case."""
    assert "A preference is not a requirement." in ITER1_PROMPT
    assert "8+" not in ITER1_PROMPT


def test_every_variant_declares_itself():
    for name, variant in VARIANTS.items():
        assert variant.name == name
        assert variant.description


# ─── iteration 2: decomposition ───────────────────────────────────────────

def test_iteration2_asks_one_question_per_group():
    """Four narrower questions, not four copies of the same one."""
    from src.trajectory import Trajectory

    calls = []

    class _Capture(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            calls.append((name, user))

            class _R:
                text = "BLOCKERS: NONE"

            return _R()

    VARIANTS["iter2"].predict("# Role\nRemote (United States)\n", PROFILE, TAXONOMY,
                              _Capture(posting_id="jd_test"))
    names = [n for n, _ in calls]
    assert names == [f"check_{g}" for g in TAXONOMY["groups"]]
    assert len(set(u for _, u in calls)) == 4, "each group must get a different prompt"


def test_each_group_check_sees_only_its_own_conditions():
    """Otherwise it is four identical passes, not a decomposition."""
    from src.trajectory import Trajectory

    prompts = {}

    class _Capture(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            prompts[name] = user

            class _R:
                text = "BLOCKERS: NONE"

            return _R()

    VARIANTS["iter2"].predict("# Role\n", PROFILE, TAXONOMY, _Capture(posting_id="jd_test"))
    for group in TAXONOMY["groups"]:
        text = prompts[f"check_{group}"]
        # Match the rendered definition line, not a bare id: the profile block
        # legitimately contains `employment_types`, which has the id
        # `employment_type` inside it.
        for blocker in TAXONOMY["blockers"]:
            line = f"- {blocker['id']} ({blocker['group']}):"
            if blocker["group"] == group:
                assert line in text, f"{group} check is missing {blocker['id']}"
            else:
                assert line not in text, f"{group} check leaks {blocker['id']}"


def test_iteration2_merges_and_deduplicates():
    from src.trajectory import Trajectory

    replies = iter([
        "BLOCKERS: work_authorization",
        "BLOCKERS: onsite_location",
        "BLOCKERS: NONE",
        "BLOCKERS: NONE",
    ])

    class _Fake(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            class _R:
                text = next(replies)

            return _R()

    p = VARIANTS["iter2"].predict("# Role\n", PROFILE, TAXONOMY, _Fake(posting_id="jd_test"))
    assert p.verdict == "SKIP"
    assert sorted(c.type for c in p.blockers) == ["onsite_location", "work_authorization"]


def test_iteration2_returns_apply_when_no_group_finds_anything():
    from src.trajectory import Trajectory

    class _Fake(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            class _R:
                text = "BLOCKERS: NONE"

            return _R()

    p = VARIANTS["iter2"].predict("# Role\n", PROFILE, TAXONOMY, _Fake(posting_id="jd_test"))
    assert p.verdict == "APPLY" and p.blockers == []


# ─── iteration 3: evidence ────────────────────────────────────────────────

def _fake_traj(replies):
    from src.trajectory import Trajectory

    it = iter(replies)

    class _Fake(Trajectory):
        def call(self, name, system, user, **kw):  # type: ignore[override]
            class _R:
                text = next(it)

            return _R()

    return _Fake(posting_id="jd_test")


def test_iteration3_carries_evidence_through():
    p = VARIANTS["iter3"].predict(
        "# Role\n", PROFILE, TAXONOMY,
        _fake_traj([
            '{"blockers": [{"type": "citizenship_required", "evidence": "U.S. Persons only."}]}',
            '{"blockers": []}', '{"blockers": []}', '{"blockers": []}',
        ]),
    )
    assert p.verdict == "SKIP"
    assert p.blockers[0].evidence == "U.S. Persons only."


def test_iteration3_rejects_a_claim_from_the_wrong_group():
    """A logistics check may not report a legal blocker.

    Without this, decomposition collapses: one over-eager group could claim
    everything and the split would stop meaning anything.
    """
    p = VARIANTS["iter3"].predict(
        "# Role\n", PROFILE, TAXONOMY,
        _fake_traj([
            '{"blockers": []}',
            '{"blockers": [{"type": "citizenship_required", "evidence": "x"}]}',
            '{"blockers": []}', '{"blockers": []}',
        ]),
    )
    assert p.blockers == [], "a legal claim from the logistics check must be dropped"


def test_iteration3_survives_unparseable_group_output():
    """One bad group reply must not lose the other three."""
    p = VARIANTS["iter3"].predict(
        "# Role\n", PROFILE, TAXONOMY,
        _fake_traj([
            "I could not determine this.",
            '{"blockers": [{"type": "onsite_location", "evidence": "Austin office."}]}',
            '{"blockers": []}', '{"blockers": []}',
        ]),
    )
    assert [c.type for c in p.blockers] == ["onsite_location"]


def test_iteration3_asks_for_verbatim_quotes():
    from src.agent.variants import ITER3_GROUP_PROMPT

    assert "exactly as it appears" in ITER3_GROUP_PROMPT
    assert "do not paraphrase" in ITER3_GROUP_PROMPT.lower()
    assert "if you cannot find a sentence" in ITER3_GROUP_PROMPT.lower()
