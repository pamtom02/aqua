import logging

from app.config import settings
from app.postgres import PostgresClient

logger = logging.getLogger(__name__)


def get_database_client():
    dsn = settings.database_url.get_secret_value()
    return PostgresClient(dsn, settings.storage_root) if dsn else None


database = get_database_client()


def check_database_connection():
    if database is None:
        return {"status": "error", "detail": "Conexión PostgreSQL sin configurar."}
    try:
        with database.connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "engine": "postgresql"}
    except Exception:
        logger.warning("PostgreSQL no disponible.")
        return {"status": "error", "detail": "PostgreSQL no disponible."}
