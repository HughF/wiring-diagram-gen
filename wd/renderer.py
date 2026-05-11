from __future__ import annotations
import json
from .layout import (
    DiagramLayout, ConnectorLayout, WireLayout,
    CONN_HEADER_H, ROW_H, BOT_PAD, WARN_BOX_PAD, WARN_BOX_H,
    WIRE_LEFT_X, WIRE_RIGHT_X,
)
from .colours import resolve, is_light, colour_name

# Bezier control-point x positions, tuned to match the reference diagram style.
_SPAN    = WIRE_RIGHT_X - WIRE_LEFT_X
_CP1_X   = round(WIRE_LEFT_X  + _SPAN * 0.38)   # departs horizontally from left
_CP2_X   = round(WIRE_RIGHT_X - _SPAN * 0.15)   # arrives horizontally at right
_TWIST_X = round(WIRE_LEFT_X/8 + 3*_CP1_X/8 + 3*_CP2_X/8 + WIRE_RIGHT_X/8)  # Bézier t=0.5 x
_SYM_W   = 38   # helix symbol width in px (3×10-step + 2×4-pad)

# ── Colour themes ─────────────────────────────────────────────────────────────
_LEFT_THEME = {
    "bg": "#ECEFF1", "border": "#37474F", "header": "#37474F",
    "row_a": "#E8EAF6", "row_b": "#C5CAE9",
}
_RIGHT_THEMES = [
    {"bg": "#E3F2FD", "border": "#1976D2", "header": "#1565C0",
     "row_a": "#BBDEFB", "row_b": "#DDEEFF"},
    {"bg": "#FFF8E1", "border": "#FB8C00", "header": "#E65100",
     "row_a": "#FFE0B2", "row_b": "#FFF3CD"},
    {"bg": "#E8EAF6", "border": "#1A237E", "header": "#283593",
     "row_a": "#C5CAE9", "row_b": "#E8EAF6"},
    {"bg": "#E8F5E9", "border": "#388E3C", "header": "#2E7D32",
     "row_a": "#C8E6C9", "row_b": "#DCEDC8"},
    {"bg": "#FCE4EC", "border": "#C62828", "header": "#B71C1C",
     "row_a": "#FFCDD2", "row_b": "#FFEAEA"},
    {"bg": "#F3E5F5", "border": "#6A1B9A", "header": "#4A148C",
     "row_a": "#E1BEE7", "row_b": "#F5E6FA"},
    {"bg": "#E0F2F1", "border": "#00695C", "header": "#004D40",
     "row_a": "#B2DFDB", "row_b": "#D8F0EE"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _x(s: str) -> str:
    """XML-escape a string for SVG text or attribute values."""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _bez(yl: int, yr: int) -> str:
    return f"M{WIRE_LEFT_X},{yl} C{_CP1_X},{yl} {_CP2_X},{yr} {WIRE_RIGHT_X},{yr}"


def _twist_sym_svg(ys: list[int], pair_name: str, x_offset: int = 0) -> list[str]:
    """Helix symbol for one twisted-pair group at the given wire y-positions."""
    if len(ys) < 2:
        return []
    top, bot = min(ys), max(ys)
    if bot - top < 4:
        return []

    MAX_H = 2 * ROW_H   # 56 px cap — beyond this, add connector lines
    s     = 10           # horizontal step; 3 segments → 30 px wide
    cx    = _TWIST_X + x_offset
    x0    = cx - (3 * s) // 2
    pad   = 4

    out: list[str] = []

    if bot - top <= MAX_H:
        h_top, h_bot = top, bot
    else:
        mid   = (top + bot) // 2
        h_top = mid - MAX_H // 2
        h_bot = mid + MAX_H // 2
        # Dashed lines from helix tips to the outermost wire positions
        out += [
            f'<line x1="{cx}" y1="{top}" x2="{cx}" y2="{h_top}"'
            f' stroke="#455A64" stroke-width="1.2" stroke-dasharray="3,2" pointer-events="none"/>',
            f'<line x1="{cx}" y1="{h_bot}" x2="{cx}" y2="{bot}"'
            f' stroke="#455A64" stroke-width="1.2" stroke-dasharray="3,2" pointer-events="none"/>',
        ]

    # White backing so the helix reads cleanly over any wire colour
    out.append(
        f'<rect x="{x0-pad}" y="{h_top-pad}" width="{3*s+2*pad}" height="{h_bot-h_top+2*pad}"'
        f' rx="3" fill="white" fill-opacity="0.82" pointer-events="none"/>'
    )

    d = (
        f"M{x0},{h_top} "
        f"C{x0+s},{h_top} {x0},{h_bot} {x0+s},{h_bot} "
        f"C{x0+2*s},{h_bot} {x0+s},{h_top} {x0+2*s},{h_top} "
        f"C{x0+3*s},{h_top} {x0+2*s},{h_bot} {x0+3*s},{h_bot}"
    )
    out.append(
        f'<path d="{d}" stroke="#455A64" stroke-width="1.5" fill="none" pointer-events="none"/>'
    )

    # Pair-name label — white stroke halo keeps it legible over any background
    out.append(
        f'<text x="{cx}" y="{h_top-5}" text-anchor="middle" font-size="9" font-weight="bold"'
        f' fill="#37474F" stroke="white" stroke-width="3" paint-order="stroke"'
        f' pointer-events="none">{_x(pair_name)}</text>'
    )
    return out


def _wrap(text: str, max_chars: int = 46) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        lines.append(cur)
    return lines


# ── Termination symbols ───────────────────────────────────────────────────────
def _term_sym(wid: str, term: str, cy: int, col: str, signal: str = "") -> list[str]:
    t = term.lower()
    out: list[str] = []

    if "bootlace" in t or "ferrule" in t:
        out += [
            f'<rect id="termSym_{wid}" x="954" y="{cy-7}" width="22" height="14" rx="4"'
            f' fill="{col}" stroke="white" stroke-width="1" pointer-events="none"/>',
            f'<line id="termTail_{wid}" x1="976" y1="{cy}" x2="984" y2="{cy}"'
            f' stroke="{col}" stroke-width="4" stroke-linecap="round" pointer-events="none"/>',
        ]
    elif "3/16" in t or "small spade" in t:
        out += [
            f'<line id="termTail_{wid}" x1="954" y1="{cy}" x2="962" y2="{cy}"'
            f' stroke="{col}" stroke-width="3" stroke-linecap="round" pointer-events="none"/>',
            f'<polygon id="termSym_{wid}" points="986,{cy-6} 972,{cy-6} 962,{cy} 972,{cy+6} 986,{cy+6}"'
            f' fill="{col}" stroke="white" stroke-width="1" pointer-events="none"/>',
        ]
    elif "1/4" in t or "large spade" in t:
        sig = signal.strip().upper()
        sleeve = "#795548" if sig == "L" else "#1565C0" if sig == "N" else "#388E3C"
        out += [
            f'<line id="termTail_{wid}" x1="954" y1="{cy}" x2="960" y2="{cy}"'
            f' stroke="{col}" stroke-width="3" stroke-linecap="round" pointer-events="none"/>',
            f'<polygon id="termSym_{wid}" points="982,{cy-6} 968,{cy-6} 960,{cy} 968,{cy+6} 982,{cy+6}"'
            f' fill="{col}" stroke="white" stroke-width="1" pointer-events="none"/>',
            f'<rect id="termSleeve_{wid}" x="982" y="{cy-8}" width="12" height="16" rx="3"'
            f' fill="{sleeve}" stroke="white" stroke-width="0.8" pointer-events="none"/>',
        ]
    elif "bare" in t or "strip" in t:
        out.append(
            f'<line id="termSym_{wid}" x1="954" y1="{cy}" x2="972" y2="{cy}"'
            f' stroke="{col}" stroke-width="4" stroke-linecap="butt" pointer-events="none"/>'
        )
    else:
        out.append(
            f'<circle id="termSym_{wid}" cx="963" cy="{cy}" r="5"'
            f' fill="{col}" stroke="white" stroke-width="1" pointer-events="none"/>'
        )
    return out


# ── Connector SVG ─────────────────────────────────────────────────────────────
def _connector_svg(cl: ConnectorLayout, is_left: bool) -> list[str]:
    out: list[str] = []
    theme = _LEFT_THEME if is_left else _RIGHT_THEMES[cl.theme_idx % len(_RIGHT_THEMES)]
    cx, cy, cw, ch = cl.x, cl.y, cl.w, cl.h

    out.append(
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="7"'
        f' fill="{theme["bg"]}" stroke="{theme["border"]}" stroke-width="2"/>'
    )
    out.append(
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{CONN_HEADER_H}" rx="7"'
        f' fill="{theme["header"]}"/>'
    )
    out.append(
        f'<text x="{cx + cw // 2}" y="{cy + 17}" text-anchor="middle"'
        f' font-size="12" font-weight="bold" fill="white">{_x(cl.label)}</text>'
    )

    for i, row in enumerate(cl.rows):
        ry   = row.y - ROW_H // 2
        fill = theme["row_a"] if i % 2 == 0 else theme["row_b"]

        if is_left:
            out.append(
                f'<rect id="rowL_{row.wire.wid}" data-wid="{row.wire.wid}"'
                f' x="{cx+2}" y="{ry}" width="{cw-4}" height="{ROW_H}" rx="2"'
                f' fill="{fill}" opacity="0.6" style="cursor:pointer"/>'
            )
            out.append(
                f'<text x="{cx+8}" y="{row.y+4}" font-size="10" font-weight="bold"'
                f' fill="#1A237E">{row.wire.left_pin}</text>'
            )
            out.append(
                f'<text x="{cx+28}" y="{row.y+4}" font-size="9.5"'
                f' fill="#263238">{_x(row.wire.signal)}</text>'
            )
        else:
            out.append(
                f'<rect id="rowR_{row.wire.wid}" data-wid="{row.wire.wid}"'
                f' x="{cx+2}" y="{ry}" width="{cw-4}" height="{ROW_H}" rx="2"'
                f' fill="{fill}" opacity="0.6" style="cursor:pointer"/>'
            )
            if not cl.spec.is_free_end and row.wire.right_pin is not None:
                out.append(
                    f'<text x="{cx+10}" y="{row.y+4}" font-size="10" font-weight="bold"'
                    f' fill="{theme["header"]}">{row.wire.right_pin}</text>'
                )
                out.append(
                    f'<text x="{cx+cw-6}" y="{row.y+4}" text-anchor="end"'
                    f' font-size="9" fill="#37474F">{_x(row.wire.signal)}</text>'
                )
            else:
                out.append(
                    f'<text x="{cx+10}" y="{row.y+4}" font-size="9"'
                    f' fill="{theme["header"]}">{row.wire.left_pin}</text>'
                )
                out.append(
                    f'<text x="{cx+32}" y="{row.y+4}" font-size="9.5"'
                    f' fill="#263238">{_x(row.wire.signal)}</text>'
                )

    if cl.warnings:
        box_y = cy + CONN_HEADER_H + len(cl.rows) * ROW_H + BOT_PAD - 4 + WARN_BOX_PAD
        for warn_text in cl.warnings:
            out.append(
                f'<rect x="{cx+8}" y="{box_y}" width="{cw-16}" height="{WARN_BOX_H-4}" rx="5"'
                f' fill="#FFF9C4" stroke="#F57F17" stroke-width="1.5" stroke-dasharray="4,3"/>'
            )
            for li, line in enumerate(_wrap(warn_text)[:3]):
                ly  = box_y + 15 + li * 13
                pfx = "⚠ " if li == 0 else "   "
                fw  = "bold"    if li == 0 else "normal"
                fc  = "#BF360C" if li == 0 else "#5D4037"
                out.append(
                    f'<text x="{cx+16}" y="{ly}" font-size="9.5"'
                    f' font-weight="{fw}" fill="{fc}">{pfx}{_x(line)}</text>'
                )
            box_y += WARN_BOX_H

    return out


# ── Embedded JS ───────────────────────────────────────────────────────────────
def _build_js(layout: DiagramLayout, title: str) -> str:
    wire_meta = []
    for wl in layout.wire_layouts:
        w = wl.wire
        right_desc = (
            f"{w.right_conn} Pin {w.right_pin}"
            if w.right_pin is not None else w.right_conn
        )
        wire_meta.append({
            "wid":       w.wid,
            "signal":    w.signal,
            "leftConn":  w.left_conn,
            "leftPin":   w.left_pin,
            "rightDesc": right_desc,
            "colName":   colour_name(w.colour),
            "isLight":   is_light(resolve(w.colour)),
            "hasTerm":   w.right_pin is None,
            "length":    w.length,
        })

    safe_title = _x(title)
    return f"""
const wireData={json.dumps(wire_meta, separators=(',', ':'))};
const ALL=wireData.map(w=>w.wid);
let sel=null;
const svg=document.getElementById('mainSvg');
const TERM_PFX=['termSym_','termTail_','termSleeve_'];
const WIRE_PFX=['wire_','wireBG_','dot33_','dotR_'];

function getElems(wid){{
  return [...WIRE_PFX,...TERM_PFX].map(p=>document.getElementById(p+wid)).filter(Boolean);
}}
function clearAll(){{
  ALL.forEach(wid=>{{
    getElems(wid).forEach(e=>{{e.style.opacity='';e.style.filter='';}});
    const wp=document.getElementById('wire_'+wid);
    if(wp)wp.setAttribute('stroke-width','2');
    const wb=document.getElementById('wireBG_'+wid);
    if(wb){{wb.setAttribute('stroke','#90A4AE');wb.setAttribute('stroke-width','3.4');}}
    ['rowL_','rowR_'].forEach(p=>{{
      const r=document.getElementById(p+wid);
      if(r){{r.style.opacity='';r.style.filter='';r.setAttribute('fill',r.dataset.origFill);}}
    }});
  }});
  sel=null;
  document.getElementById('infoPanel').setAttribute('opacity','0');
}}
function highlight(wid){{
  if(sel===wid){{clearAll();return;}}
  clearAll();sel=wid;
  ALL.forEach(x=>{{
    if(x===wid)return;
    getElems(x).forEach(e=>e.style.opacity='0.07');
    ['rowL_','rowR_'].forEach(p=>{{
      const r=document.getElementById(p+x);
      if(r){{r.style.opacity='0.12';r.style.filter='grayscale(80%)';}}
    }});
  }});
  const wd=wireData.find(w=>w.wid===wid);
  const wp=document.getElementById('wire_'+wid);
  if(wp){{
    wp.style.opacity='1';
    wp.setAttribute('stroke-width','4');
    const shadowCol=wd.isLight?'#37474F':wp.getAttribute('stroke');
    wp.style.filter='drop-shadow(0 0 6px '+shadowCol+')';
  }}
  const wb=document.getElementById('wireBG_'+wid);
  if(wb){{wb.style.opacity='1';wb.setAttribute('stroke','#37474F');wb.setAttribute('stroke-width',wd.isLight?'5':'3.4');}}
  [...WIRE_PFX.slice(2),...TERM_PFX].forEach(p=>{{
    const e=document.getElementById(p+wid);if(e)e.style.opacity='1';
  }});
  ['rowL_','rowR_'].forEach(p=>{{
    const r=document.getElementById(p+wid);
    if(r){{r.setAttribute('fill','#FFEB3B');r.style.opacity='1';r.style.filter='none';}}
  }});
  const panel=document.getElementById('infoPanel');
  panel.setAttribute('opacity','1');
  document.getElementById('infoTitle').textContent=
    wd.signal+' ('+wd.leftConn+' Pin '+wd.leftPin+' → '+wd.rightDesc+')';
  document.getElementById('infoSub').textContent=
    'Wire: '+wd.colName+(wd.hasTerm?' | Termination: '+wd.rightDesc:'')+(wd.length?' | Length: '+wd.length:'');
}}
document.querySelectorAll('[id^="rowL_"],[id^="rowR_"]').forEach(r=>
  r.dataset.origFill=r.getAttribute('fill'));
svg.addEventListener('click',e=>{{
  const t=e.target.closest('[data-wid]');
  if(t)highlight(t.getAttribute('data-wid'));else clearAll();
}});
document.addEventListener('keydown',e=>{{if(e.key==='Escape')clearAll();}});
document.getElementById('dlSvg').addEventListener('click',function(e){{
  e.preventDefault();
  const blob=new Blob([svg.outerHTML],{{type:'image/svg+xml'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='{safe_title}.svg';a.click();
}});
document.getElementById('dlHtml').addEventListener('click',function(e){{
  e.preventDefault();
  const blob=new Blob([document.documentElement.outerHTML],{{type:'text/html'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='{safe_title}.html';a.click();
}});
"""


def _notes_html(notes: list[str]) -> str:
    if not notes:
        return ""
    paras = "".join(f"<p>{_x(n)}</p>" for n in notes)
    return f'<div id="notes"><h2>Notes</h2>{paras}</div>'


def _parse_length(raw: str) -> tuple[float, str] | None:
    """Return (value, unit) from a raw length string, or None if unparseable."""
    s = raw.strip()
    unit = ""
    for u in ("mm", "cm", "ft", "m"):   # longest-match order prevents 'mm'→'m' mis-parse
        if s.lower().endswith(u):
            s = s[:-len(u)].strip()
            unit = u
            break
    try:
        return float(s), unit
    except ValueError:
        return None


def _cut_list_html(layout: DiagramLayout) -> str:
    wires = [wl.wire for wl in layout.wire_layouts]
    if not any(w.length for w in wires):
        return ""

    # Sort by left connector diagram order, then pin
    conn_order = {cl.spec.name: i for i, cl in enumerate(layout.left_connectors)}
    sorted_wires = sorted(wires, key=lambda w: (conn_order.get(w.left_conn, 999), w.left_pin))

    rows: list[str] = []
    for w in sorted_wires:
        col      = resolve(w.colour)
        col_nm   = colour_name(w.colour)
        right_pin = str(w.right_pin) if w.right_pin is not None else "—"
        length   = _x(w.length) if w.length else "—"
        swatch   = f'<span class="swatch" style="background:{col}"></span>'
        rows.append(
            f"<tr>"
            f"<td>{_x(w.signal)}</td>"
            f"<td>{_x(w.left_conn)}</td><td>{w.left_pin}</td>"
            f"<td>{_x(w.right_conn)}</td><td>{right_pin}</td>"
            f"<td>{swatch}{_x(col_nm)}</td>"
            f"<td>{length}</td>"
            f"</tr>"
        )

    # Totals per (colour, unit) — only wires with parseable lengths
    totals: dict[tuple[str, str], float] = {}
    has_unparsed = False
    for w in sorted_wires:
        if not w.length:
            continue
        parsed = _parse_length(w.length)
        if parsed is None:
            has_unparsed = True
            continue
        val, unit = parsed
        key = (colour_name(w.colour), unit)
        totals[key] = totals.get(key, 0.0) + val

    tfoot = ""
    if totals:
        note = " *" if has_unparsed else ""
        total_rows = "".join(
            f'<tr><td colspan="6" class="tot-label">{_x(col_nm)} ({unit or "no unit"}){note}</td>'
            f'<td class="tot-val">{val:.4g}{unit}</td></tr>'
            for (col_nm, unit), val in sorted(totals.items())
        )
        disclaimer = (
            '<tr><td colspan="7" class="tot-note">* Some wires have non-numeric lengths and are excluded from totals.</td></tr>'
            if has_unparsed else ""
        )
        tfoot = f"<tfoot>{total_rows}{disclaimer}</tfoot>"

    return (
        '<div id="cutList"><h2>Cut list</h2>'
        '<table><thead><tr>'
        "<th>Signal</th><th>From</th><th>Pin</th><th>To</th><th>Pin</th><th>Colour</th><th>Length</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody>{tfoot}</table></div>"
    )


# ── Main render entry point ───────────────────────────────────────────────────
def render_html(layout: DiagramLayout, title: str) -> str:
    W, H    = layout.svg_width, layout.svg_height
    mid_x   = (WIRE_LEFT_X + WIRE_RIGHT_X) // 2
    panel_y = H - 72

    svg: list[str] = []

    svg.append(f'<svg id="mainSvg" xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    svg.append(f'<rect id="bg" width="{W}" height="{H}" fill="#F0F2F5"/>')
    svg.append(f'<rect x="0" y="0" width="{W}" height="68" fill="#1A237E"/>')
    svg.append(
        f'<text x="{W//2}" y="34" text-anchor="middle" font-size="22"'
        f' font-weight="bold" fill="white">{_x(title)}</text>'
    )
    svg.append(
        f'<text x="{W//2}" y="56" text-anchor="middle" font-size="12" fill="#90CAF9">'
        'Click a wire or row to highlight · Press Esc to clear</text>'
    )

    for cl in layout.left_connectors:
        svg.extend(_connector_svg(cl, is_left=True))
    for cr in layout.right_connectors:
        svg.extend(_connector_svg(cr, is_left=False))

    svg.append('<g id="hitAreas">')
    for wl in layout.wire_layouts:
        svg.append(
            f'<path d="{_bez(wl.y_left, wl.y_right)}" stroke="transparent"'
            f' stroke-width="14" fill="none" data-wid="{wl.wire.wid}" style="cursor:pointer"/>'
        )
    svg.append('</g>')

    svg.append('<g id="wires">')
    for wl in layout.wire_layouts:
        w   = wl.wire
        col = resolve(w.colour)
        d   = _bez(wl.y_left, wl.y_right)
        if is_light(col):
            svg.append(
                f'<path id="wireBG_{w.wid}" d="{d}" stroke="#90A4AE"'
                f' stroke-width="3.4" fill="none" opacity="0.9" pointer-events="none"/>'
            )
        svg.append(
            f'<path id="wire_{w.wid}" d="{d}" stroke="{col}"'
            f' stroke-width="2" fill="none" opacity="0.85" pointer-events="none"/>'
        )
        svg.append(
            f'<circle id="dot33_{w.wid}" cx="{WIRE_LEFT_X}" cy="{wl.y_left}" r="4.5"'
            f' fill="{col}" stroke="white" stroke-width="1.2" pointer-events="none"/>'
        )
        svg.append(
            f'<circle id="dotR_{w.wid}" cx="{WIRE_RIGHT_X}" cy="{wl.y_right}" r="4.5"'
            f' fill="{col}" stroke="white" stroke-width="1.2" pointer-events="none"/>'
        )
    svg.append('</g>')

    if layout.pair_groups:
        wid_ymid = {wl.wire.wid: (wl.y_left + wl.y_right) // 2
                    for wl in layout.wire_layouts}
        svg.append('<g id="twistSyms">')
        placed: list[tuple[int, int, int]] = []   # (cx, y_full_top, y_full_bot)
        _OFFSETS = [0, 40, -40, 80, -80, 120, -120]
        MAX_H = 2 * ROW_H
        for pair_name, wids in layout.pair_groups.items():
            ys = [wid_ymid[wid] for wid in wids if wid in wid_ymid]
            if len(ys) < 2:
                continue
            top, bot = min(ys), max(ys)
            if bot - top <= MAX_H:
                h_top, h_bot = top, bot
            else:
                mid   = (top + bot) // 2
                h_top = mid - MAX_H // 2
                h_bot = mid + MAX_H // 2
            y_full_top = min(top, h_top) - 16   # headroom for the label text
            y_full_bot = max(bot, h_bot)
            x_offset = 0   # fallback if all slots collide
            for offset in _OFFSETS:
                cx = _TWIST_X + offset
                if not any(
                    abs(cx - px) < _SYM_W
                    and not (y_full_bot < py_top or y_full_top > py_bot)
                    for px, py_top, py_bot in placed
                ):
                    x_offset = offset
                    placed.append((cx, y_full_top, y_full_bot))
                    break
            else:
                placed.append((_TWIST_X, y_full_top, y_full_bot))
            svg.extend(_twist_sym_svg(ys, pair_name, x_offset))
        svg.append('</g>')

    svg.append('<g id="terms">')
    for wl in layout.wire_layouts:
        w = wl.wire
        if w.right_pin is None and w.right_conn:
            svg.extend(_term_sym(w.wid, w.right_conn, wl.y_right, resolve(w.colour), w.signal))
    svg.append('</g>')

    svg.append(f'<g id="infoPanel" opacity="0" pointer-events="none">')
    svg.append(
        f'<rect x="{mid_x-220}" y="{panel_y}" width="440" height="54" rx="8"'
        f' fill="#1A237E" stroke="#90CAF9" stroke-width="1.5"/>'
    )
    svg.append(
        f'<text id="infoTitle" x="{mid_x}" y="{panel_y+20}" text-anchor="middle"'
        f' font-size="13" font-weight="bold" fill="white"> </text>'
    )
    svg.append(
        f'<text id="infoSub" x="{mid_x}" y="{panel_y+39}" text-anchor="middle"'
        f' font-size="11" fill="#90CAF9"> </text>'
    )
    svg.append('</g>')

    svg.append(
        f'<rect x="30" y="{panel_y}" width="320" height="60" rx="6"'
        f' fill="white" stroke="#B0BEC5" stroke-width="1.5"/>'
    )
    svg.append(f'<text x="40" y="{panel_y+16}" font-size="10" font-weight="bold" fill="#263238">Legend</text>')
    svg.append(f'<text x="40" y="{panel_y+34}" font-size="9" fill="#263238">Wire colours reflect the physical cable colour in the harness.</text>')
    svg.append(f'<text x="40" y="{panel_y+50}" font-size="9" fill="#263238">Click a wire or row to highlight its end-to-end route.</text>')

    svg.append('</svg>')

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{_x(title)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#6b8291;display:flex;flex-direction:column;align-items:center;
  padding:16px;font-family:Arial,sans-serif;min-height:100vh}}
#svgWrap{{background:white;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.35);
  overflow-x:auto;max-width:100%}}
#svgWrap svg{{display:block}}
#controls{{margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:center}}
.btn{{padding:9px 22px;color:#fff;text-decoration:none;border-radius:5px;font-size:13px;
  font-weight:700;border:none;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.25)}}
.btn-blue{{background:#1565C0}}.btn-blue:hover{{background:#0D47A1}}
.btn-green{{background:#2E7D32}}.btn-green:hover{{background:#1B5E20}}
#hint{{font-size:12px;color:#dde}}
#notes,#cutList{{margin-top:16px;background:white;border-radius:8px;padding:16px 22px;
  max-width:{W}px;width:100%;box-shadow:0 2px 10px rgba(0,0,0,.25)}}
#notes h2,#cutList h2{{font-size:14px;font-weight:700;color:#1A237E;margin-bottom:8px;
  border-bottom:1px solid #C5CAE9;padding-bottom:6px}}
#notes p{{font-size:13px;color:#263238;line-height:1.5;margin-top:6px}}
#cutList table{{width:100%;border-collapse:collapse;font-size:12px}}
#cutList th{{text-align:left;padding:5px 8px;background:#E8EAF6;color:#1A237E;
  font-weight:700;border-bottom:2px solid #9FA8DA}}
#cutList td{{padding:4px 8px;border-bottom:1px solid #ECEFF1;color:#263238}}
#cutList tbody tr:nth-child(even) td{{background:#F5F7FA}}
#cutList tfoot .tot-label{{text-align:right;font-weight:600;background:#E8EAF6;
  border-top:2px solid #9FA8DA}}
#cutList tfoot .tot-val{{font-weight:600;background:#E8EAF6;border-top:2px solid #9FA8DA}}
#cutList tfoot .tot-note{{font-size:11px;color:#78909C;font-style:italic}}
.swatch{{display:inline-block;width:10px;height:10px;border-radius:2px;
  border:1px solid rgba(0,0,0,.25);margin-right:5px;vertical-align:middle}}
</style></head><body>
<div id="svgWrap">{chr(10).join(svg)}</div>
<div id="controls">
<a class="btn btn-blue" id="dlSvg" href="#">&#11015; Download SVG</a>
<a class="btn btn-green" id="dlHtml" href="#">&#11015; Download HTML</a>
<span id="hint">Click any wire, pin row, or termination row to highlight. Click again or Esc to clear.</span>
</div>
{_notes_html(layout.notes)}
{_cut_list_html(layout)}
<script>{_build_js(layout, title)}</script>
</body></html>"""
