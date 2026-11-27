"""Container startup: wait for PostgreSQL, migrate, optionally bootstrap one admin."""
import logging
import time

from app.config import settings
from app.database import database
from app.migrate import migrate

logger = logging.getLogger(__name__)


def prepare():
    if database is None:
        raise RuntimeError("Falta DATABASE_URL.")
    if len(settings.jwt_secret.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET necesita al menos 32 caracteres aleatorios.")
    if settings.environment == "production" and (
        settings.internal_service_token is None or len(settings.internal_service_token.get_secret_value()) < 32
    ):
        raise RuntimeError("INTERNAL_SERVICE_TOKEN necesita al menos 32 caracteres aleatorios.")
    for attempt in range(30):
        try:
            with database.connection() as connection:
                connection.execute("SELECT 1")
            break
        except Exception:
            if attempt == 29:
                raise RuntimeError("PostgreSQL no respondió durante el arranque.") from None
            logger.info("Esperando PostgreSQL (%s/30).", attempt + 1)
            time.sleep(2)
    migrate()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        from app.auth import create_user
        with database.connection() as connection:
            present = connection.execute("SELECT id FROM public.users WHERE email=%s",
                                         (settings.bootstrap_admin_email.strip().lower(),)).fetchone()
        if present is None:
            create_user(settings.bootstrap_admin_email, settings.bootstrap_admin_password.get_secret_value(),
                        "Administrador AquaBloom", "administrador")


if __name__ == "__main__":
    prepare()
