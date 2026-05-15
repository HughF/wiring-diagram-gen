from __future__ import annotations
import csv
from dataclasses import dataclass

# Flexible column name aliases (all lowercase, spaces normalised).
# The first entry in each tuple is the canonical form — identical to the
# field key after replacing underscores with spaces.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "signal":      ("signal", "signal name", "name", "wire", "wire name"),
    "left_conn":   ("left conn", "left connector", "from connector", "from",
                    "source connector", "source"),
    "left_pin":    ("left pin", "from pin", "source pin", "pin (left)", "left pin no"),
    "right_conn":  ("right conn", "right connector", "to connector", "to",
                    "dest connector", "destination connector", "destination",
                    "termination", "termination type"),
    "right_pin":   ("right pin", "to pin", "dest pin", "destination pin",
                    "pin (right)", "right pin no"),
    "colour":      ("colour", "wire colour", "wire color", "color", "wire col"),
    "warning":     ("warning", "note", "notes", "annotation", "remark"),
    "pair":        ("pair", "twisted pair", "tp", "pair group"),
    "cable":       ("cable", "cable group", "cable name", "sheath", "multicore", "cable ref"),
    "length":      ("length", "wire length", "len"),
    "sleeving":    ("sleeving", "sleeve", "sleeved"),
}


def _norm(h: str) -> str:
    # Replace separators before stripping so a leading/trailing _ or - is also removed.
    return h.replace("_", " ").replace("-", " ").strip().lower()


def _map_headers(headers: list[str]) -> dict[str, int]:
    norm = {_norm(h): i for i, h in enumerate(headers)}
    result: dict[str, int] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                result[field] = norm[alias]
                break
    return result


@dataclass
class Wire:
    wid: str
    signal: str
    left_conn: str
    left_pin: str
    right_conn: str
    right_pin: str | None   # None = free-end / termination group
    colour: str             # raw name as written in CSV
    warning: str | None
    pair: str               # pair group name; empty string = unpaired
    cable: str              # cable/sheath group name; empty string = individual wire
    length: str             # raw length string as written in CSV; empty = unspecified
    sleeving: str           # sleeve colour/label for wire end; empty = none


@dataclass
class ConnectorSpec:
    name: str
    side: str           # 'left' | 'right'
    is_free_end: bool   # True when right_pin is always None for this connector
    order: int          # first-appearance order in the CSV


def parse(path: str) -> tuple[list[Wire], list[ConnectorSpec], list[str], list[tuple[str, str]]]:
    wires: list[Wire] = []
    conn_seen: dict[tuple[str, str], ConnectorSpec] = {}  # keyed by (name, side)
    conn_order = 0
    notes: list[str] = []
    images: list[tuple[str, str]] = []   # (path, caption) pairs
    next_is_notes = False
    next_is_images = False

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers: list[str] | None = None
        col_map: dict[str, int] = {}

        for row in reader:
            if not any(c.strip() for c in row):
                continue
            if row[0].strip().startswith("#"):
                continue

            if headers is None:
                headers = row
                col_map = _map_headers(headers)
                continue

            if next_is_notes:
                text = " ".join(c.strip() for c in row if c.strip())
                if text:
                    notes.append(text)
                next_is_notes = False
                continue

            if next_is_images:
                cell = row[0].strip()
                if cell.lower() == "notes":
                    next_is_images = False
                    next_is_notes = True
                    continue
                if "|" in cell:
                    path_s, _, cap = cell.partition("|")
                    path_s, cap = path_s.strip(), cap.strip()
                else:
                    path_s = cell
                    cap = row[1].strip() if len(row) > 1 else ""
                if path_s:
                    images.append((path_s, cap))
                continue

            if row[0].strip().lower() == "notes":
                next_is_notes = True
                continue

            if row[0].strip().lower() == "images":
                next_is_images = True
                continue

            def get(field: str) -> str:
                idx = col_map.get(field)
                return row[idx].strip() if idx is not None and idx < len(row) else ""

            signal = get("signal")
            if not signal:
                continue

            left_conn = get("left_conn")
            left_pin_s = get("left_pin")
            right_conn = get("right_conn")
            right_pin_s = get("right_pin")
            colour = get("colour") or "grey"
            warning = get("warning") or None
            pair = get("pair")
            cable = get("cable")
            length = get("length")
            sleeving = get("sleeving")

            if not left_conn or not left_pin_s:
                continue
            left_pin = left_pin_s

            right_pin: str | None = None
            if right_pin_s and right_pin_s.upper() not in ("N/C", "NC", ""):
                right_pin = right_pin_s

            wid = f"w{len(wires) + 1}"
            wires.append(Wire(
                wid=wid,
                signal=signal,
                left_conn=left_conn,
                left_pin=left_pin,
                right_conn=right_conn,
                right_pin=right_pin,
                colour=colour,
                warning=warning,
                pair=pair,
                cable=cable,
                length=length,
                sleeving=sleeving,
            ))

            for name, side, free in [
                (left_conn, "left", False),
                (right_conn, "right", right_pin is None),
            ]:
                if name and (name, side) not in conn_seen:
                    conn_seen[(name, side)] = ConnectorSpec(
                        name=name, side=side, is_free_end=free, order=conn_order,
                    )
                    conn_order += 1

    connectors = sorted(conn_seen.values(), key=lambda c: c.order)
    return wires, connectors, notes, images
