"""Apply immutable SQL migrations once, serialized by a PostgreSQL advisory lock."""
import hashlib
from pathlib import Path

from app.database import database


def migrate():
    if database is None:
        raise RuntimeError("Configura DATABASE_URL.")
    with database.connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(72311926)")
        connection.execute("""CREATE TABLE IF NOT EXISTS public.schema_migrations
                            (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())""")
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            content = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            prior = connection.execute("SELECT checksum FROM public.schema_migrations WHERE name=%s", (path.name,)).fetchone()
            if prior:
                if prior["checksum"] != checksum:
                    raise RuntimeError("La migración ya aplicada fue modificada: " + path.name)
                continue
            connection.execute(content, prepare=False)
            connection.execute("INSERT INTO public.schema_migrations(name,checksum) VALUES(%s,%s)", (path.name, checksum))


if __name__ == "__main__":
    migrate()
