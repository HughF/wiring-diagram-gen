#!/usr/bin/env python3
# Copyright (C) 2026 Hugh Frater
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate an interactive SVG wiring harness diagram from a CSV file.

Usage:
    python wiring_diagram.py <input.csv> [options]

The CSV must have a header row. Column names are matched case-insensitively;
see wd/parser.py for the full list of recognised aliases.

Minimal required columns:
    Signal, Left Connector, Left Pin, Right Connector, Right Pin, Wire Colour

Optional column:
    Warning  — text shown in a warning box inside the termination section
"""
import argparse
import pathlib
import sys

from wd.parser import parse
from wd.layout import compute_layout
from wd.renderer import render_html


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate an interactive wiring harness diagram from a CSV file."
    )
    ap.add_argument("csv", help="Input CSV file")
    ap.add_argument("-o", "--output",
                    help="Output HTML path (default: same name as CSV with .html extension)")
    ap.add_argument("--title",
                    help="Diagram title shown in the header (default: CSV filename stem)")
    ap.add_argument("--width", type=int, default=1380,
                    help="SVG canvas width in pixels (default: 1380)")
    ap.add_argument("--lang", default="en", choices=["en", "zh"],
                    help="Default display language; viewer can toggle at runtime (default: en)")
    args = ap.parse_args()

    csv_path = pathlib.Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"Error: {csv_path} not found")

    out_path = pathlib.Path(args.output) if args.output else csv_path.with_suffix(".html")
    title    = args.title or csv_path.stem

    wires, connectors, notes = parse(str(csv_path))
    if not wires:
        sys.exit("Error: no wire rows found in CSV — check column headers")

    layout = compute_layout(wires, connectors, svg_width=args.width, notes=notes)
    html   = render_html(layout, title, default_lang=args.lang)

    out_path.write_text(html, encoding="utf-8")
    print(f"Written: {out_path}  ({layout.svg_width}×{layout.svg_height}px, {len(wires)} wires, "
          f"{len(layout.left_connectors)} left / {len(layout.right_connectors)} right connectors)")


if __name__ == "__main__":
    main()
