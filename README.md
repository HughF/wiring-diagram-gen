# Wiring Diagram Generator

Generates interactive, self-contained HTML wiring harness diagrams from a CSV file.

The output is a single `.html` file containing an SVG diagram with click-to-highlight interactivity, a cut list (if wire lengths are provided), and download buttons for both SVG and HTML. No internet connection is required to view it.

---

## Requirements

Python 3.10 or later. No third-party packages.

---

## Quick start

```bash
python wiring_diagram.py examples/drive_tray.csv
```

This writes `examples/drive_tray.html`. Open it in any browser.

---

## Command-line options

```
python wiring_diagram.py <input.csv> [options]

  input.csv             CSV file describing the harness (required)

  -o, --output FILE     Where to write the HTML (default: same path as CSV, .html extension)
  --title TEXT          Title shown in the diagram header (default: CSV filename without extension)
  --width PX            SVG canvas width in pixels (default: 1380)
  --lang LANG           Default display language: en or zh (default: en)
                        The viewer can switch language at runtime using the button in the output.
```

Examples:

```bash
# Write to a specific location
python wiring_diagram.py my_harness.csv -o ~/Documents/my_harness.html

# Override the title
python wiring_diagram.py my_harness.csv --title "Main Control Box — Wiring Harness Rev 3"

# Wider canvas for a harness with many wires
python wiring_diagram.py my_harness.csv --width 1600

# Generate with Chinese as the default language
python wiring_diagram.py my_harness.csv --lang zh
```

---

## CSV format

### Header row

The first non-blank, non-comment row is the header. Column names are matched
**case-insensitively** and **in any order**, so you can use whatever names feel
natural in your spreadsheet. The accepted aliases for each field are listed below.

| Field | Accepted column names | Required |
|---|---|---|
| Signal name | `Signal`, `Signal Name`, `Name`, `Wire`, `Wire Name` | Yes |
| Left connector | `Left Connector`, `Left Conn`, `From Connector`, `From`, `Source Connector`, `Source` | Yes |
| Left pin | `Left Pin`, `From Pin`, `Source Pin`, `Pin (Left)`, `Left Pin No` | Yes |
| Right connector | `Right Connector`, `Right Conn`, `To Connector`, `To`, `Dest Connector`, `Destination Connector`, `Destination`, `Termination`, `Termination Type` | Yes |
| Right pin | `Right Pin`, `To Pin`, `Dest Pin`, `Destination Pin`, `Pin (Right)`, `Right Pin No` | Yes |
| Wire colour | `Wire Colour`, `Wire Color`, `Colour`, `Color`, `Wire Col` | Yes |
| Warning | `Warning`, `Note`, `Notes`, `Annotation`, `Remark` | No |
| Twisted pair group | `Pair`, `Twisted Pair`, `TP`, `Pair Group` | No |
| Cable / multicore group | `Cable`, `Cable Group`, `Cable Name`, `Sheath`, `Multicore`, `Cable Ref` | No |
| Wire length | `Length`, `Wire Length`, `Len` | No |

### Wire rows

Each row describes one wire. Blank rows and rows beginning with `#` are ignored
(use them as section separators or comments).

```csv
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

```csv
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

Write the colour name in plain English or as a hex value. Colour names are case-insensitive.

**Solid colours:**

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
| `#RRGGBB` | Any hex colour, passed through directly |

Unknown names render as medium grey.

**Bicolour wires (green & yellow — earth / PE):**

The IEC standard earth/protective-earth wire is rendered with alternating green and
yellow dashes. Any of the following names produce the same result:

| Name |
|---|
| `green/yellow` |
| `green-yellow` |
| `green & yellow` |
| `green and yellow` |
| `earth` |
| `pe` |
| `g/y` |
| `g-y` |

Bicolour wires are drawn as two overlapping dashed paths (green and yellow alternating).
Endpoint dots use a yellow fill with a green stroke. In the cut list, the colour swatch
shows a diagonal split of both colours.

### Warning boxes

If a wire has text in the `Warning` column, a dashed warning box is rendered
inside the right-side termination section that wire connects to. Multiple wires
in the same section can share the same warning text — identical texts are
de-duplicated into one box. Different warning texts each get their own box.

```csv
L,Main PCB,1,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
N,Main PCB,2,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
E,Main PCB,3,AC Mains,,Black,Wires L/N/E are BLACK. Add 20mm sleeving.
```

The three identical warnings above produce one box in the "AC Mains" section.

Warning boxes only appear on right-side panels. Text longer than ~46 characters
is word-wrapped automatically (up to 3 lines).

### Twisted pair groups

Assign a group name in the `Pair` column to mark wires that run as a twisted pair.
Any two wires sharing the same group name are drawn with a visible wire-crossing
effect in the middle of the span — the two wire paths physically cross and interweave,
with the correct over/under ordering at each crossing point.

```csv
Step+,Main PCB,9,Drive D-Sub,42,Purple,,TP1
Step-,Main PCB,10,Drive D-Sub,41,Red,,TP1
Dir+,Main PCB,11,Drive D-Sub,40,Green,,TP2
Dir-,Main PCB,12,Drive D-Sub,39,White,,TP2
```

Group names are arbitrary strings — `TP1`, `ENC_A`, `CAN`, etc. Wires without a
`Pair` value are unaffected. The crossing visual has no effect on click-to-highlight
behaviour — clicking either wire in a pair highlights it as normal.

Only pairs of exactly 2 wires receive the crossing effect. Groups of 3 or more
wires with the same `Pair` value are drawn as straight Bézier curves.

### Cable / multicore groups

Assign a cable name in the `Cable` column to mark wires that run inside the same
multicore cable or sheath. All wires sharing the same cable name are enclosed in a
shaded band that spans the full wire area, with the cable name shown above it as a
label. Each cable group gets a distinct colour from a rotating palette.

```csv
Signal,Left Connector,Left Pin,Right Connector,Right Pin,Wire Colour,Warning,Pair,Cable
Step+,Main PCB,9,Drive D-Sub,42,Purple,,,Encoder Cable
Step-,Main PCB,10,Drive D-Sub,41,Red,,,Encoder Cable
Dir+,Main PCB,11,Drive D-Sub,40,Green,,,Encoder Cable
24V,Main PCB,15,Terminal Block,1,Red,,,Power Flex
GND,Main PCB,16,Terminal Block,2,Black,,,Power Flex
```

Cable bands are drawn behind the wires and do not affect interactivity.

### Wire lengths and cut list

Add a `Length` column to record the cut length of each wire. Lengths can include
a unit suffix (`mm`, `cm`, `m`, `ft`). Wires without a length are shown as `—` in
the cut list.

```csv
Signal,Left Connector,Left Pin,Right Connector,Right Pin,Wire Colour,Length
Step+,Main PCB,9,Drive D-Sub,42,Purple,350mm
GND,Main PCB,30,GND Rail,,White,280mm
```

If **any** wire in the CSV has a length value, a **Cut list** table is automatically
appended below the diagram in the HTML output. The cut list shows every wire with its
signal name, from/to connectors, pin numbers, colour, and length. It also shows totals
per colour and unit at the foot of the table.

When cable groups are present, the cut list is sorted by cable group first, with a
group header row for each cable. Ungrouped wires appear at the end.

Length values with non-numeric content (e.g. `"TBD"`, `"~300mm"`) are listed in the
table but excluded from the totals, with a footnote indicating this.

### Notes section

Place a `Notes` label in the first column of any row, then put the note text in the
row immediately below it:

```csv
Signal,Left Connector,Left Pin,Right Connector,Right Pin,Wire Colour
Step+,Main PCB,9,Drive D-Sub,42,Purple
...
Notes
All wires are 0.5mm² PTFE insulated. Twisted pairs at ≥1 turn per 25mm.
```

The text is rendered in a styled panel below the diagram in the HTML output. Multiple
`Notes` blocks are supported — each produces a separate paragraph. Blank rows between
the label and the text are ignored.

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
| `3/16` or `small spade` | Pentagonal spade terminal |
| `1/4` or `large spade` | Pentagonal spade with a coloured heat-shrink sleeving band. Signals named `L`, `N`, or `E` get brown/blue/green sleeving respectively. |
| `bare` or `strip` | Blunt line (stripped conductor) |
| Anything else | Small circle (generic) |

---

## Interactivity

Click any wire, left-side row, or right-side row to highlight that wire's
complete route. All other wires fade out. The info bar at the bottom shows the
signal name, connector pins, wire colour, termination type, and length (if set).

Click the highlighted wire or row again, or press **Esc**, to clear the selection.

A **language toggle button** in the controls bar switches the diagram between
English and Chinese. The chosen language is remembered across browser sessions
(stored in `localStorage`). The default language can be set at generation time
with the `--lang` option.

The **Download SVG** button saves a static image. The **Download HTML** button
saves a copy of the interactive diagram.

---

## Full example

See [`examples/drive_tray.csv`](examples/drive_tray.csv) — the Vigo2 drive tray
harness: one 33-pin left connector, a 44-way D-Sub and four free-end termination
groups on the right, with cable groups for the encoder cable and mains flex, and a
warning box for the AC mains wires.
