"""Validate and present source-backed relationships and execution walkthroughs."""

from __future__ import annotations

import html
import json
import re
from typing import Any


def guide_records(guide: dict[str, Any]) -> list[dict[str, Any]]:
    execution = guide.get("execution", {})
    return [
        *guide.get("nodes", []), *guide.get("relations", []),
        *execution.get("steps", []), *execution.get("transitions", []),
        *(frame for scenario in execution.get("scenarios", []) for frame in scenario["walkthrough"]),
    ]


def validate_guide(unit: dict[str, Any], report: dict[str, Any], side: str = "baseline") -> list[str]:
    baseline = unit.get(side, {})
    guide = baseline.get("guide")
    required = side == "baseline" and report["schema_version"] == "1.5" and unit["lane"] == "main" and unit["importance"] in {"critical", "normal"}
    if not guide:
        return [f"{unit['id']}.baseline.guide: architecture and execution guide required"] if required else []
    errors: list[str] = []
    prefix = f"{unit['id']}.{side}.guide"

    def fail(message: str) -> None:
        errors.append(f"{prefix}: {message}")

    def indexed(items, label):
        result = {}
        for item in items:
            if item["id"] in result:
                fail(f"duplicate {label} ID {item['id']!r}")
            result[item["id"]] = item
        return result

    known_refs = set(baseline.get("context_refs", []))
    for record in guide_records(guide):
        if not set(record["context_refs"]).issubset(known_refs):
            fail(f"every diagram and walkthrough reference must belong to {side}.context_refs")
    nodes = indexed(guide["nodes"], "node")
    calls = set()
    connected = set()
    for relation in guide["relations"]:
        left, right = relation["from"], relation["to"]
        if left not in nodes or right not in nodes:
            fail(f"relation has unknown endpoint {left!r} -> {right!r}")
        elif relation["kind"] in {"calls", "dispatches"} and any(nodes[key]["kind"] not in {"function", "external"} for key in (left, right)):
            fail("calls and dispatches must connect functions or external entries")
        connected.update((left, right))
        if relation["kind"] == "calls":
            calls.add((left, right))
    if len(nodes) > 1 and set(nodes) - connected:
        fail("architecture has isolated nodes; explain how each component relates to this behavior")
    execution = guide["execution"]
    if execution["status"] != "available":
        if any(execution.get(key) for key in ("entry", "steps", "transitions", "scenarios")):
            fail("unavailable execution must not include a fabricated flow or stack")
        if execution["status"] == "unknown":
            if unit["conclusion"]["status"] != "unproven" or report["outcome"]["recommendation"]["disposition"] != "expand_scope":
                fail("unknown execution requires an unproven unit and expand_scope recommendation")
        return errors
    for key in ("entry", "steps", "transitions", "scenarios"):
        if key not in execution:
            fail(f"available execution requires {key}")
    if any(key not in execution for key in ("entry", "steps", "transitions", "scenarios")):
        return errors
    steps = indexed(execution["steps"], "flow step")
    if execution["entry"] not in steps:
        fail("entry does not identify a flow step")
    for step in steps.values():
        if step["node"] not in nodes:
            fail(f"flow step {step['id']!r} references an unknown node")
        elif nodes[step["node"]]["kind"] not in {"function", "external"}:
            fail("execution steps must identify the executing function or external entry")
    transitions = {}
    outgoing: dict[str, set[str]] = {}
    for edge in execution["transitions"]:
        pair = (edge["from"], edge["to"])
        if pair in transitions:
            fail("duplicate flow transition; use distinct branch steps")
        transitions[pair] = edge
        if any(endpoint not in steps for endpoint in pair):
            fail(f"flow transition has unknown endpoint {pair!r}")
        outgoing.setdefault(pair[0], set()).add(pair[1])
    reached = set()
    pending = [execution["entry"]]
    while pending:
        step_id = pending.pop()
        if step_id not in reached:
            reached.add(step_id)
            pending.extend(outgoing.get(step_id, set()) - reached)
    if set(steps) - reached:
        fail("flow contains steps unreachable from entry")
    walked = set()
    for scenario in execution["scenarios"]:
        walk = scenario["walkthrough"]
        if walk[0]["step"] != execution["entry"]:
            fail("scenario must begin at flow entry")
        if outgoing.get(walk[-1]["step"]):
            fail("scenario must end at a terminal flow step")
        for frame in walk:
            walked.add(frame["step"])
            step = steps.get(frame["step"])
            stack = frame["stack"]
            if not step:
                fail("walkthrough references an unknown flow step")
            elif stack[-1] != step["node"]:
                fail("stack top must be the function executing the current step")
            if any(node not in nodes or nodes[node]["kind"] not in {"function", "external"} for node in stack):
                fail("stack contains an unknown or non-callable node")
            if any(pair not in calls for pair in zip(stack, stack[1:])):
                fail("adjacent stack frames require an evidenced synchronous calls relation")
        for previous, current in zip(walk, walk[1:]):
            edge = transitions.get((previous["step"], current["step"]))
            if not edge:
                fail("walkthrough jumps across a missing flow transition")
            elif edge["kind"] == "async" and len(current["stack"]) != 1:
                fail("async continuation must begin at its own entry with a new one-frame stack")
            elif edge["kind"] != "async" and previous["stack"][0] != current["stack"][0]:
                fail("a synchronous transition cannot silently replace the stack root")
    if set(steps) - walked:
        fail("every flow step must appear in at least one complete scenario")
    return errors


def mermaid(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Use generated IDs and entity-escaped labels; never execute author-supplied syntax."""
    identifiers = {node["id"]: f"n{index}" for index, node in enumerate(nodes)}

    def label(value):
        return "".join(char if char.isalnum() or char in " _-.:/" else f"#{ord(char)};" for char in str(value))

    lines = ["```mermaid", "flowchart TD"]
    lines.extend(f'  {identifiers[node["id"]]}["{label(node["label"])}"]' for node in nodes)
    for edge in edges:
        arrow = "-.->" if edge["kind"] in {"async", "dispatches"} else "-->"
        lines.append(f'  {identifiers[edge["from"]]} {arrow}|"{label(edge["label"])}"| {identifiers[edge["to"]]}')
    return [*lines, "```", ""]


def guide_markdown(guide: dict, format_refs, cell) -> list[str]:
    zh = re.search(r"[\u3400-\u9fff]", json.dumps(guide, ensure_ascii=False))
    def t(en, cn):
        return cn if zh else en

    nodes = {node["id"]: node for node in guide["nodes"]}
    views = guide.get("views", ["structure", "calls", "flow"])
    lines = []
    for view, title, relations in (
        ("structure", t("Architecture and dependencies", "架构与依赖"), [r for r in guide["relations"] if r["kind"] not in {"calls", "dispatches"}]),
        ("calls", t("Calls", "调用关系"), [r for r in guide["relations"] if r["kind"] in {"calls", "dispatches"}]),
    ):
        if view not in views:
            continue
        lines.extend([f"#### {title}", ""])
        used = {r[k] for r in relations for k in ("from", "to")}
        selected = [node for node in nodes.values() if node["id"] in used] or list(nodes.values())
        lines.extend(mermaid(selected, relations))
        lines.extend([t("| From | To | Relationship | Source |", "| 来源 | 目标 | 关系 | 源码 |"), "|---|---|---|---|"])
        for edge in relations:
            lines.append("| " + " | ".join(cell(x) for x in (nodes[edge["from"]]["label"], nodes[edge["to"]]["label"], edge["label"], format_refs(edge["context_refs"]))) + " |")
        lines.append("")
    lines.extend([t("| Component | Responsibility | Source |", "| 组成部分 | 职责 | 源码 |"), "|---|---|---|"])
    for node in nodes.values():
        lines.append("| " + " | ".join(cell(x) for x in (node["label"], node["responsibility"], format_refs(node["context_refs"]))) + " |")
    execution = guide["execution"]
    lines.extend(["", "#### " + t("Execution", "运行流程"), "", execution["reason"], ""])
    if execution["status"] != "available":
        return lines
    steps = {step["id"]: step for step in execution["steps"]}
    if "flow" in views:
        lines.extend(mermaid([{"id": s["id"], "label": s["action"]} for s in steps.values()], execution["transitions"]))
        lines.extend([t("| From | To | Condition | Source |", "| 来源 | 目标 | 条件 | 源码 |"), "|---|---|---|---|"])
        for edge in execution["transitions"]:
            lines.append("| " + " | ".join(cell(x) for x in (steps[edge["from"]]["action"], steps[edge["to"]]["action"], edge["label"], format_refs(edge["context_refs"]))) + " |")
    lines.extend(["", t("Source-derived stack illustration; not a runtime capture.", "调用栈依据源码推导，未实际运行。"), ""])
    for scenario in execution["scenarios"]:
        lines.extend([f"##### {scenario['title']}", "", scenario["summary"], ""])
        for index, frame in enumerate(scenario["walkthrough"], 1):
            step = steps[frame["step"]]
            lines.extend([
                f"{index}. **{step['action']}** — {frame['explanation']}", "",
                "   " + t("Stack (outermost → current): ", "调用栈（外层 → 当前）：") + " → ".join(html.escape(nodes[key]["label"]) for key in frame["stack"]), "",
                "   " + format_refs(list(dict.fromkeys([*step["context_refs"], *frame["context_refs"]]))), "",
            ])
    return lines
