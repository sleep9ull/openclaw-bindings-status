#!/usr/bin/env python3

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import zlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AgentRecord:
    agent_id: str
    workspace: str
    default: bool
    display_name: str


@dataclass
class BindingRecord:
    agent_id: str
    channel: str
    account_id: str
    peer_kind: str
    peer_id: str
    source: str
    raw: dict[str, Any]

    @property
    def route_key(self) -> str:
        parts = [self.channel or "unknown"]
        if self.account_id:
            parts.append(f"account={self.account_id}")
        if self.peer_kind or self.peer_id:
            scope = self.peer_kind or "peer"
            if self.peer_id:
                scope = f"{scope}:{self.peer_id}"
            parts.append(scope)
        return " / ".join(parts)

    @property
    def is_wildcard(self) -> bool:
        return self.account_id == "*"

    @property
    def has_peer_scope(self) -> bool:
        return bool(self.peer_kind or self.peer_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render OpenClaw agent/channel bindings as a Markdown dashboard."
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON from stdin instead of executing openclaw.",
    )
    parser.add_argument(
        "--from-json",
        help="Read JSON from a file instead of executing openclaw.",
    )
    parser.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Skip Mermaid diagram output.",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="Print normalized JSON instead of Markdown.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = load_payload(args)
        agents, bindings = normalize_payload(payload)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to render bindings: {exc}", file=sys.stderr)
        return 1

    if args.raw_json:
        print(
            json.dumps(
                {
                    "agents": [agent.__dict__ for agent in agents],
                    "bindings": [
                        {
                            **binding.raw,
                            "_normalized": {
                                "agent_id": binding.agent_id,
                                "channel": binding.channel,
                                "account_id": binding.account_id,
                                "peer_kind": binding.peer_kind,
                                "peer_id": binding.peer_id,
                                "source": binding.source,
                            },
                        }
                        for binding in bindings
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(render_markdown(agents, bindings, include_mermaid=not args.no_mermaid))
    return 0


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.stdin and args.from_json:
        raise ValueError("Use either --stdin or --from-json, not both.")

    if args.stdin:
        return json.load(sys.stdin)

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as handle:
            return json.load(handle)

    return collect_from_openclaw()


def collect_from_openclaw() -> dict[str, Any]:
    if not shutil.which("openclaw"):
        raise RuntimeError(
            "openclaw is not on PATH. Install it or pass --stdin / --from-json."
        )

    combined = run_json_command(["openclaw", "agents", "list", "--bindings", "--json"])
    if combined is not None:
        return {"agents_payload": combined, "bindings_payload": combined}

    agents_payload = run_json_command(["openclaw", "agents", "list", "--json"])
    bindings_payload = run_json_command(["openclaw", "agents", "bindings", "--json"])
    if agents_payload is None or bindings_payload is None:
        raise RuntimeError(
            "Failed to collect JSON from OpenClaw. "
            "Try `openclaw agents list --bindings --json` manually."
        )
    return {"agents_payload": agents_payload, "bindings_payload": bindings_payload}


def run_json_command(command: list[str]) -> Optional[Any]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def normalize_payload(payload: dict[str, Any]) -> tuple[list[AgentRecord], list[BindingRecord]]:
    if "agents_payload" in payload or "bindings_payload" in payload:
        agents_payload = payload.get("agents_payload")
        bindings_payload = payload.get("bindings_payload")
    else:
        agents_payload = payload
        bindings_payload = payload

    agents = parse_agents(agents_payload)
    bindings = parse_bindings(bindings_payload)

    if not agents and bindings:
        agents = build_agents_from_bindings(bindings)

    binding_map = defaultdict(list)
    for binding in bindings:
        binding_map[binding.agent_id].append(binding)

    if agents and not bindings:
        for agent in agents:
            embedded = extract_bindings_from_agent_payload(agents_payload, agent.agent_id)
            binding_map[agent.agent_id].extend(embedded)
        bindings = [item for items in binding_map.values() for item in items]

    if agents and bindings:
        known_ids = {agent.agent_id for agent in agents}
        for binding in bindings:
            if binding.agent_id and binding.agent_id not in known_ids:
                agents.append(
                    AgentRecord(
                        agent_id=binding.agent_id,
                        workspace="",
                        default=False,
                        display_name=binding.agent_id,
                    )
                )
                known_ids.add(binding.agent_id)

    agents.sort(key=lambda item: (not item.default, item.agent_id))
    bindings.sort(key=lambda item: (item.agent_id, item.channel, item.account_id, item.peer_kind, item.peer_id))
    return agents, bindings


def parse_agents(payload: Any) -> list[AgentRecord]:
    items = extract_agent_like_items(payload)
    records: list[AgentRecord] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        agent_id = str(
            item.get("id")
            or item.get("agentId")
            or item.get("agent")
            or item.get("name")
            or ""
        ).strip()
        if not agent_id or agent_id in seen:
            continue
        workspace = str(
            item.get("workspace")
            or item.get("workspacePath")
            or item.get("cwd")
            or ""
        ).strip()
        default = bool(item.get("default") or item.get("isDefault"))
        display_name = str(item.get("name") or agent_id).strip()
        records.append(
            AgentRecord(
                agent_id=agent_id,
                workspace=workspace,
                default=default,
                display_name=display_name,
            )
        )
        seen.add(agent_id)
    return records


def parse_bindings(payload: Any) -> list[BindingRecord]:
    raw_bindings = extract_binding_like_items(payload)
    records: list[BindingRecord] = []
    for item in raw_bindings:
        normalized = normalize_binding(item)
        if normalized is not None:
            records.append(normalized)
    return records


def extract_agent_like_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("agents", "list", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            if value and isinstance(value[0], dict) and (
                "workspace" in value[0]
                or "default" in value[0]
                or "isDefault" in value[0]
                or "bindings" in value[0]
            ):
                return value
            if key == "agents":
                return value
    if "agents" in payload and isinstance(payload["agents"], dict):
        return extract_agent_like_items(payload["agents"])
    return []


def extract_binding_like_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        if any(looks_like_binding(item) for item in payload):
            return payload
        nested: list[Any] = []
        for item in payload:
            if isinstance(item, dict):
                nested.extend(extract_binding_like_items(item))
        return nested

    if not isinstance(payload, dict):
        return []

    explicit = payload.get("bindings")
    if isinstance(explicit, list):
        return explicit

    nested: list[Any] = []
    for key in ("agents", "list", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    embedded = item.get("bindings")
                    if isinstance(embedded, list):
                        parent_agent_id = str(
                            item.get("id") or item.get("agentId") or item.get("agent") or ""
                        ).strip()
                        nested.extend(
                            inject_agent_id(candidate, parent_agent_id)
                            for candidate in embedded
                        )
    return nested


def extract_bindings_from_agent_payload(payload: Any, agent_id: str) -> list[BindingRecord]:
    for item in extract_agent_like_items(payload):
        if not isinstance(item, dict):
            continue
        item_agent_id = str(item.get("id") or item.get("agentId") or item.get("agent") or "").strip()
        if item_agent_id != agent_id:
            continue
        embedded = item.get("bindings")
        if isinstance(embedded, list):
            results: list[BindingRecord] = []
            for candidate in embedded:
                normalized = normalize_binding(inject_agent_id(candidate, agent_id))
                if normalized is not None:
                    results.append(normalized)
            return results
    return []


def looks_like_binding(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return any(
        key in item
        for key in ("match", "channel", "agentId", "accountId", "peer", "binding", "bind")
    )


def normalize_binding(item: Any) -> Optional[BindingRecord]:
    if isinstance(item, str):
        channel, account_id = split_channel_binding(item)
        if not channel:
            return None
        return BindingRecord(
            agent_id="",
            channel=channel,
            account_id=account_id,
            peer_kind="",
            peer_id="",
            source="string",
            raw={"bind": item},
        )

    if not isinstance(item, dict):
        return None

    match = item.get("match")
    if not isinstance(match, dict):
        match = {}

    peer = match.get("peer")
    if not isinstance(peer, dict):
        peer = item.get("peer") if isinstance(item.get("peer"), dict) else {}

    bind_value = item.get("bind") or item.get("binding")
    bind_channel = ""
    bind_account = ""
    if isinstance(bind_value, str):
        bind_channel, bind_account = split_channel_binding(bind_value)

    channel = str(
        item.get("channel")
        or match.get("channel")
        or bind_channel
        or ""
    ).strip()
    account_id = str(
        item.get("accountId")
        or match.get("accountId")
        or bind_account
        or ""
    ).strip()
    agent_id = str(
        item.get("agentId")
        or item.get("agent")
        or item.get("id")
        or ""
    ).strip()
    peer_kind = str(peer.get("kind") or "").strip()
    peer_id = str(peer.get("id") or peer.get("name") or "").strip()

    if not channel and not agent_id and not peer_kind and not peer_id:
        return None

    return BindingRecord(
        agent_id=agent_id,
        channel=channel or "unknown",
        account_id=account_id,
        peer_kind=peer_kind,
        peer_id=peer_id,
        source="dict",
        raw=item,
    )


def inject_agent_id(candidate: Any, agent_id: str) -> Any:
    if not agent_id:
        return candidate
    if isinstance(candidate, dict):
        return {**candidate, "agentId": candidate.get("agentId") or agent_id}
    if isinstance(candidate, str):
        return {"bind": candidate, "agentId": agent_id}
    return candidate


def split_channel_binding(value: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def build_agents_from_bindings(bindings: list[BindingRecord]) -> list[AgentRecord]:
    seen: set[str] = set()
    agents: list[AgentRecord] = []
    for binding in bindings:
        if not binding.agent_id or binding.agent_id in seen:
            continue
        agents.append(
            AgentRecord(
                agent_id=binding.agent_id,
                workspace="",
                default=False,
                display_name=binding.agent_id,
            )
        )
        seen.add(binding.agent_id)
    return agents


def render_markdown(
    agents: list[AgentRecord],
    bindings: list[BindingRecord],
    *,
    include_mermaid: bool,
) -> str:
    by_agent: dict[str, list[BindingRecord]] = defaultdict(list)
    for binding in bindings:
        by_agent[binding.agent_id].append(binding)

    unique_channels = sorted({binding.channel for binding in bindings if binding.channel})
    wildcard_count = sum(1 for binding in bindings if binding.is_wildcard)
    peer_scope_count = sum(1 for binding in bindings if binding.has_peer_scope)
    default_agents = [agent.agent_id for agent in agents if agent.default]
    unbound_agents = [agent.agent_id for agent in agents if not by_agent.get(agent.agent_id)]

    lines: list[str] = []
    lines.append("# OpenClaw Bindings Dashboard")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Agents: {len(agents)}")
    lines.append(f"- Default agents: {', '.join(default_agents) if default_agents else 'none'}")
    lines.append(f"- Bindings: {len(bindings)}")
    lines.append(f"- Channels in use: {', '.join(unique_channels) if unique_channels else 'none'}")
    lines.append(f"- Wildcard channel bindings: {wildcard_count}")
    lines.append(f"- Peer-scoped bindings: {peer_scope_count}")

    if unbound_agents:
        lines.append(f"- Unbound agents: {', '.join(unbound_agents)}")

    lines.append("")
    lines.append("## Agent Table")
    lines.append("")
    lines.append("| Agent | Workspace | Default | Bindings | Channels |")
    lines.append("| --- | --- | --- | ---: | --- |")
    for agent in agents:
        agent_bindings = by_agent.get(agent.agent_id, [])
        channels = sorted({binding.channel for binding in agent_bindings if binding.channel})
        lines.append(
            "| {agent} | {workspace} | {default} | {count} | {channels} |".format(
                agent=escape_table(agent.agent_id),
                workspace=escape_table(agent.workspace or "-"),
                default="yes" if agent.default else "",
                count=len(agent_bindings),
                channels=escape_table(", ".join(channels) if channels else "-"),
            )
        )

    lines.append("")
    lines.append("## Wiring View")
    lines.append("")
    if bindings:
        for binding in bindings:
            target = binding.agent_id or "unknown-agent"
            lines.append(f"- [{binding.route_key}] --> [{target}]")
    else:
        lines.append("- No bindings found.")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    if not bindings:
        lines.append("- No routing bindings were detected in the provided payload.")
    else:
        if wildcard_count:
            lines.append("- `account=*` indicates a channel-wide fallback route.")
        if peer_scope_count:
            lines.append("- `group`, `dm`, or other peer scopes describe routing scope, not permission policy.")
        if unbound_agents:
            lines.append("- Some agents exist without bindings; they may only be used via direct spawn or default routing.")
        if not wildcard_count and not peer_scope_count and not unbound_agents:
            lines.append("- Bindings look straightforward with no wildcard or peer-scoped special cases.")

    if include_mermaid and bindings:
        mermaid = render_mermaid(bindings)
        if mermaid:
            static_svg_url = build_mermaid_ink_svg_url(mermaid)
            lines.append("")
            lines.append("## Mermaid")
            lines.append("")
            lines.append("```mermaid")
            lines.extend(mermaid)
            lines.append("```")
            lines.append("")
            lines.append(f"Static Diagram: [Open SVG]({static_svg_url})")

    return "\n".join(lines).strip() + "\n"


def render_mermaid(bindings: list[BindingRecord]) -> list[str]:
    lines = ["flowchart LR"]
    channel_nodes: dict[str, str] = {}
    agent_nodes: dict[str, str] = {}

    for index, binding in enumerate(bindings, start=1):
        channel_key = binding.route_key
        channel_label = sanitize_mermaid_label(channel_key)
        if channel_key not in channel_nodes:
            channel_nodes[channel_key] = f"c{len(channel_nodes) + 1}"
            lines.append(f'  {channel_nodes[channel_key]}["{escape_mermaid(channel_label)}"]')

        agent_key = binding.agent_id or "unknown-agent"
        agent_label = sanitize_mermaid_label(agent_key)
        if agent_key not in agent_nodes:
            agent_nodes[agent_key] = f"a{len(agent_nodes) + 1}"
            lines.append(f'  {agent_nodes[agent_key]}["{escape_mermaid(agent_label)}"]')

        edge_label = f"binding {index}"
        lines.append(
            f'  {channel_nodes[channel_key]} -->|"{escape_mermaid(edge_label)}"| {agent_nodes[agent_key]}'
        )
    return lines


def build_mermaid_ink_svg_url(mermaid_lines: list[str]) -> str:
    payload = {
        "code": "\n".join(mermaid_lines),
        "mermaid": {"theme": "default"},
    }
    compressed = zlib.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"), 9)
    encoded = base64.b64encode(compressed).decode("ascii").replace("+", "-").replace("/", "_")
    return f"https://mermaid.ink/svg/pako:{encoded}?bgColor=!white"


def sanitize_mermaid_label(value: str, max_length: int = 96) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = cleaned.replace('"', "'")
    cleaned = re.sub(r"[\[\]\{\}\|<>`]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        cleaned = "unknown"
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 3].rstrip() + "..."
    return cleaned


def escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def escape_mermaid(value: str) -> str:
    return value.replace('"', '\\"')


if __name__ == "__main__":
    raise SystemExit(main())
