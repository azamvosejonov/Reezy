"""
Database migration script for advertisements.
This script creates the advertisements table if it doesn't exist.
"""

import logging
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

def create_advertisements_table():
    """Create the advertisements table if it doesn't exist."""
    try:
        # Check if the table already exists
        inspector = inspect(engine)
        if 'advertisements' in inspector.get_table_names():
            logger.info("Advertisements table already exists")
            return
        
        # Create the new advertisements table
        advertisements = Table(
            'advertisements',
            metadata,
            Column('id', Integer, primary_key=True, index=True),
            Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
            Column('admin_id', Integer, ForeignKey('users.id'), nullable=True),
            Column('post_id', Integer, ForeignKey('posts.id'), nullable=False),
            Column('link', String, nullable=False),
            Column('budget', Integer, default=1),  # in dollars
            Column('views_count', Integer, default=0),
            Column('max_views', Integer, default=900),  # 1$ = 900 views by default
            Column('is_approved', Boolean, default=False),
            Column('is_active', Boolean, default=True),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('approved_at', DateTime, nullable=True)
        )
        
        # Create the table
        metadata.create_all(engine)
        logger.info("Successfully created advertisements table")
        
    except SQLAlchemyError as e:
        logger.error(f"Error creating advertisements table: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        from sqlalchemy import inspect
        create_advertisements_table()
    except ImportError as e:
        logger.error(f"Failed to import required module: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        raise
