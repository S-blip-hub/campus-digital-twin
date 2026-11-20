"""SQLite export of simulation tables and the analysis queries in sql/queries.sql."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "queries.sql"


def write_db(tables: Dict[str, pd.DataFrame], path: str | Path = ":memory:") -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).unlink(missing_ok=True)
    con = sqlite3.connect(str(path))
    for name, df in tables.items():
        df.to_sql(name, con, index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_road ON road_usage(segment, day, hour)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_occ ON occupancy(place, day, step)")
    con.commit()
    return con


def load_queries(path: Path = SQL_FILE) -> Dict[str, str]:
    queries, name, buf = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf).strip()
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf).strip()
    return queries


def run_queries(con: sqlite3.Connection) -> Dict[str, pd.DataFrame]:
    return {n: pd.read_sql_query(q, con) for n, q in load_queries().items()}
