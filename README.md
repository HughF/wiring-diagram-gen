# Wiring Diagram Generator

Generates interactive, self-contained HTML wiring harness diagrams from a CSV file.

The output is a single `.html` file containing an SVG diagram with click-to-highlight interactivity and download buttons for both SVG and HTML. No internet connection is required to view it.

---

## Requirements

Python 3.10 or later. No third-party packages.

---

## Quick start

```
python wiring_diagram.py examples/drive_tray.csv
```

This writes `examples/drive_tray.html`. Open it in any browser.

---

## Command-line options

```
python wiring_diagram.py <input.csv> [options]

  input.csv             CSV file describing the harness (see below)

  -o, --output FILE     Where to write the HTML (default: same path as CSV, .html extension)
  --title TEXT          Title shown in the diagram header (default: CSV filename without extension)
  --width PX            SVG canvas width in pixels (default: 1380)
```

Examples:

```bash
# Write to a specific location
python wiring_diagram.py my_harness.csv -o ~/Documents/my_harness.html

# Override the title
python wiring_diagram.py my_harness.csv --title "Main Control Box — Wiring Harness Rev 3"

# Wider canvas for a harness with many wires
python wiring_diagram.py my_harness.csv --width 1600
```

---

## CSV format

### Header row

The first non-blank, non-comment row is the header. Column names are matched
**case-insensitively** and **in any order**, so you can use whatever names feel
natural in your spreadsheet. The accepted aliases for each field are listed below.

| Field | Accepted column names |
|---|---|
| Signal name | `Signal`, `Signal Name`, `Name`, `Wire`, `Wire Name` |
| Left connector | `Left Connector`, `Left Conn`, `From Connector`, `From`, `Source Connector`, `Source` |
| Left pin | `Left Pin`, `From Pin`, `Source Pin`, `Pin (Left)`, `Left Pin No` |
| Right connector | `Right Connector`, `Right Conn`, `To Connector`, `To`, `Dest Connector`, `Destination Connector`, `Destination`, `Termination`, `Termination Type` |
| Right pin | `Right Pin`, `To Pin`, `Dest Pin`, `Destination Pin`, `Pin (Right)`, `Right Pin No` |
| Wire colour | `Wire Colour`, `Wire Color`, `Colour`, `Color`, `Wire Col` |
| Warning | `Warning`, `Note`, `Notes`, `Annotation`, `Remark` |
| Twisted pair group | `Pair`, `Twisted Pair`, `TP`, `Pair Group`, `Cable Group` |

The `Warning` and `Pair` columns are optional. All other fields are required.

### Wire rows

Each row describes one wire. Blank rows and rows beginning with `#` are ignored
(use them as section separators or comments).

```
Signal,Left Connector,Left Pin,Right Connector,Right Pin,Wire Colour,Warning
Step+,Main PCB,9,Drive D-Sub,42,Purple,
L,Main PCB,1,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
```

### Connectors

Connectors are discovered automatically from the data — you do not define them
separately. The name you write in `Left Connector` or `Right Connector` becomes
the panel label in the diagram.

**Multiple connectors on each side are supported.** Each unique name becomes a
separate connector panel, stacked top-to-bottom in the order it first appears in
the CSV.

```
# Two left-side connectors feeding one right-side D-Sub
Signal,Left Connector,Left Pin,Right Connector,Right Pin,Wire Colour
Step+,Power PCB,1,Drive D-Sub,42,Purple
Enable,IO PCB,3,Drive D-Sub,7,Green
```

### Pinned connectors vs. free-end termination groups

The `Right Pin` column determines how the right-side panel is drawn:

| `Right Pin` | Behaviour |
|---|---|
| A number | **Pinned connector** — pin numbers are shown in the panel (e.g. D-Sub, Molex). Rows are sorted to minimise wire crossings. |
| Blank, `N/C`, or `NC` | **Free-end termination group** — the `Right Connector` name becomes the section heading (e.g. "Bootlace ferrule", "3/16 female spade"). No pin numbers are shown; rows are labelled with the left-side pin number for reference. |

You can mix pinned connectors and free-end groups freely on the right side.

### Wire colour

Write the colour name in plain English or as a hex value:

| Name | Rendered colour |
|---|---|
| `Purple` | Deep purple |
| `Red` | Material red |
| `Green` | Material green |
| `White` | Off-white (rendered with a grey outline so it is visible) |
| `Yellow` | Amber yellow |
| `Blue` | Material blue |
| `Black` | Near-black |
| `Orange` | Deep orange |
| `Brown` | Dark brown |
| `Grey` / `Gray` | Blue-grey |
| `Pink` | Hot pink |
| `Violet` | Dark violet |
| `Cyan` | Teal |
| `Lime` | Dark lime green |
| `Silver` | Medium grey |
| `#RRGGBB` | Any hex colour passed through directly |

Colour names are case-insensitive. Unknown names render as medium grey.

### Warning boxes

If a wire has text in the `Warning` column, a dashed warning box is rendered
inside the right-side termination section that wire connects to. Multiple wires
in the same section can share the same warning text — identical texts are
de-duplicated into one box. Different warning texts each get their own box.

```
L,Main PCB,1,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
N,Main PCB,2,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
E,Main PCB,3,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
```

The three identical warnings above produce one box in the "AC Mains" section.

Warning boxes only appear on right-side panels. Text longer than ~46 characters
is word-wrapped automatically (up to 3 lines).

### Twisted pair groups

Assign a group name in the `Pair` column to mark wires that run as a twisted pair. Any two (or more) wires sharing the same group name get a small helix symbol drawn between them at the midpoint of the wire span.

```
Step+,Main PCB,9,Drive D-Sub,42,Purple,,TP1
Step-,Main PCB,10,Drive D-Sub,41,Red,,TP1
Dir+,Main PCB,11,Drive D-Sub,40,Green,,TP2
Dir-,Main PCB,12,Drive D-Sub,39,White,,TP2
```

Group names are arbitrary strings — `TP1`, `ENC_A`, `CAN`, etc. Wires without a `Pair` value are unaffected. The symbol is a passive visual indicator only; it does not change click-to-highlight behaviour.

---

## Layout rules

Understanding these helps you structure your CSV for the clearest diagram.

**Left side — top to bottom:**
Connectors appear in the order they first appear in the CSV. Within each
connector, pins are sorted ascending by pin number.

**Right side — top to bottom:**
Panels are ordered by the lowest left-side pin number that feeds them. This
means panels receiving wires from early pins sit at the top, keeping wires
short and reducing crossings. Within each pinned connector, rows are sorted
ascending by left-side pin number (not right-side pin number) for the same
reason.

**Practical tip:** Write your CSV rows in left-side pin order, with each
free-end group's rows together. The layout engine will handle the right-side
ordering automatically.

---

## Termination symbols

For free-end termination groups, a small symbol is drawn at the wire endpoint
based on keywords in the `Right Connector` name:

| Name contains | Symbol drawn |
|---|---|
| `bootlace` or `ferrule` | Rounded rectangle (ferrule body) with a tail |
| `3/16` or `small spade` | Pentagonal spade |
| `1/4` or `large spade` | Pentagonal spade with a coloured sleeving band. Signals named `L`, `N`, or `E` get brown/blue/green sleeving respectively. |
| `bare` or `strip` | Blunt line (stripped conductor) |
| Anything else | Small circle (generic) |

---

## Interactivity

Click any wire, left-side row, or right-side row to highlight that wire's
complete route. All other wires fade out. The info bar at the bottom shows the
signal name, connector pins, wire colour, and termination type.

Click the highlighted wire or row again, or press **Esc**, to clear the
selection.

The **Download SVG** button saves a static image. The **Download HTML** button
saves a copy of the interactive diagram.

---

## Full example

See [`examples/drive_tray.csv`](examples/drive_tray.csv) — the Vigo2 drive tray
harness: one 33-pin left connector, a 44-way D-Sub and four free-end termination
groups on the right, including a warning box for the AC mains wires.
