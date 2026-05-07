from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from .parser import Wire, ConnectorSpec

# ── Layout constants ──────────────────────────────────────────────────────────
SVG_HEADER_H  = 68   # height of the top title bar
CONN_HEADER_H = 26   # height of each connector's header rect
ROW_H         = 28   # height of each wire row
CONN_GAP      = 26   # vertical gap between consecutive connectors
TOP_Y         = 86   # y of the first connector (= SVG_HEADER_H + 18)
BOTTOM_INFO_H = 80   # reserved at the bottom for legend + info panel
BOT_PAD       = 22   # padding inside a connector below its last row
WARN_BOX_PAD  = 10   # space between last row and first warning box
WARN_BOX_H    = 52   # height per unique warning block

LEFT_X        = 20
LEFT_W        = 210
RIGHT_X       = 950
RIGHT_W       = 215
RIGHT_W_WIDE  = 285  # used when the section contains a warning box

WIRE_LEFT_X   = 230  # x where wires depart the left panel (right edge)
WIRE_RIGHT_X  = 950  # x where wires arrive at the right panel (left edge)


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class RowLayout:
    wire: Wire
    y: int          # vertical centre of the row rect


@dataclass
class ConnectorLayout:
    spec: ConnectorSpec
    x: int
    y: int          # top of connector rect
    w: int
    h: int          # total height of connector rect
    label: str
    rows: list[RowLayout]
    theme_idx: int  # index into RIGHT_THEMES in renderer
    warnings: list[str]  # unique warning texts, in appearance order


@dataclass
class WireLayout:
    wire: Wire
    y_left: int     # vertical centre at left panel edge
    y_right: int    # vertical centre at right panel edge


@dataclass
class DiagramLayout:
    svg_width: int
    svg_height: int
    left_connectors: list[ConnectorLayout]
    right_connectors: list[ConnectorLayout]
    wire_layouts: list[WireLayout]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _conn_height(n_rows: int, n_warnings: int) -> int:
    h = CONN_HEADER_H + n_rows * ROW_H + BOT_PAD
    if n_warnings:
        h += WARN_BOX_PAD + n_warnings * WARN_BOX_H
    return h


# ── Main entry point ──────────────────────────────────────────────────────────
def compute_layout(
    wires: list[Wire],
    connectors: list[ConnectorSpec],
    svg_width: int = 1380,
) -> DiagramLayout:

    left_specs  = [c for c in connectors if c.side == "left"]
    right_specs = [c for c in connectors if c.side == "right"]

    # Group wires by connector name
    left_wires:  dict[str, list[Wire]] = defaultdict(list)
    right_wires: dict[str, list[Wire]] = defaultdict(list)
    for w in wires:
        left_wires[w.left_conn].append(w)
        if w.right_conn:
            right_wires[w.right_conn].append(w)

    # Left: sort rows ascending by left_pin within each connector
    for ws in left_wires.values():
        ws.sort(key=lambda w: w.left_pin)

    # Right: order connectors top-to-bottom by the min left_pin that feeds them,
    # so that short wires stay near the top and crossings are minimised.
    def _right_key(c: ConnectorSpec) -> int:
        ws = right_wires.get(c.name, [])
        return min((w.left_pin for w in ws), default=9999)

    right_specs_ordered = sorted(right_specs, key=_right_key)

    # Within each right connector sort rows by ascending left_pin — this
    # aligns top-of-right with top-of-left and eliminates crossing for any
    # single connector pair.
    for c in right_specs_ordered:
        right_wires[c.name].sort(key=lambda w: w.left_pin)

    # ── Left connector layouts ────────────────────────────────────────────────
    left_layouts: list[ConnectorLayout] = []
    y = TOP_Y
    for spec in left_specs:
        ws = left_wires.get(spec.name, [])
        h = _conn_height(len(ws), 0)  # warnings are displayed on right-side panels only
        rows = [
            RowLayout(wire=w, y=y + CONN_HEADER_H + i * ROW_H + ROW_H // 2)
            for i, w in enumerate(ws)
        ]
        left_layouts.append(ConnectorLayout(
            spec=spec, x=LEFT_X, y=y, w=LEFT_W, h=h,
            label=spec.name, rows=rows, theme_idx=0, warnings=[],
        ))
        y += h + CONN_GAP

    left_bottom = (left_layouts[-1].y + left_layouts[-1].h) if left_layouts else TOP_Y

    # ── Right connector layouts ───────────────────────────────────────────────
    right_layouts: list[ConnectorLayout] = []
    y = TOP_Y
    for theme_idx, spec in enumerate(right_specs_ordered):
        ws = right_wires.get(spec.name, [])
        unique_warns = list(dict.fromkeys(w.warning for w in ws if w.warning))
        h = _conn_height(len(ws), len(unique_warns))
        w = RIGHT_W_WIDE if unique_warns else RIGHT_W
        rows = [
            RowLayout(wire=wr, y=y + CONN_HEADER_H + i * ROW_H + ROW_H // 2)
            for i, wr in enumerate(ws)
        ]
        right_layouts.append(ConnectorLayout(
            spec=spec, x=RIGHT_X, y=y, w=w, h=h,
            label=spec.name, rows=rows, theme_idx=theme_idx, warnings=unique_warns,
        ))
        y += h + CONN_GAP

    right_bottom = (right_layouts[-1].y + right_layouts[-1].h) if right_layouts else TOP_Y

    # ── Wire y-coordinate lookup ──────────────────────────────────────────────
    left_y:  dict[str, int] = {row.wire.wid: row.y for cl in left_layouts  for row in cl.rows}
    right_y: dict[str, int] = {row.wire.wid: row.y for cr in right_layouts for row in cr.rows}

    wire_layouts = [
        WireLayout(wire=w, y_left=left_y.get(w.wid, 0), y_right=right_y.get(w.wid, 0))
        for w in wires
    ]

    svg_height = max(left_bottom, right_bottom) + BOTTOM_INFO_H
    return DiagramLayout(
        svg_width=svg_width,
        svg_height=svg_height,
        left_connectors=left_layouts,
        right_connectors=right_layouts,
        wire_layouts=wire_layouts,
    )
