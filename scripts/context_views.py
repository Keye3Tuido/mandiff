"""Small source-backed views selected for the reader's question."""

import json
import re


def is_chinese(view):
    return bool(re.search(r"[\u3400-\u9fff]", json.dumps(view, ensure_ascii=False)))


def view_columns(view):
    zh = is_chinese(view)
    if view.get("columns"):
        return view["columns"]
    if view["kind"] == "state":
        return ["原状态", "事件或条件", "新状态"] if zh else ["Before state", "Event or condition", "After state"]
    return ["来源", "关系或职责", "目标"] if zh else ["Source", "Relationship or responsibility", "Target"]


def views_markdown(views, format_refs, cell):
    lines = []
    for view in views:
        lines.extend([f"#### {view['title']}", "", view["reason"], ""])
        if view["kind"] == "sequence":
            for index, row in enumerate(view["rows"], 1):
                lines.extend([f"{index}. {cell(row['from'])} → {cell(row['to'])}: {row['label']}", "",
                              "   " + format_refs(row["context_refs"]), ""])
        else:
            columns = view_columns(view)
            source_label = "源码" if is_chinese(view) else "Evidence"
            lines.extend(["| " + " | ".join(cell(c) for c in [*columns, source_label]) + " |", "|---|---|---|---|"])
            for row in view["rows"]:
                lines.append("| " + " | ".join(cell(c) for c in [row["from"], row["label"], row["to"], format_refs(row["context_refs"])]) + " |")
            lines.append("")
    return lines
