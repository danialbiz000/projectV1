"""Illustrative floor plan generation (M7).

No source in this platform has a real floor plan for any listing — only
aggregate figures (total size, room count, bathroom count). This module
turns those aggregates into a schematic room layout: a deterministic
"slice-and-dice" rectangle partition (the simplest treemap variant) sized
proportionally to each room's assumed share of the total area. It is
explicitly illustrative, not a reconstruction of the real property — the
frontend is required to show a permanent disclaimer alongside it (see
listings/[id]/page.tsx), the same "never present an estimate as certain"
principle used for valuations and forecasts elsewhere in the platform.

The layout is a pure function of (rooms, bathrooms, size_sqm,
property_type): same inputs always produce the same rectangles, no random
seed needed, since room order is fixed rather than shuffled.
"""
from __future__ import annotations

from typing import Any

CANVAS_WIDTH = 400.0
CANVAS_HEIGHT = 300.0

LIVING_ROOM_SHARE = 0.28
KITCHEN_SHARE = 0.14
BATHROOM_SHARE = 0.07
STUDIO_MAIN_SHARE = 0.75
STUDIO_BATHROOM_SHARE = 0.25


def _room_shares(rooms: int, bathrooms: int, property_type: str) -> list[tuple[str, float]]:
    """Ordered (label, share-of-total-area) pairs, shares summing to 1.0.
    Order is fixed (not sorted by size) so the same inputs always tile the
    canvas the same way and the plan reads left-to-right like a real one:
    living areas first, then bedrooms, then bathrooms."""
    bathrooms = max(bathrooms, 1)

    if property_type == "studio":
        bath_share = STUDIO_BATHROOM_SHARE / bathrooms
        return [("Soggiorno + Cucina", STUDIO_MAIN_SHARE)] + [
            (f"Bagno {i + 1}" if bathrooms > 1 else "Bagno", bath_share) for i in range(bathrooms)
        ]

    bedrooms = max(rooms - 1, 1)
    fixed_share = LIVING_ROOM_SHARE + KITCHEN_SHARE + BATHROOM_SHARE * bathrooms
    # If a very small unit has too many nominal rooms, the fixed shares
    # alone could crowd out the bedrooms — floor the leftover so every
    # bedroom still gets a positive area, then rescale the whole set back
    # to sum to 1.0 (the floor can push the raw total above or below 1).
    remaining = max(1.0 - fixed_share, 0.05 * bedrooms)
    bedroom_share = remaining / bedrooms
    scale = 1.0 / (fixed_share + remaining)

    rooms_list: list[tuple[str, float]] = [
        ("Soggiorno", LIVING_ROOM_SHARE),
        ("Cucina", KITCHEN_SHARE),
    ]
    rooms_list += [
        (f"Camera {i + 1}" if bedrooms > 1 else "Camera", bedroom_share) for i in range(bedrooms)
    ]
    rooms_list += [
        (f"Bagno {i + 1}" if bathrooms > 1 else "Bagno", BATHROOM_SHARE) for i in range(bathrooms)
    ]
    return [(label, share * scale) for label, share in rooms_list]


def _slice_layout(
    rooms: list[tuple[str, float]], x: float, y: float, w: float, h: float, horizontal: bool
) -> list[dict[str, Any]]:
    if len(rooms) == 1:
        label, share = rooms[0]
        return [{"label": label, "x": x, "y": y, "width": w, "height": h, "share": share}]

    total = sum(share for _, share in rooms)
    mid = len(rooms) // 2
    left, right = rooms[:mid], rooms[mid:]
    left_fraction = (sum(share for _, share in left) / total) if total else 0.5

    if horizontal:
        split = w * left_fraction
        return _slice_layout(left, x, y, split, h, False) + _slice_layout(
            right, x + split, y, w - split, h, False
        )
    split = h * left_fraction
    return _slice_layout(left, x, y, w, split, True) + _slice_layout(
        right, x, y + split, w, h - split, True
    )


def generate_floorplan(
    rooms: int, bathrooms: int, size_sqm: float, property_type: str
) -> dict[str, Any]:
    shares = _room_shares(rooms, bathrooms, property_type)
    boxes = _slice_layout(shares, 0.0, 0.0, CANVAS_WIDTH, CANVAS_HEIGHT, horizontal=True)
    return {
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT,
        "rooms": [
            {
                "label": box["label"],
                "x": round(box["x"], 1),
                "y": round(box["y"], 1),
                "width": round(box["width"], 1),
                "height": round(box["height"], 1),
                "area_sqm": round(box["share"] * size_sqm, 1),
            }
            for box in boxes
        ],
    }
