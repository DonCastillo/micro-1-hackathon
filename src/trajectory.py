"""Record every model call, so the trajectories deliverable costs nothing later.

Deliverable 4 asks for representative trajectories for *every* agent used —
instructions through tool responses to final result, including retries. Built
now, in the baseline, every later variant inherits it. Reconstructed on Sunday
night from memory, it would be fiction.

The recorder wraps `llm.call` rather than sitting beside it, so a variant
cannot make an unrecorded request. That matters more than it sounds: the calls
most worth having in a trajectory are the retries and the verification passes,
which are exactly the ones an author forgets to log by hand.

Layout:

    runs/20260830-142317_baseline/
      manifest.json     model, effort, corpus digest, git sha, totals
      jd_01.json        every step for that posting, in order
      ...
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import llm

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def corpus_digest(corpus: Path) -> str:
    """Which corpus this run scored against, so results cannot be misattributed."""
    digest = hashlib.sha256()
    for path in sorted(corpus.glob("jd_*.md")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


@dataclass
class Step:
    name: str
    system: str
    user: str
    output: str
    usage: dict[str, Any]
    seconds: float
    stop_reason: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "system": self.system,
            "user": self.user,
            "output": self.output,
            "usage": self.usage,
            "seconds": round(self.seconds, 3),
            "stop_reason": self.stop_reason,
            "note": self.note,
        }


@dataclass
class Trajectory:
    """One posting's full history. Steps are appended in the order they ran."""

    posting_id: str
    steps: list[Step] = field(default_factory=list)
    usage: llm.Usage = field(default_factory=llm.Usage)
    prediction: dict[str, Any] | None = None
    started: float = field(default_factory=time.monotonic)

    def call(
        self,
        name: str,
        system: str,
        user: str,
        note: str | None = None,
        **kwargs: Any,
    ) -> llm.Response:
        """Make a recorded model call. The only way a variant should call out."""
        began = time.monotonic()
        response = llm.call(system, user, **kwargs)
        elapsed = time.monotonic() - began

        self.usage.add(response.usage)
        self.steps.append(
            Step(
                name=name,
                system=system,
                user=user,
                output=response.text,
                usage=response.usage.to_dict(),
                seconds=elapsed,
                stop_reason=response.stop_reason,
                note=note,
            )
        )
        return response

    def note(self, name: str, text: str) -> None:
        """Record something that shaped the next step but was not a model call.

        Retries, verification rejections, and human checkpoints belong here —
        deliverable 4 asks for the feedback that shaped each next step, and a
        trace of prompts alone does not show why the second one differed.
        """
        self.steps.append(
            Step(name=name, system="", user="", output=text, usage={}, seconds=0.0, note="event")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "posting_id": self.posting_id,
            "steps": [s.to_dict() for s in self.steps],
            "usage": self.usage.to_dict(),
            "seconds": round(time.monotonic() - self.started, 3),
            "prediction": self.prediction,
        }


class Recorder:
    """A run: many trajectories plus the manifest that makes them reproducible."""

    def __init__(
        self,
        system: str,
        corpus: Path,
        root: Path | None = None,
        stamp: str | None = None,
    ) -> None:
        stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.dir = (root or RUNS) / f"{stamp}_{system}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.system = system
        self.corpus = corpus
        self.started = time.monotonic()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.total = llm.Usage()
        self.trajectories: list[Trajectory] = []

    def trajectory(self, posting_id: str) -> Trajectory:
        traj = Trajectory(posting_id=posting_id)
        self.trajectories.append(traj)
        return traj

    def finish(self, traj: Trajectory, prediction: dict[str, Any]) -> None:
        """Close one posting: attach its prediction and write it to disk."""
        traj.prediction = prediction
        self.total.add(traj.usage)
        (self.dir / f"{traj.posting_id}.json").write_text(
            json.dumps(traj.to_dict(), indent=2) + "\n"
        )

    def write_manifest(self, extra: dict[str, Any] | None = None) -> Path:
        manifest = {
            "system": self.system,
            "started_at": self.started_at,
            "seconds": round(time.monotonic() - self.started, 1),
            "model": llm.model_id(),
            "effort": llm.effort(),
            "corpus": str(self.corpus),
            "corpus_digest": corpus_digest(self.corpus),
            "git_sha": _git_sha(),
            "python": platform.python_version(),
            "postings": len(self.trajectories),
            "parse_failures": sum(
                1 for t in self.trajectories if (t.prediction or {}).get("parse_error")
            ),
            "usage": self.total.to_dict(),
            **(extra or {}),
        }
        path = self.dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        return path


def render_markdown(trajectory: dict[str, Any]) -> str:
    """Human-readable trace, for the curated trajectories in step 7.3.

    A judge should be able to follow instructions -> calls -> result without
    reading JSON.
    """
    lines = [
        f"# Trajectory: {trajectory['posting_id']}",
        "",
        f"{len(trajectory['steps'])} steps, {trajectory['seconds']}s, "
        f"${trajectory['usage'].get('cost_usd', 0):.4f}",
        "",
    ]
    for i, step in enumerate(trajectory["steps"], start=1):
        if step.get("note") == "event":
            lines += [f"## {i}. {step['name']} _(event)_", "", step["output"], ""]
            continue
        lines += [
            f"## {i}. {step['name']}",
            "",
            f"_{step['seconds']}s · {step['usage'].get('input_tokens', 0)} in / "
            f"{step['usage'].get('output_tokens', 0)} out_",
            "",
            "**System**", "", "```", step["system"].strip(), "```", "",
            "**User**", "", "```", step["user"].strip(), "```", "",
            "**Output**", "", "```", step["output"].strip(), "```", "",
        ]
    if trajectory.get("prediction"):
        lines += ["## Result", "", "```json",
                  json.dumps(trajectory["prediction"], indent=2), "```", ""]
    return "\n".join(lines)
