"""One place that talks to the API, so every system is billed and configured alike.

The baseline and every agent variant call through here, which is how EVAL.md 9's
"same model, same effort" invariant stays true without each variant remembering
to honour it.

Sampling parameters were removed on this model generation — there is no
temperature to set. Effort is the equivalent dial and is read from the
environment, so a variant cannot quietly raise its own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic


def _load_dotenv() -> None:
    """Read .env into the environment if the shell hasn't already.

    REPRODUCE.md asks for `set -a; source .env; set +a`, and forgetting it in a
    fresh shell surfaced as a missing key several frames deep in a traceback.
    It also silently unpinned MODEL_ID, which would break the "same model"
    invariant this module exists to hold.

    Existing values win, so an inline `MODEL_ID=... python -m ...` still
    overrides the file.
    """
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()

# USD per million tokens. Verified against the pricing table on 2026-08-30.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_EFFORT = "medium"

# Outputs here are a few hundred tokens, but adaptive thinking is billed as
# output and counts against this ceiling. 8000 leaves room without inviting a
# truncated response, which would read as a parse failure rather than a cap.
MAX_TOKENS = 8000


def model_id() -> str:
    return os.environ.get("MODEL_ID", DEFAULT_MODEL)


def effort() -> str:
    return os.environ.get("EFFORT", DEFAULT_EFFORT)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in PRICING:
        raise KeyError(f"no pricing for {model!r}; add it to PRICING before running")
    per_in, per_out = PRICING[model]
    return input_tokens * per_in / 1_000_000 + output_tokens * per_out / 1_000_000


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        self.cache_creation_input_tokens += other.cache_creation_input_tokens
        self.calls += other.calls
        self.cost_usd += other.cost_usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


@dataclass
class Response:
    text: str
    usage: Usage
    stop_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set, and no .env at the repository root "
            "supplied one. Copy .env.example to .env and add your key."
        )

    # An identity-linked key belongs to an organisation rather than to a single
    # workspace, so the API cannot infer which workspace to bill and returns a
    # 400 until one is named.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    return anthropic.Anthropic(default_headers=headers)


def call(
    system: str,
    user: str,
    model: str | None = None,
    effort_level: str | None = None,
    max_tokens: int = MAX_TOKENS,
    client: anthropic.Anthropic | None = None,
) -> Response:
    """One request. Returns the text, token usage, and computed cost."""
    model = model or model_id()
    client = client or _client()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort_level or effort()},
    )

    text = "".join(block.text for block in message.content if block.type == "text")
    raw_usage = message.usage
    usage = Usage(
        input_tokens=raw_usage.input_tokens,
        output_tokens=raw_usage.output_tokens,
        cache_read_input_tokens=getattr(raw_usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0) or 0,
        calls=1,
    )
    usage.cost_usd = cost_usd(model, usage.input_tokens, usage.output_tokens)

    return Response(
        text=text,
        usage=usage,
        stop_reason=message.stop_reason,
        raw={"id": message.id, "model": message.model, "stop_reason": message.stop_reason},
    )
