COLOUR_MAP = {
    "purple":  "#7B1FA2",
    "red":     "#D32F2F",
    "green":   "#388E3C",
    "white":   "#ECEFF1",
    "yellow":  "#FBC02D",
    "blue":    "#1565C0",
    "black":   "#1A1A1A",
    "orange":  "#E65100",
    "brown":   "#5D4037",
    "grey":    "#607D8B",
    "gray":    "#607D8B",
    "pink":    "#E91E63",
    "violet":  "#6A1B9A",
    "cyan":    "#00838F",
    "lime":    "#558B2F",
    "silver":  "#9E9E9E",
}

# Bicolour wires: name aliases → (primary_hex, secondary_hex).
# Primary is used wherever a single colour is required (resolve, is_light checks).
_BICOLOUR: dict[str, tuple[str, str]] = {
    "green/yellow":     ("#388E3C", "#FBC02D"),
    "green-yellow":     ("#388E3C", "#FBC02D"),
    "green & yellow":   ("#388E3C", "#FBC02D"),
    "green and yellow": ("#388E3C", "#FBC02D"),
    "earth":            ("#388E3C", "#FBC02D"),
    "pe":               ("#388E3C", "#FBC02D"),
    "g/y":              ("#388E3C", "#FBC02D"),
    "g-y":              ("#388E3C", "#FBC02D"),
}

# Colours that need a contrasting outline on the diagram background
LIGHT_COLS = {c.upper() for c in ("#ECEFF1", "#FFFFFF", "#F5F5F5", "#FAFAFA", "#E0E0E0")}


def resolve_pair(name: str) -> tuple[str, str] | None:
    """Return (primary_hex, secondary_hex) for a bicolour name, or None for solid colours."""
    return _BICOLOUR.get(name.strip().lower())


def resolve(name: str) -> str:
    """Return a hex colour for a CSS colour name or pass a hex value through."""
    n = name.strip()
    if n.startswith("#"):
        return n
    pair = _BICOLOUR.get(n.lower())
    if pair:
        return pair[0]
    return COLOUR_MAP.get(n.lower(), "#888888")


def is_light(hex_col: str) -> bool:
    return hex_col.upper() in LIGHT_COLS


def colour_name(raw: str) -> str:
    return raw.strip().title() if raw.strip() else "Unknown"
