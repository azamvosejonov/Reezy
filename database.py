from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker, scoped_session, configure_mappers
import os
import sys
from typing import Any, Dict, Type

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

# Use scoped_session for thread-local sessions
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

# Base model with common functionality
class BaseModel:
    """Base model with common functionality."""
    
    @declared_attr
    def __tablename__(cls) -> str:
        return ''.join(['_'+i.lower() if i.isupper() else i for i in cls.__name__]).lstrip('_')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns  # type: ignore
        }

# Create declarative base with our custom BaseModel
Base = declarative_base(cls=BaseModel)

def init_models():
    """Initialize all models and configure mappers."""
    # Import all models here to ensure they are registered with SQLAlchemy
    # The imports are only needed to make sure the models are loaded
    import models  # This will import all models through __init__.py
    
    # Explicitly import models with relationships
    from models import user, post, blocked_post, social_account
    
    # Try to import optional modules
    try:
        # Import calls models from the root level package
        import calls.models  # noqa: F401
        print("Successfully imported calls models")
    except ImportError as e:
        print(f"Note: calls module not found, skipping... Error: {e}")

    # Configure mappers after all models are loaded
    try:
        configure_mappers()
    except Exception as e:
        print(f"Error configuring mappers: {e}")
        import traceback
        traceback.print_exc()
        raise


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
