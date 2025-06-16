# auto_migrate.py

from alembic import command
from alembic.config import Config

def auto_migrate(message: str = "auto migration"):
    """
    Alembic yordamida avtomatik migratsiya yaratish va uni qo'llash.
    """
    alembic_cfg = Config("alembic.ini")
    # Avval barcha mavjud migratsiyalarni qo'llash
    command.upgrade(alembic_cfg, "head")
    # Yangi migratsiya yaratish
    command.revision(alembic_cfg, message=message, autogenerate=True)
    # Yangi migratsiyani qo'llash
    command.upgrade(alembic_cfg, "head")

if __name__ == "__main__":
    auto_migrate()