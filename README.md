# openclaw-bindings-status

[简体中文](./README.zh-CN.md)

`openclaw-bindings-status` is a lightweight OpenClaw skill that turns `openclaw agents list --bindings` output into a clearer status dashboard.

Instead of asking users to read raw CLI payloads, this skill lets them ask in natural language which agents are bound to which channels, how DM and group routing works, and which workspaces are currently in play.

## Features

- Summarize agent and workspace status in a compact dashboard
- Group bindings by channel, account, and peer scope
- Render readable Markdown tables
- Generate a Mermaid wiring diagram for route visualization
- Keep dependencies minimal by using only the Python standard library

## Example Prompts

- "Show me my OpenClaw bindings status"
- "Which agent is bound to Telegram group chats?"
- "Visualize my OpenClaw agent-channel bindings"
- "Explain the result of `openclaw agents list --bindings`"

## Installation

Clone this repository into your skills directory and keep the folder name as `openclaw-bindings-status`:

```bash
git clone https://github.com/sleep9ull/openclaw-bindings-status.git "${CODEX_HOME:-$HOME/.codex}/skills/openclaw-bindings-status"
```

## Usage

The skill prefers JSON output because it is easier to parse reliably:

```bash
openclaw agents list --bindings --json
```

For local debugging, run the renderer directly:

```bash
python3 scripts/render_openclaw_bindings.py
```

If you already captured JSON output, pipe it into stdin:

```bash
openclaw agents list --bindings --json | python3 scripts/render_openclaw_bindings.py --stdin
```

You can also render a saved JSON file:

```bash
python3 scripts/render_openclaw_bindings.py --from-json ./bindings.json
```

## Output

The renderer produces a small Markdown dashboard with:

- `Summary`: totals for agents, bindings, channels, wildcard routes, and peer-scoped routes
- `Agent Table`: agent, workspace, default status, binding count, and channel coverage
- `Wiring View`: line-by-line readable routes
- `Mermaid`: optional `flowchart LR` graph for visual inspection
- `Notes`: warnings for wildcard bindings, missing metadata, or unbound agents

## Limitations

- The script works best when `openclaw` supports JSON output.
- If `openclaw` is not available on `PATH`, use `--stdin` or `--from-json`.
- The exact JSON schema may vary across OpenClaw versions, so some field mapping may need follow-up tuning against real-world payloads.

## Repository Layout

- `SKILL.md`: trigger conditions and workflow guidance for the skill
- `agents/openai.yaml`: UI metadata for the skill
- `scripts/render_openclaw_bindings.py`: OpenClaw bindings renderer

## License

[MIT](./LICENSE)
