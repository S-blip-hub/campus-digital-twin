"""Six spatial layers of a schematic residential campus, stored as GeoJSON.

Layers: roads, residential halls, academic buildings, amenities (dining,
library, market, health), sports and open spaces, and gates. Coordinates are in
metres on a local grid. The layout follows the structure of a large Indian
residential campus (halls on the periphery, an academic core, amenities in
between) but is schematic, not surveyed data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx

LAYER_NAMES = ("roads", "halls", "academic", "amenities", "sports_open", "gates")

# name -> (x, y, capacity)
HALLS = {
    "Hall 1": (200, 1650, 650), "Hall 2": (500, 1700, 700), "Hall 3": (850, 1720, 600),
    "Hall 4": (1250, 1700, 750), "Hall 5": (1650, 1650, 650), "Hall 6": (1900, 1300, 550),
    "Hall 7": (1900, 900, 600), "Hall 8": (150, 1100, 500),
}
ACADEMIC = {
    "Main Building": (1000, 900, 2500), "Academic Block A": (750, 1000, 2000),
    "Academic Block B": (1250, 1000, 2000), "Academic Block C": (800, 650, 2000),
    "Academic Block D": (1250, 650, 2000), "Central Library": (1000, 1180, 1200),
}
AMENITIES = {
    "Dining Centre": (650, 1350, 600), "Market": (1400, 1350, 800), "Health Centre": (450, 900, 120),
}
SPORTS_OPEN = {"Sports Complex": (500, 450, 1200), "Central Lawn": (1000, 450, 1500)}
GATES = {"Main Gate": (1000, 100, 0), "North Gate": (1000, 1950, 0)}

# Road junctions (x, y) and road segments between junctions or buildings.
JUNCTIONS = {
    "J1": (300, 1450), "J2": (650, 1500), "J3": (1000, 1500), "J4": (1400, 1500), "J5": (1750, 1450),
    "J6": (650, 1150), "J7": (1000, 1050), "J8": (1400, 1150), "J9": (650, 800), "J10": (1000, 800),
    "J11": (1400, 800), "J12": (1000, 300), "J13": (1750, 1050),
}
ROADS: List[Tuple[str, str]] = [
    ("J1", "J2"), ("J2", "J3"), ("J3", "J4"), ("J4", "J5"), ("J2", "J6"), ("J3", "J7"), ("J4", "J8"),
    ("J6", "J7"), ("J7", "J8"), ("J6", "J9"), ("J7", "J10"), ("J8", "J11"), ("J9", "J10"), ("J10", "J11"),
    ("J10", "J12"), ("J5", "J13"), ("J13", "J8"), ("J13", "J11"), ("J1", "J6"), ("J9", "J12"), ("J11", "J12"),
    # building access spurs
    ("Hall 1", "J1"), ("Hall 2", "J2"), ("Hall 3", "J3"), ("Hall 4", "J4"), ("Hall 5", "J5"), ("Hall 6", "J13"),
    ("Hall 7", "J13"), ("Hall 8", "J1"), ("Main Building", "J10"), ("Academic Block A", "J6"),
    ("Academic Block B", "J8"), ("Academic Block C", "J9"), ("Academic Block D", "J11"), ("Central Library", "J7"),
    ("Dining Centre", "J2"), ("Market", "J4"), ("Health Centre", "J9"), ("Sports Complex", "J9"),
    ("Central Lawn", "J12"), ("Main Gate", "J12"), ("North Gate", "J3"),
]

KIND = {**{k: "hall" for k in HALLS}, **{k: "academic" for k in ACADEMIC}, **{k: "amenity" for k in AMENITIES},
        **{k: "sports_open" for k in SPORTS_OPEN}, **{k: "gate" for k in GATES}}


def _points(items: Dict[str, Tuple[float, float, int]], kind: str) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
         "properties": {"name": n, "kind": kind, "capacity": c}} for n, (x, y, c) in items.items()]}


def places_table() -> List[dict]:
    """One record per building or open space: name, kind, position and capacity."""
    rows = []
    for d, kind in ((HALLS, "hall"), (ACADEMIC, "academic"), (AMENITIES, "amenity"),
                    (SPORTS_OPEN, "sports_open"), (GATES, "gate")):
        rows += [{"place": n, "kind": kind, "x": x, "y": y, "capacity": c} for n, (x, y, c) in d.items()]
    return rows


def coordinates() -> Dict[str, Tuple[float, float]]:
    pts = {n: (x, y) for d in (HALLS, ACADEMIC, AMENITIES, SPORTS_OPEN, GATES) for n, (x, y, _) in d.items()}
    pts.update(JUNCTIONS)
    return pts


def build_layers() -> Dict[str, dict]:
    xy = coordinates()
    roads = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(xy[a]), list(xy[b])]},
         "properties": {"id": f"{a}--{b}", "from": a, "to": b}} for a, b in ROADS]}
    return {"roads": roads, "halls": _points(HALLS, "hall"), "academic": _points(ACADEMIC, "academic"),
            "amenities": _points(AMENITIES, "amenity"), "sports_open": _points(SPORTS_OPEN, "sports_open"),
            "gates": _points(GATES, "gate")}


def write_layers(folder: str | Path) -> List[Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fc in build_layers().items():
        p = folder / f"{name}.geojson"
        p.write_text(json.dumps(fc, indent=1))
        paths.append(p)
    return paths


def load_network(folder: str | Path | None = None) -> nx.Graph:
    """Build the walkable road graph from the layers (from disk if a folder is given)."""
    layers = build_layers() if folder is None else {
        n: json.loads((Path(folder) / f"{n}.geojson").read_text()) for n in LAYER_NAMES}
    g = nx.Graph()
    for name in LAYER_NAMES[1:]:
        for f in layers[name]["features"]:
            x, y = f["geometry"]["coordinates"]
            g.add_node(f["properties"]["name"], pos=(x, y), kind=f["properties"]["kind"],
                       capacity=f["properties"]["capacity"])
    for f in layers["roads"]["features"]:
        (x1, y1), (x2, y2) = f["geometry"]["coordinates"]
        a, b = f["properties"]["from"], f["properties"]["to"]
        for n, xy in ((a, (x1, y1)), (b, (x2, y2))):
            if n not in g:
                g.add_node(n, pos=xy, kind="junction", capacity=0)
        g.add_edge(a, b, length=((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5, id=f["properties"]["id"])
    return g
