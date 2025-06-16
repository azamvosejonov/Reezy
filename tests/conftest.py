import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI

from main import app

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import User, Post, Comment, Like
from database import Base, get_db, SQLALCHEMY_DATABASE_URL
from api.v1.endpoints import users as users_router

# Create a test app that includes only the necessary routers
def create_test_app():
    app = FastAPI()
    app.include_router(users_router.router, prefix="/api/v1")
    
    # Add a health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "message": "Service is running"}
        
    return app

test_app = create_test_app()

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Set up the database connection
@test_app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)

@test_app.on_event("shutdown")
async def shutdown():
    Base.metadata.drop_all(bind=engine)

# Fixtures
@pytest.fixture(scope="function")
def test_db():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create a new connection and transaction
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Start a nested transaction
    nested = connection.begin_nested()

    # If the application code calls session.commit, it will end the nested
    # transaction. We need to start a new one when that happens.
    @event.listens_for(session, 'after_transaction_end')
    def restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()
    
    try:
        yield session
    finally:
        # Clean up
        session.close()
        transaction.rollback()
        connection.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client that uses the test database."""
    # Override the get_db dependency to use our test database session
    def override_get_db():
        try:
            yield test_db
        finally:
            # Don't close the session here, as it's managed by the test_db fixture
            pass
    
    # Apply the override
    test_app.dependency_overrides[get_db] = override_get_db
    
    # Create and yield the test client
    with TestClient(test_app) as client:
        try:
            yield client
        finally:
            # Ensure any pending transactions are rolled back
            test_db.rollback()
    
    # Clear overrides after the test
    test_app.dependency_overrides.clear()

# Model factories
@pytest.fixture
def create_user(test_db):
    """Factory to create a test user."""
    def _create_user(**kwargs):
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": "hashed_password",
            "full_name": "Test User",
            "is_active": True,
            "is_admin": False
        }
        user_data.update(kwargs)
        
        user = User(**user_data)
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user
    return _create_user

@pytest.fixture
def create_post(test_db, create_user):
    """Factory to create a test post."""
    def _create_post(**kwargs):
        if 'author_id' not in kwargs:
            user = create_user()
            kwargs['author_id'] = user.id
            
        post_data = {
            "title": "Test Post",
            "content": "This is a test post",
            "is_published": True,
            **kwargs
        }
        
        post = Post(**post_data)
        test_db.add(post)
        test_db.commit()
        test_db.refresh(post)
        return post
    return _create_post

@pytest.fixture
def create_comment(test_db, create_user, create_post):
    """Factory to create a test comment."""
    def _create_comment(**kwargs):
        if 'post_id' not in kwargs:
            post = create_post()
            kwargs['post_id'] = post.id
            
        if 'author_id' not in kwargs:
            user = create_user()
            kwargs['author_id'] = user.id
            
        comment_data = {
            "content": "Test comment",
            **kwargs
        }
        
        comment = Comment(**comment_data)
        test_db.add(comment)
        test_db.commit()
        test_db.refresh(comment)
        return comment
    return _create_comment

# Authentication helpers
@pytest.fixture
def auth_client(client, create_user):
    """Return an authenticated test client."""
    user = create_user()
    
    # Get token
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": "testpass"}
    )
    token = response.json()["access_token"]
    
    # Set auth header
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
