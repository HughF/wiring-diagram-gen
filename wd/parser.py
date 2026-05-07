from __future__ import annotations
import csv
from dataclasses import dataclass

# Flexible column name aliases (all lowercase, spaces normalised)
COLUMN_ALIASES: dict[str, list[str]] = {
    "signal":      ["signal", "signal name", "name", "wire", "wire name"],
    "left_conn":   ["left connector", "left conn", "from connector", "from",
                    "source connector", "source"],
    "left_pin":    ["left pin", "from pin", "source pin", "pin (left)", "left pin no"],
    "right_conn":  ["right connector", "right conn", "to connector", "to",
                    "dest connector", "destination connector", "destination",
                    "termination", "termination type"],
    "right_pin":   ["right pin", "to pin", "dest pin", "destination pin",
                    "pin (right)", "right pin no"],
    "colour":      ["wire colour", "wire color", "colour", "color", "wire col"],
    "warning":     ["warning", "note", "notes", "annotation", "remark"],
}


def _norm(h: str) -> str:
    return h.strip().lower().replace("_", " ").replace("-", " ")


def _map_headers(headers: list[str]) -> dict[str, int]:
    norm = {_norm(h): i for i, h in enumerate(headers)}
    result: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
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
    left_pin: int
    right_conn: str
    right_pin: int | None   # None = free-end / termination group
    colour: str             # raw name as written in CSV
    warning: str | None


@dataclass
class ConnectorSpec:
    name: str
    side: str           # 'left' | 'right'
    is_free_end: bool   # True when right_pin is always None for this connector
    order: int          # first-appearance order in the CSV


def parse(path: str) -> tuple[list[Wire], list[ConnectorSpec]]:
    wires: list[Wire] = []
    conn_seen: dict[str, ConnectorSpec] = {}
    conn_order = 0

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

            if not left_conn or not left_pin_s:
                continue
            try:
                left_pin = int(left_pin_s)
            except ValueError:
                continue

            right_pin: int | None = None
            if right_pin_s and right_pin_s.upper() not in ("N/C", "NC", ""):
                try:
                    right_pin = int(right_pin_s)
                except ValueError:
                    pass

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
            ))

            for name, side, free in [
                (left_conn, "left", False),
                (right_conn, "right", right_pin is None),
            ]:
                if name and name not in conn_seen:
                    conn_seen[name] = ConnectorSpec(
                        name=name, side=side, is_free_end=free, order=conn_order,
                    )
                    conn_order += 1

    connectors = sorted(conn_seen.values(), key=lambda c: c.order)
    return wires, connectors
