---
name: openclaw-bindings-status
description: Inspect OpenClaw agent and channel binding status and present it in a clear, visual way. Use when the user asks which agent is bound to which channel, wants to inspect single-chat or group routing scope, wants a readable summary of `openclaw agents list --bindings`, or wants help understanding OpenClaw binding and workspace status without reading raw CLI output.
---

# OpenClaw Bindings Status

## Overview

Use this skill to turn OpenClaw binding data into a readable status report. Prefer a compact Markdown dashboard over raw CLI output, and include a Mermaid wiring diagram when bindings are detailed enough to visualize.

## Workflow

1. Prefer JSON output so the rendering is stable:

   ```bash
   openclaw agents list --bindings --json
   ```

2. If that fails, fall back to:

   ```bash
   openclaw agents list --json
   openclaw agents bindings --json
   ```

   Merge the agent list with the binding list before summarizing.

3. Render the result with the bundled script:

   ```bash
   python3 scripts/render_openclaw_bindings.py
   ```

   To debug or reuse captured output, pipe JSON in through stdin:

   ```bash
   openclaw agents list --bindings --json | python3 scripts/render_openclaw_bindings.py --stdin
   ```

4. If `openclaw` is not installed or JSON output is unavailable, tell the user directly and ask for either:
   - a pasted CLI output, or
   - a local environment where `openclaw` is on `PATH`

## Output Contract

Return the result as a small dashboard with these sections when data is available:

- `Summary`: total agents, default agents, total bindings, channel count, wildcard count, peer-scope count.
- `Agent Table`: one row per agent with workspace, default status, binding count, and channel list.
- `Wiring View`: short line-based routes such as `[telegram / group:-100123] --> [ops-agent]`.
- `Mermaid`: a `flowchart LR` block when bindings contain enough detail to draw useful edges.
- `Notes`: call out unbound agents, wildcard routes, or ambiguous rules.

## Interpretation Rules

- Treat `accountId: "*"` as a wildcard channel fallback.
- Treat `match.peer.kind` and `match.peer.id` as routing scope, not as authorization policy.
- Call out bindings that have only a channel and no peer or account details as broad/default routes.
- If multiple bindings target the same agent and channel with different scopes, preserve all of them instead of collapsing them.
- If workspace data is missing, say that the binding data was available but workspace metadata was not.
