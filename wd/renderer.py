from __future__ import annotations
import json
import math
import re
from .i18n import STRINGS
from .layout import (
    DiagramLayout, ConnectorLayout, WireLayout,
    CONN_HEADER_H, ROW_H, BOT_PAD, WARN_BOX_PAD, WARN_BOX_H,
    WIRE_LEFT_X, WIRE_RIGHT_X,
)
from .colours import resolve, resolve_pair, is_light, colour_name

def _pin_key(pin: str) -> list:
    return [int(c) if c.isdigit() else c.lower()
            for c in re.split(r'(\d+)', str(pin))]


# Bezier control-point x positions, tuned to match the reference diagram style.
_SPAN    = WIRE_RIGHT_X - WIRE_LEFT_X
_CP1_X   = round(WIRE_LEFT_X  + _SPAN * 0.38)   # departs horizontally from left
_CP2_X   = round(WIRE_RIGHT_X - _SPAN * 0.15)   # arrives horizontally at right
_TWIST_T0 = 0.30   # Bézier parameter where the twist zone begins
_TWIST_T1 = 0.70   # Bézier parameter where the twist zone ends (one full twist → N must be int)
_N_SAMP   = 60     # polyline sample count for twisted wire paths

# ── Cable band colour palette (stroke, fill) ─────────────────────────────────
_CABLE_PALETTE = [
    ("#546E7A", "#B0BEC5"),   # blue-grey
    ("#5D4037", "#D7B9AC"),   # brown
    ("#2E7D32", "#A5D6A7"),   # green
    ("#E65100", "#FFCC80"),   # orange
    ("#6A1B9A", "#CE93D8"),   # purple
    ("#00695C", "#80CBC4"),   # teal
]

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


def _bezier_pt(t: float, y_left: float, y_right: float) -> tuple[float, float]:
    """Evaluate the wire cubic Bézier at parameter t, returning (x, y)."""
    x = ((1-t)**3*WIRE_LEFT_X + 3*(1-t)**2*t*_CP1_X
         + 3*(1-t)*t**2*_CP2_X + t**3*WIRE_RIGHT_X)
    y = y_left*(1-t)**2*(1+2*t) + y_right*t**2*(3-2*t)
    return x, y


def _twisted_paths(
    wl1: WireLayout, wl2: WireLayout,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Sample both wires of a twisted pair, applying one full sinusoidal twist in the zone."""
    pts1: list[tuple[float, float]] = []
    pts2: list[tuple[float, float]] = []
    for i in range(_N_SAMP + 1):
        t = i / _N_SAMP
        x, y1 = _bezier_pt(t, wl1.y_left, wl1.y_right)
        _,  y2 = _bezier_pt(t, wl2.y_left, wl2.y_right)
        if _TWIST_T0 <= t <= _TWIST_T1:
            s   = (t - _TWIST_T0) / (_TWIST_T1 - _TWIST_T0)  # 0→1 through zone
            yc  = (y1 + y2) / 2
            amp = (y2 - y1) / 2
            # One full twist: cos starts and ends at 1 so endpoints rejoin naturally
            twist = amp * math.cos(2 * math.pi * s)
            y1, y2 = yc - twist, yc + twist
        pts1.append((x, y1))
        pts2.append((x, y2))
    return pts1, pts2


def _pts_path(pts: list[tuple[float, float]]) -> str:
    cmd = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for x, y in pts[1:]:
        cmd.append(f"L{x:.1f},{y:.1f}")
    return " ".join(cmd)


def _twisted_pair_svg(wl1: WireLayout, wl2: WireLayout) -> list[str]:
    """Draw a 2-wire twisted pair with actual crossing effect instead of an overlay symbol."""
    w1, w2   = wl1.wire, wl2.wire
    col1, col2 = resolve(w1.colour), resolve(w2.colour)

    pts1, pts2 = _twisted_paths(wl1, wl2)
    d1, d2 = _pts_path(pts1), _pts_path(pts2)

    out: list[str] = []

    # Halos for light-coloured wires (drawn first so they sit below the wire)
    if is_light(col1):
        out.append(f'<path id="wireBG_{w1.wid}" d="{d1}" stroke="#90A4AE"'
                   f' stroke-width="3.4" fill="none" opacity="0.9" pointer-events="none"/>')
    if is_light(col2):
        out.append(f'<path id="wireBG_{w2.wid}" d="{d2}" stroke="#90A4AE"'
                   f' stroke-width="3.4" fill="none" opacity="0.9" pointer-events="none"/>')

    out.append(f'<path id="wire_{w1.wid}" d="{d1}" stroke="{col1}"'
               f' stroke-width="2" fill="none" opacity="0.85" pointer-events="none"/>')
    out.append(f'<path id="wire_{w2.wid}" d="{d2}" stroke="{col2}"'
               f' stroke-width="2" fill="none" opacity="0.85" pointer-events="none"/>')

    # Crossing indices — for _N_SAMP=60, both cross points land exactly on a sample
    c1 = round(_N_SAMP * (_TWIST_T0 + 0.25 * (_TWIST_T1 - _TWIST_T0)))
    c2 = round(_N_SAMP * (_TWIST_T0 + 0.75 * (_TWIST_T1 - _TWIST_T0)))

    # Which wire is naturally above (smaller y) at the zone entrance?
    _, y1_z = _bezier_pt(_TWIST_T0, wl1.y_left, wl1.y_right)
    _, y2_z = _bezier_pt(_TWIST_T0, wl2.y_left, wl2.y_right)
    # The naturally-above wire goes OVER at crossing 1, the other goes OVER at crossing 2.
    # Each tuple: (crossing_idx, under_pts, over_pts, over_col, over_wid)
    if y1_z <= y2_z:
        crossings = [(c1, pts2, pts1, col1, w1.wid), (c2, pts1, pts2, col2, w2.wid)]
    else:
        crossings = [(c1, pts1, pts2, col2, w2.wid), (c2, pts2, pts1, col1, w1.wid)]

    GAP_R, GAP_W, N_OVER = 5, 5, 3
    BG = "#F0F2F5"   # matches the SVG background rect

    for c_idx, under_pts, over_pts, over_col, over_wid in crossings:
        x_c, y_c = pts1[c_idx]   # at crossing, both paths share (x, y_center)

        # Perpendicular direction to the under wire at the crossing
        if 0 < c_idx < len(under_pts) - 1:
            dx = under_pts[c_idx+1][0] - under_pts[c_idx-1][0]
            dy = under_pts[c_idx+1][1] - under_pts[c_idx-1][1]
            L  = math.hypot(dx, dy)
            px, py = (-dy/L, dx/L) if L > 0 else (0.0, 1.0)
        else:
            px, py = 0.0, 1.0

        # White gap masks the under wire at the crossing
        out.append(
            f'<line x1="{x_c+px*GAP_R:.1f}" y1="{y_c+py*GAP_R:.1f}"'
            f' x2="{x_c-px*GAP_R:.1f}" y2="{y_c-py*GAP_R:.1f}"'
            f' stroke="{BG}" stroke-width="{GAP_W}" stroke-linecap="round"'
            f' pointer-events="none"/>'
        )

        # Redraw the over wire through the crossing so it appears on top.
        # ID is required so the JS fade/highlight machinery can control this element.
        seg = over_pts[max(0, c_idx-N_OVER): c_idx+N_OVER+1]
        if len(seg) > 1:
            out.append(
                f'<path id="wireOD_{over_wid}" d="{_pts_path(seg)}" stroke="{over_col}"'
                f' stroke-width="2" fill="none" opacity="0.85" pointer-events="none"/>'
            )

    # Endpoint dots
    for wl in [wl1, wl2]:
        w    = wl.wire
        bpair = resolve_pair(w.colour)
        if bpair:
            dc1, dc2 = bpair
            out += [
                f'<circle id="dot33_{w.wid}" cx="{WIRE_LEFT_X}" cy="{wl.y_left}" r="5"'
                f' fill="{dc2}" stroke="{dc1}" stroke-width="2.5" pointer-events="none"/>',
                f'<circle id="dotR_{w.wid}" cx="{WIRE_RIGHT_X}" cy="{wl.y_right}" r="5"'
                f' fill="{dc2}" stroke="{dc1}" stroke-width="2.5" pointer-events="none"/>',
            ]
        else:
            dcol = resolve(w.colour)
            out += [
                f'<circle id="dot33_{w.wid}" cx="{WIRE_LEFT_X}" cy="{wl.y_left}" r="4.5"'
                f' fill="{dcol}" stroke="white" stroke-width="1.2" pointer-events="none"/>',
                f'<circle id="dotR_{w.wid}" cx="{WIRE_RIGHT_X}" cy="{wl.y_right}" r="4.5"'
                f' fill="{dcol}" stroke="white" stroke-width="1.2" pointer-events="none"/>',
            ]

    return out


def _cable_band_svg(name: str, cable_idx: int, wids: list[str],
                    wid_to_wl: dict[str, "WireLayout"]) -> list[str]:
    wls = [wid_to_wl[wid] for wid in wids if wid in wid_to_wl]
    if not wls:
        return []
    stroke_col, fill_col = _CABLE_PALETTE[cable_idx % len(_CABLE_PALETTE)]
    pad = 6
    yl_lo = min(wl.y_left  for wl in wls) - pad
    yl_hi = max(wl.y_left  for wl in wls) + pad
    yr_lo = min(wl.y_right for wl in wls) - pad
    yr_hi = max(wl.y_right for wl in wls) + pad
    x0, x1 = WIRE_LEFT_X - 4, WIRE_RIGHT_X + 4
    pts = f"{x0},{yl_lo} {x1},{yr_lo} {x1},{yr_hi} {x0},{yl_hi}"
    lx  = (x0 + x1) // 2
    ly  = (yl_lo + yr_lo) // 2 - 9   # baseline sits 9px above the band's top edge
    return [
        f'<polygon points="{pts}" fill="{fill_col}" fill-opacity="0.25"'
        f' stroke="{stroke_col}" stroke-width="1.2" stroke-dasharray="6,3"'
        f' pointer-events="none"/>',
        f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="12"'
        f' fill="{stroke_col}" font-style="italic" pointer-events="none">{_x(name)}</text>',
    ]


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
            out.append(f'<g data-wid="{row.wire.wid}" style="cursor:pointer">')
            out.append(
                f'<rect id="rowL_{row.wire.wid}"'
                f' x="{cx+2}" y="{ry}" width="{cw-4}" height="{ROW_H}" rx="2"'
                f' fill="{fill}" opacity="0.6"/>'
            )
            out.append(
                f'<text x="{cx+8}" y="{row.y+4}" font-size="10" font-weight="bold"'
                f' fill="#1A237E">{row.wire.left_pin}</text>'
            )
            out.append(
                f'<text x="{cx+28}" y="{row.y+4}" font-size="9.5"'
                f' fill="#263238">{_x(row.wire.signal)}</text>'
            )
            out.append('</g>')
        else:
            out.append(f'<g data-wid="{row.wire.wid}" style="cursor:pointer">')
            out.append(
                f'<rect id="rowR_{row.wire.wid}"'
                f' x="{cx+2}" y="{ry}" width="{cw-4}" height="{ROW_H}" rx="2"'
                f' fill="{fill}" opacity="0.6"/>'
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
            out.append('</g>')

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
def _build_js(layout: DiagramLayout, title: str, default_lang: str = "en") -> str:
    wire_meta = []
    for wl in layout.wire_layouts:
        w = wl.wire
        wire_meta.append({
            "wid":      w.wid,
            "signal":   w.signal,
            "leftConn": w.left_conn,
            "leftPin":  w.left_pin,
            "rightConn": w.right_conn,
            "rightPin":  w.right_pin,   # None → null in JSON; null = free-end/termination group
            "colName":  colour_name(w.colour),
            "isLight":  is_light(resolve(w.colour)),
            "length":   w.length,
        })

    safe_title = _x(title)
    lang_json  = json.dumps(STRINGS, ensure_ascii=False, separators=(',', ':'))
    wire_json  = json.dumps(wire_meta, separators=(',', ':'))
    return f"""
const LANG={lang_json};
const wireData={wire_json};
const ALL=wireData.map(w=>w.wid);
let sel=null;
let curLang=localStorage.getItem('wdLang')||'{default_lang}';
const svg=document.getElementById('mainSvg');
const TERM_PFX=['termSym_','termTail_','termSleeve_'];
const WIRE_PFX=['wire_','wireBG_','wireB2_','wireOD_','dot33_','dotR_'];
function t(k){{return((LANG[k]||{{}})[curLang]||(LANG[k]||{{}})['en'])||k;}}
function setLang(lang){{
  curLang=lang;
  document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.getAttribute('data-i18n')));
  const btn=document.getElementById('langBtn');
  if(btn)btn.textContent=t('lang_switch');
  document.documentElement.lang=lang;
  localStorage.setItem('wdLang',lang);
  if(sel)renderInfoPanel(sel);
}}
function toggleLang(){{setLang(curLang==='en'?'zh':'en');}}
function getElems(wid){{
  return [...WIRE_PFX,...TERM_PFX].map(p=>document.getElementById(p+wid)).filter(Boolean);
}}
function clearAll(){{
  ALL.forEach(wid=>{{
    getElems(wid).forEach(e=>{{e.style.opacity='';e.style.filter='';}});
    const wp=document.getElementById('wire_'+wid);
    if(wp)wp.setAttribute('stroke-width','2');
    const wb2c=document.getElementById('wireB2_'+wid);
    if(wb2c)wb2c.setAttribute('stroke-width','2');
    const wod0=document.getElementById('wireOD_'+wid);
    if(wod0)wod0.setAttribute('stroke-width','2');
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
  const wb2=document.getElementById('wireB2_'+wid);
  if(wb2){{wb2.style.opacity='1';wb2.setAttribute('stroke-width','4');}}
  const wod=document.getElementById('wireOD_'+wid);
  if(wod){{wod.style.opacity='1';wod.setAttribute('stroke-width','4');}}
  const wb=document.getElementById('wireBG_'+wid);
  if(wb){{wb.style.opacity='1';wb.setAttribute('stroke','#37474F');wb.setAttribute('stroke-width',wd.isLight?'5':'3.4');}}
  [...WIRE_PFX.slice(2),...TERM_PFX].forEach(p=>{{
    const e=document.getElementById(p+wid);if(e)e.style.opacity='1';
  }});
  ['rowL_','rowR_'].forEach(p=>{{
    const r=document.getElementById(p+wid);
    if(r){{r.setAttribute('fill','#FFEB3B');r.style.opacity='1';r.style.filter='none';}}
  }});
  document.getElementById('infoPanel').setAttribute('opacity','1');
  renderInfoPanel(wid);
}}
function renderInfoPanel(wid){{
  const wd=wireData.find(w=>w.wid===wid);
  if(!wd)return;
  const rDesc=wd.rightPin!==null
    ?wd.rightConn+' '+t('info_pin')+' '+wd.rightPin
    :wd.rightConn;
  document.getElementById('infoTitle').textContent=
    wd.signal+' ('+wd.leftConn+' '+t('info_pin')+' '+wd.leftPin+' → '+rDesc+')';
  document.getElementById('infoSub').textContent=
    t('info_wire')+': '+wd.colName+(wd.rightPin===null?' | '+t('info_term')+': '+rDesc:'')+(wd.length?' | '+t('info_length')+': '+wd.length:'');
}}
document.querySelectorAll('[id^="rowL_"],[id^="rowR_"]').forEach(r=>
  r.dataset.origFill=r.getAttribute('fill'));
svg.addEventListener('click',e=>{{
  const el=e.target.closest('[data-wid]');
  if(el)highlight(el.getAttribute('data-wid'));else clearAll();
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
setLang(curLang);
"""


def _notes_html(notes: list[str]) -> str:
    if not notes:
        return ""
    paras = "".join(f"<p>{_x(n)}</p>" for n in notes)
    return f'<div id="notes"><h2 data-i18n="notes_heading">Notes</h2>{paras}</div>'


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

    conn_order = {cl.spec.name: i for i, cl in enumerate(layout.left_connectors)}
    has_cables = any(w.cable for w in wires)

    if has_cables:
        sorted_wires = sorted(wires, key=lambda w: (
            0 if w.cable else 1,
            w.cable,
            conn_order.get(w.left_conn, 999),
            _pin_key(w.left_pin),
        ))
    else:
        sorted_wires = sorted(wires, key=lambda w: (conn_order.get(w.left_conn, 999), _pin_key(w.left_pin)))

    rows: list[str] = []
    last_cable: str | None = None
    for w in sorted_wires:
        if has_cables and w.cable != last_cable:
            last_cable = w.cable
            if w.cable:
                rows.append(
                    f'<tr class="cable-hdr"><td colspan="7">'
                    f'<span data-i18n="cable_group">Cable</span>: {_x(w.cable)}</td></tr>'
                )
        col      = resolve(w.colour)
        col_nm   = colour_name(w.colour)
        right_pin = str(w.right_pin) if w.right_pin is not None else "—"
        length   = _x(w.length) if w.length else "—"
        spair    = resolve_pair(w.colour)
        if spair:
            swatch = (f'<span class="swatch" style="background:linear-gradient('
                      f'135deg,{spair[0]} 50%,{spair[1]} 50%)"></span>')
        else:
            swatch = f'<span class="swatch" style="background:{col}"></span>'
        rows.append(
            f"<tr>"
            f"<td>{_x(w.signal)}</td>"
            f"<td>{_x(w.left_conn)}</td><td>{w.left_pin}</td>"
            f"<td>{_x(w.right_conn)}</td><td>{right_pin}</td>"
            f"<td>{swatch}{_x(col_nm)}</td>"
            f"<td>{length}</td>"
            f"</tr>"
        )

    # Cable conductors are excluded from per-colour totals: you buy the cable
    # as a unit, so only ungrouped conductors contribute to colour totals.
    cable_max: dict[str, tuple[float, str]] = {}   # cable_name → (max conductor length, unit)
    cable_has_unparsed: set[str] = set()
    colour_totals: dict[tuple[str, str], float] = {}
    has_unparsed_ungrouped = False

    for w in sorted_wires:
        if not w.length:
            continue
        parsed = _parse_length(w.length)
        if w.cable:
            if parsed is None:
                cable_has_unparsed.add(w.cable)
            else:
                val, unit = parsed
                prev = cable_max.get(w.cable)
                if prev is None or val > prev[0]:
                    cable_max[w.cable] = (val, unit)
        else:
            if parsed is None:
                has_unparsed_ungrouped = True
            else:
                val, unit = parsed
                key = (colour_name(w.colour), unit)
                colour_totals[key] = colour_totals.get(key, 0.0) + val

    tfoot_rows: list[str] = []
    has_any_unparsed = False

    if cable_max or cable_has_unparsed:
        tfoot_rows.append(
            '<tr><td colspan="7" class="tot-section" data-i18n="totals_cables">'
            'Cable lengths required</td></tr>'
        )
        seen_cables: list[str] = []
        for w in sorted_wires:
            if w.cable and w.cable not in seen_cables:
                seen_cables.append(w.cable)
        for cname in seen_cables:
            if cname in cable_has_unparsed:
                has_any_unparsed = True
            flag = " *" if cname in cable_has_unparsed else ""
            if cname in cable_max:
                val, unit = cable_max[cname]
                tfoot_rows.append(
                    f'<tr><td colspan="6" class="tot-label">{_x(cname)}{flag}</td>'
                    f'<td class="tot-val">{val:.4g}{unit}</td></tr>'
                )
            else:
                tfoot_rows.append(
                    f'<tr><td colspan="6" class="tot-label">{_x(cname)} *</td>'
                    f'<td class="tot-val">—</td></tr>'
                )

    if colour_totals:
        if tfoot_rows:
            tfoot_rows.append(
                '<tr><td colspan="7" class="tot-section" data-i18n="totals_conductors">'
                'Individual conductors</td></tr>'
            )
        if has_unparsed_ungrouped:
            has_any_unparsed = True
        note = " *" if has_unparsed_ungrouped else ""
        for (col_nm, unit), val in sorted(colour_totals.items()):
            tfoot_rows.append(
                f'<tr><td colspan="6" class="tot-label">{_x(col_nm)} ({unit or "no unit"}){note}</td>'
                f'<td class="tot-val">{val:.4g}{unit}</td></tr>'
            )

    tfoot = ""
    if tfoot_rows:
        disclaimer = (
            '<tr><td colspan="7" class="tot-note" data-i18n="totals_note">'
            '* Some wires have non-numeric lengths and are excluded from totals.</td></tr>'
            if has_any_unparsed else ""
        )
        tfoot = f"<tfoot>{''.join(tfoot_rows)}{disclaimer}</tfoot>"

    return (
        '<div id="cutList"><h2 data-i18n="cut_heading">Cut list</h2>'
        '<table><thead><tr>'
        '<th data-i18n="col_signal">Signal</th>'
        '<th data-i18n="col_from">From</th>'
        '<th data-i18n="col_pin">Pin</th>'
        '<th data-i18n="col_to">To</th>'
        '<th data-i18n="col_pin">Pin</th>'
        '<th data-i18n="col_colour">Colour</th>'
        '<th data-i18n="col_length">Length</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody>{tfoot}</table></div>"
    )


# ── Main render entry point ───────────────────────────────────────────────────
def render_html(layout: DiagramLayout, title: str, default_lang: str = "en") -> str:
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
        f'<text id="svgHint" data-i18n="hint_header" x="{W//2}" y="56"'
        f' text-anchor="middle" font-size="12" fill="#90CAF9">'
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

    wid_to_wl: dict[str, WireLayout] = {wl.wire.wid: wl for wl in layout.wire_layouts}

    if layout.cable_groups:
        svg.append('<g id="cableBands">')
        for ci, (cname, wids) in enumerate(layout.cable_groups.items()):
            svg.extend(_cable_band_svg(cname, ci, wids, wid_to_wl))
        svg.append('</g>')

    # Wires that belong to exactly-2-wire pairs are drawn later with crossing effect
    pair2_wids: set[str] = set()
    pair2_pairs: list[tuple[WireLayout, WireLayout]] = []
    drawn_pairs: set[str] = set()
    for wids in layout.pair_groups.values():
        if len(wids) == 2:
            pair2_wids.update(wids)

    svg.append('<g id="wires">')
    for wl in layout.wire_layouts:
        if wl.wire.wid in pair2_wids:
            continue
        w    = wl.wire
        pair = resolve_pair(w.colour)
        col  = resolve(w.colour)
        d    = _bez(wl.y_left, wl.y_right)
        if pair:
            col1, col2 = pair
            svg.append(
                f'<path id="wire_{w.wid}" d="{d}" stroke="{col1}"'
                f' stroke-dasharray="6,6" stroke-width="2" fill="none" opacity="0.85"'
                f' pointer-events="none"/>'
            )
            svg.append(
                f'<path id="wireB2_{w.wid}" d="{d}" stroke="{col2}"'
                f' stroke-dasharray="6,6" stroke-dashoffset="6" stroke-width="2"'
                f' fill="none" opacity="0.85" pointer-events="none"/>'
            )
            svg.append(
                f'<circle id="dot33_{w.wid}" cx="{WIRE_LEFT_X}" cy="{wl.y_left}" r="5"'
                f' fill="{col2}" stroke="{col1}" stroke-width="2.5" pointer-events="none"/>'
            )
            svg.append(
                f'<circle id="dotR_{w.wid}" cx="{WIRE_RIGHT_X}" cy="{wl.y_right}" r="5"'
                f' fill="{col2}" stroke="{col1}" stroke-width="2.5" pointer-events="none"/>'
            )
        else:
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

    if pair2_wids:
        svg.append('<g id="twistWires">')
        for wids in layout.pair_groups.values():
            if len(wids) != 2:
                continue
            key = wids[0] + ":" + wids[1]
            if key in drawn_pairs:
                continue
            drawn_pairs.add(key)
            svg.extend(_twisted_pair_svg(wid_to_wl[wids[0]], wid_to_wl[wids[1]]))
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
    svg.append(
        f'<text id="lgdTitle" data-i18n="legend_title" x="40" y="{panel_y+16}"'
        f' font-size="10" font-weight="bold" fill="#263238">Legend</text>'
    )
    svg.append(
        f'<text id="lgdLine1" data-i18n="legend_line1" x="40" y="{panel_y+34}"'
        f' font-size="9" fill="#263238">Wire colours reflect the physical cable colour in the harness.</text>'
    )
    svg.append(
        f'<text id="lgdLine2" data-i18n="legend_line2" x="40" y="{panel_y+50}"'
        f' font-size="9" fill="#263238">Click a wire or row to highlight its end-to-end route.</text>'
    )

    svg.append('</svg>')

    return f"""<!DOCTYPE html>
<html lang="{default_lang}"><head>
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
.btn-grey{{background:#546E7A}}.btn-grey:hover{{background:#37474F}}
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
#cutList tfoot .tot-section{{text-align:left;font-weight:700;background:#C5CAE9;
  color:#1A237E;border-top:2px solid #9FA8DA;padding:6px 8px}}
#cutList tfoot .tot-label{{text-align:right;font-weight:600;background:#E8EAF6;
  border-top:2px solid #9FA8DA}}
#cutList tfoot .tot-val{{font-weight:600;background:#E8EAF6;border-top:2px solid #9FA8DA}}
#cutList tfoot .tot-note{{font-size:11px;color:#78909C;font-style:italic}}
#cutList tr.cable-hdr td{{background:#E8EAF6;font-weight:700;color:#1A237E;
  font-style:italic;padding:6px 8px;border-top:2px solid #9FA8DA}}
.swatch{{display:inline-block;width:10px;height:10px;border-radius:2px;
  border:1px solid rgba(0,0,0,.25);margin-right:5px;vertical-align:middle}}
</style></head><body>
<div id="svgWrap">{chr(10).join(svg)}</div>
<div id="controls">
<a class="btn btn-blue" id="dlSvg" href="#" data-i18n="btn_svg">⬇ Download SVG</a>
<a class="btn btn-green" id="dlHtml" href="#" data-i18n="btn_html">⬇ Download HTML</a>
<button class="btn btn-grey" id="langBtn" onclick="toggleLang()">中文</button>
<span id="hint" data-i18n="hint_controls">Click any wire, pin row, or termination to highlight. Click again or Esc to clear.</span>
</div>
{_notes_html(layout.notes)}
{_cut_list_html(layout)}
<script>{_build_js(layout, title, default_lang)}</script>
</body></html>"""
