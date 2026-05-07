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

# Colours that need a contrasting outline on the diagram background
LIGHT_COLS = {c.upper() for c in ("#ECEFF1", "#FFFFFF", "#F5F5F5", "#FAFAFA", "#E0E0E0")}


def resolve(name: str) -> str:
    """Return a hex colour for a CSS colour name or pass a hex value through."""
    n = name.strip()
    if n.startswith("#"):
        return n
    return COLOUR_MAP.get(n.lower(), "#888888")


def is_light(hex_col: str) -> bool:
    return hex_col.upper() in LIGHT_COLS


def colour_name(raw: str) -> str:
    return raw.strip().title() if raw.strip() else "Unknown"
