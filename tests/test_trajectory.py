"""Trajectory capture, exercised end to end against a fake client.

Deliverable 4 wants instructions through responses to result, including the
feedback that shaped each next step. The tests below check that a multi-step
run with a retry is fully recoverable from disk afterwards — because that is
the only state in which the deliverable is free rather than reconstructed.

No API calls: `llm.call` takes a client, so a stub stands in.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from src import llm
from src.trajectory import Recorder, corpus_digest, render_markdown

CORPUS = Path(__file__).resolve().parent.parent / "data/corpus"


# ─── a stand-in for the SDK ───────────────────────────────────────────────

@dataclass
class _Usage:
    input_tokens: int = 1000
    output_tokens: int = 200
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Message:
    content: list
    usage: _Usage
    stop_reason: str = "end_turn"
    id: str = "msg_test"
    model: str = "claude-sonnet-5"


class FakeClient:
    """Returns canned replies and records what it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []
        self.messages = self

    def create(self, **kwargs):
        self.seen.append(kwargs)
        return _Message(content=[_Block(self.replies.pop(0))], usage=_Usage())


@pytest.fixture
def fake(monkeypatch):
    def _make(replies):
        client = FakeClient(replies)
        monkeypatch.setattr(llm, "_client", lambda: client)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
        monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")
        return client

    return _make


# ─── recording ────────────────────────────────────────────────────────────

def test_a_single_call_is_captured_whole(tmp_path, fake):
    fake(["Skip it — work_authorization."])
    rec = Recorder("baseline", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_01")
    traj.call("ask", "SYSTEM TEXT", "USER TEXT")
    rec.finish(traj, {"verdict": "SKIP"})

    saved = json.loads((rec.dir / "jd_01.json").read_text())
    step = saved["steps"][0]
    assert step["name"] == "ask"
    assert step["system"] == "SYSTEM TEXT"
    assert step["user"] == "USER TEXT"
    assert step["output"] == "Skip it — work_authorization."
    assert step["usage"]["input_tokens"] == 1000
    assert step["seconds"] >= 0
    assert saved["prediction"] == {"verdict": "SKIP"}


def test_multi_step_order_is_preserved(tmp_path, fake):
    """Agent variants make several calls per posting; order is the story."""
    fake(["legal check", "logistics check", "verification"])
    rec = Recorder("agent", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_04")
    for name in ("check_legal", "check_logistics", "verify"):
        traj.call(name, "s", "u")
    rec.finish(traj, {"verdict": "SKIP"})

    saved = json.loads((rec.dir / "jd_04.json").read_text())
    assert [s["name"] for s in saved["steps"]] == ["check_legal", "check_logistics", "verify"]
    assert saved["usage"]["calls"] == 3


def test_notes_record_what_shaped_the_next_step(tmp_path, fake):
    """A trace of prompts alone does not explain why the second one differed."""
    fake(["bad output", "good output"])
    rec = Recorder("agent", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_07")
    traj.call("attempt", "s", "u")
    traj.note("retry", "verification rejected the claim: quote not found in posting")
    traj.call("attempt_2", "s", "u2")
    rec.finish(traj, {"verdict": "SKIP"})

    saved = json.loads((rec.dir / "jd_07.json").read_text())
    assert [s["name"] for s in saved["steps"]] == ["attempt", "retry", "attempt_2"]
    assert saved["steps"][1]["note"] == "event"
    assert "verification rejected" in saved["steps"][1]["output"]
    assert saved["usage"]["calls"] == 2, "a note is not a model call"


def test_usage_and_cost_accumulate_across_steps(tmp_path, fake):
    fake(["a", "b"])
    rec = Recorder("agent", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_01")
    traj.call("one", "s", "u")
    traj.call("two", "s", "u")
    rec.finish(traj, {})

    expected = llm.cost_usd("claude-sonnet-5", 2000, 400)
    assert traj.usage.cost_usd == pytest.approx(expected)
    assert rec.total.cost_usd == pytest.approx(expected)


def test_recording_cannot_be_skipped(tmp_path, fake):
    """The recorder wraps the call rather than sitting beside it.

    The retries and verification passes are the steps most worth having and
    the ones an author most reliably forgets to log by hand.
    """
    client = fake(["x"])
    rec = Recorder("agent", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_01")
    traj.call("step", "s", "u")
    assert len(client.seen) == 1
    assert len(traj.steps) == 1, "every call the client saw must appear in the trace"


# ─── manifest ─────────────────────────────────────────────────────────────

def test_manifest_pins_what_the_run_depended_on(tmp_path, fake):
    fake(["ok"])
    rec = Recorder("baseline", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_01")
    traj.call("ask", "s", "u")
    rec.finish(traj, {"verdict": "APPLY"})
    manifest = json.loads(rec.write_manifest().read_text())

    assert manifest["model"] == "claude-sonnet-5"
    assert manifest["effort"] in ("low", "medium", "high", "xhigh", "max")
    assert manifest["corpus_digest"] == corpus_digest(CORPUS)
    assert manifest["postings"] == 1
    assert manifest["usage"]["cost_usd"] > 0
    assert "python" in manifest


def test_corpus_digest_detects_a_changed_corpus(tmp_path):
    """Results must not be attributable to a corpus that has since changed."""
    before = corpus_digest(CORPUS)
    copy = tmp_path / "corpus"
    copy.mkdir()
    for path in CORPUS.glob("jd_*.md"):
        (copy / path.name).write_text(path.read_text())
    assert corpus_digest(copy) == before

    (copy / "jd_01.md").write_text("edited")
    assert corpus_digest(copy) != before


def test_manifest_counts_parse_failures(tmp_path, fake):
    fake(["nonsense", "ok"])
    rec = Recorder("baseline", corpus=CORPUS, root=tmp_path)
    for posting_id, prediction in (
        ("jd_01", {"verdict": "APPLY", "parse_error": "no verdict found"}),
        ("jd_02", {"verdict": "SKIP"}),
    ):
        traj = rec.trajectory(posting_id)
        traj.call("ask", "s", "u")
        rec.finish(traj, prediction)
    assert json.loads(rec.write_manifest().read_text())["parse_failures"] == 1


# ─── rendering for the deliverable ────────────────────────────────────────

def test_markdown_render_is_followable(tmp_path, fake):
    fake(["first answer", "second answer"])
    rec = Recorder("agent", corpus=CORPUS, root=tmp_path)
    traj = rec.trajectory("jd_11")
    traj.call("check", "SYS", "USER ONE")
    traj.note("retry", "quote not found")
    traj.call("recheck", "SYS", "USER TWO")
    rec.finish(traj, {"verdict": "SKIP", "blockers": []})

    out = render_markdown(json.loads((rec.dir / "jd_11.json").read_text()))
    assert "# Trajectory: jd_11" in out
    assert "## 1. check" in out and "## 3. recheck" in out
    assert "_(event)_" in out, "notes must be visibly different from calls"
    assert "USER ONE" in out and "first answer" in out
    assert "## Result" in out
