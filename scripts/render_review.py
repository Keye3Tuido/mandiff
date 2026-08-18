#!/usr/bin/env python3
"""Embed a ManDiff review model into the portable HTML explorer."""

import argparse
import json
from pathlib import Path

from validate_review import validate_report


PLACEHOLDER = '{"__replace_with_mandiff_report__":true}'


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
    errors = validate_report(report)
    if errors:
        raise SystemExit("Invalid ManDiff report:\n- " + "\n- ".join(errors))

    template = args.template.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit("template must contain exactly one ManDiff data placeholder")

    embedded = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace(PLACEHOLDER, embedded), encoding="utf-8")


if __name__ == "__main__":
    main()
