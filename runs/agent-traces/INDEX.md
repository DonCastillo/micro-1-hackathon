# Coding-agent traces

The challenge requires disclosing which coding agents were used and submitting the
trajectories. This directory holds them.

**Everything in this repository — code, tests, corpus, documentation and analysis — was
written by Claude Opus 5 running in Claude Code**, directed turn by turn by the participant.
Every commit records this in its trailer:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

## What is here

| File | What it is |
|---|---|
| `claude-code-session.jsonl` | The complete session transcript, 2,844 entries, ~4.9 MB |
| `human-checkpoints.md` | Every instruction the participant gave, in order — 115 turns |

There is a second, different set of traces under **`runs/curated/`**. Those are the
*product's* trajectories — the blocker detector calling the API on a job posting. These
are the *development* trajectories — the coding agent building the product. The submission
includes both because the deliverable is ambiguous between them.

## The session in numbers

| | |
|---|---|
| Agent | Claude Opus 5 via Claude Code |
| Human turns | 115 |
| Tool calls | 288 |
| Bash | 201 |
| Write / Edit | 46 / 22 |
| Duration | 2026-08-29 to 2026-08-31 |
| Commits produced | 30 |

## How to read the transcript

Newline-delimited JSON. Each line is one event; `type` distinguishes them. The two that
matter:

```bash
# what the human asked for
jq -r 'select(.type=="user") | .message.content' claude-code-session.jsonl

# what the agent did
jq -r 'select(.type=="assistant") | .message.content[]?
       | select(.type=="tool_use") | .name' claude-code-session.jsonl
```

`human-checkpoints.md` is the readable version of the first of those.

## What the checkpoints show

The interesting parts of this trace are the places where the human **redirected** the agent,
because those are where the project's design was actually decided:

- **Choosing the problem.** The agent proposed several candidates; the participant supplied
  the domain (active job search) and the budget constraint, and the agent recommended
  against the two closest to the brief's own worked examples.
- **A fairness decision put to the participant.** When the baseline's freeform prose proved
  unparseable, the agent stopped and presented the options rather than picking — because
  changing the baseline's prompt affects every number downstream. Recorded in `EVAL.md` §10.
- **A security correction.** The participant's API key was pasted into the session by an
  editor selection. The agent flagged it, the key was rotated, and the participant instructed
  that `.env` never be read again — an instruction the agent then held for the rest of the
  session.
- **Scope decisions.** Whether to harden the corpus after a strong baseline, whether to keep
  decomposition, whether to run the ablation. Each was raised with evidence and decided
  explicitly.

## Redaction

Applied to parsed JSON string values, not to the raw text:

| Pattern | Replacement | Count |
|---|---|---|
| `sk-ant-…` | `[REDACTED_API_KEY]` | 1 |
| `wrkspc_…` | `[REDACTED_WORKSPACE_ID]` | 0 |
| Email addresses | `[REDACTED_EMAIL]` | 41 |

The API key redacted here had already been rotated before this export, after it was
accidentally pasted into the session.

**Why value-level and not text-level:** the first attempt substituted on raw bytes and
corrupted 37 lines, because this project's own source contains regular expressions that the
email pattern matched inside — destroying their JSON escaping. The export was rebuilt by
parsing each line, walking the structure, redacting string values, and re-serialising.
Verified afterwards: 0 unparseable lines, 0 keys, 0 workspace ids, 0 real addresses.

Nothing else was removed. The transcript includes the agent's mistakes, the tests that
failed, and the claims that were later corrected.
