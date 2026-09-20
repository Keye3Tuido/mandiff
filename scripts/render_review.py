#!/usr/bin/env python3
"""Embed a ManDiff review model into the portable HTML explorer."""

import argparse
import json
from pathlib import Path

from validate_review import validate_report


PLACEHOLDER = '{"__replace_with_mandiff_report__":true}'
GUIDE_SCRIPT = Path(__file__).resolve().parent.parent / "assets" / "context-guide.js"


def render_html(report: dict, template: str) -> str:
    errors = validate_report(report)
    if errors:
        raise ValueError("Invalid ManDiff report:\n- " + "\n- ".join(errors))
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("template must contain exactly one ManDiff data placeholder")
    embedded = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = template.replace("/*__MANDIFF_CONTEXT_GUIDE__*/", GUIDE_SCRIPT.read_text(encoding="utf-8"))
    return template.replace(PLACEHOLDER, embedded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "assets" / "review-explorer-template.html",
    )
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    template = args.template.read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        args.output.write_text(render_html(report, template), encoding="utf-8")
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
