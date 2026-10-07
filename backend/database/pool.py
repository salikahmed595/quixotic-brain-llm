"""PostgreSQL + pgvector connection pool (PRD §45) and a minimal migration runner."""
from __future__ import annotations

from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def migrate(database_url: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply migrations/*.sql in filename order, once each. Returns the names applied now."""
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, at timestamptz DEFAULT now())")
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(directory.glob("*.sql")):
            if f.name in done:
                continue
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
            applied.append(f.name)
    return applied


def _configure(conn) -> None:
    register_vector(conn)
    # MEASURED DEFECT (RAG audit): with the default HNSW scan, the index returns its global top-40 and the department filter
    # (PRD §42) is applied afterwards, so a user in a small department got ZERO results whenever a bigger department held
    # near-duplicate content. Iterative scan keeps scanning until enough rows pass the filter (pgvector >= 0.8).
    try:
        conn.execute("SET hnsw.iterative_scan = relaxed_order")
    except Exception:             # older pgvector: the setting does not exist (docs/PRD_GAPS.md)
        conn.rollback()
    conn.commit()


def make_pool(database_url: str) -> ConnectionPool:
    """Call after `migrate` (the pgvector adapter needs the extension to exist)."""
    return ConnectionPool(database_url, kwargs={"row_factory": dict_row}, configure=_configure, open=True)


if __name__ == "__main__":      # python -m backend.database.pool
    from ..config import get_settings
    print("applied:", migrate(get_settings().database_url) or "nothing to do")
