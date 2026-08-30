# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

There is no code here yet. The directory currently holds only the competition brief
(`micro1 - First Hackathon97ce7c5.pdf`) and is not a git repository. The sections below
capture the brief's requirements, since they constrain what gets built. **Once a stack is
chosen, replace the "Commands" and "Architecture" placeholders with real content** — build,
test (including how to run a single test), baseline, and evaluation commands.

## What this project is

A submission for the **micro1 Agentic Workflows Hackathon**: pick a specific, well-understood
problem and use agents to solve it, with evidence that the solution improves on how the task
is handled today.

Every design decision should trace back to four questions from the brief:
1. Who has this problem?
2. What bottleneck makes it worth solving?
3. Does the agent solve it well?
4. Can another person reproduce the result?

## Required deliverables

These four items shape the repository layout — expect to maintain them alongside the code,
not at the end:

1. **Solution code + Improvement Changelog** — full project plus everything needed to run it,
   including the instructions that shape each agent. The README introduces the intended user
   and their bottleneck, then carries a clearly labeled `Improvement Changelog`.
2. **Reproduction guide** — written for someone on a clean environment: setup, exact commands
   for solution / baseline / evaluation, required data, expected output, tool versions,
   approximate runtime and cost.
3. **Solution video** (≤5 min) — problem and baseline, one realistic end-to-end execution,
   final comparison, changelog highlights.
4. **Agent trajectories** — representative traces for *every* agent used: instructions →
   tool calls and responses → final result, including retries and human checkpoints.

## Baseline and evaluation (non-negotiable structure)

A **simple baseline** must exist and be committed: one direct prompt, one general-purpose
agent with basic tools, a simple script/template, or the manual process people use today.
Baseline and final solution get the **same task and the same evaluation cases** — any
difference in available resources must be explained.

Evaluation uses one **primary metric** reflecting what success means to the user, plus human
time per task and cost per task. Define what a good final result looks like *before* running.
Ten or more cases when the task allows, including at least one deliberately challenging case.
If that format fits poorly, design and propose an explicit scoring rubric instead.

The changelog carries columns: stage / what you tried and why / evidence / decision-learning.
One entry per meaningful experiment, including experiments that were later removed and what
they taught. Every claim in the writeup must point to submitted evidence.

## Judging weights (100 pts)

| Criterion | Pts |
|---|---|
| Agent Solution & Engineering | 30 |
| End-to-End Quality | 20 |
| Problem & User Value | 15 |
| Measured Improvement | 15 |
| Reproducibility | 15 |
| Hot Take / Insights | 5 |

Engineering is the largest bucket: purposeful use of context, tools, memory, verification,
skills, or orchestration — judged on whether each choice made the agent reach the goal more
reliably, **not** on component count. End-to-End Quality specifically penalizes output that
"reads as clearly AI generated" rather than something a person would sign their name to.

## Ground rules that affect implementation

- Consequential actions stay behind a sandbox or simulation, with human approval before the
  action happens. Any solution that could significantly affect someone needs a qualified
  human reviewer in the loop.
- Use public, synthetic, or approved-anonymous data. No credentials or private information in
  the submission.
- Make explicit in the README what existed before the competition and what was added here.
- Judges must be able to run the project and reproduce the main result.

## Commands

_TBD — fill in once the stack exists: install, run solution, run baseline, run evaluation,
run a single test._

## Architecture

_TBD — document the agent topology (which agents, what each one's instructions and tools are,
how they hand off), where evaluation cases live, and where trajectories are written._
