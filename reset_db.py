import os
from alembic import command
from alembic.config import Config
from database import Base, engine
import app.models  # This ensures all models are loaded

def reset_database():
    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    # Remove existing migrations
    print("Cleaning up migrations...")
    if os.path.exists("migrations/versions"):
        for file in os.listdir("migrations/versions"):
            if file.endswith(".py") and file != "__init__.py":
                os.remove(os.path.join("migrations/versions", file))
    
    # Initialize new migration
    print("Creating new migration...")
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message="Initial migration")
    
    # Apply migrations
    print("Applying migrations...")
    command.upgrade(alembic_cfg, "head")
    
    print("Database reset and migrations applied successfully!")

if __name__ == "__main__":
    reset_database()
