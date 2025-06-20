import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends, HTTPException, status

from main import app
from database import Base, get_db
from config import settings
from models.user import User
from models.ai_usage import AIUsage
from datetime import datetime, timedelta

# Override the get_db dependency for testing
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create a test database engine and session
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_reezy"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def test_db():
    # Drop all tables first to ensure a clean state
    Base.metadata.drop_all(bind=engine)
    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield
    # Clean up after all tests
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(test_db):
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # Begin a nested transaction
    nested = connection.begin_nested()
    
    @event.listens_for(session, 'after_transaction_end')
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()
    
    yield session
    
    # Clean up
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client():
    return TestClient(app)

@pytest.fixture(scope="function")
def test_user(db_session):
    # Clean up any existing test user
    db_session.query(User).filter(User.email == TEST_USER_EMAIL).delete()
    db_session.commit()
    
    # Create a test user with hashed password
    hashed_password = get_password_hash(TEST_USER_PASSWORD)
    user = User(
        email=TEST_USER_EMAIL,
        username=TEST_USER_USERNAME,
        hashed_password=hashed_password,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user



@pytest.fixture(scope="function")
def test_ai_usage(db_session, test_user):
    # Delete any existing AI usage for this user
    db_session.query(AIUsage).filter(AIUsage.user_id == test_user.id).delete()
    
    # Create new AI usage
    ai_usage = AIUsage(
        user_id=test_user.id,
        is_premium=False,
        premium_expires_at=None,
        daily_limit=10,
        current_month_limit=0,
        last_reset_date=datetime.utcnow().date(),
        premium_verification_email=None,
        is_premium_verified=False
    )
    db_session.add(ai_usage)
    db_session.commit()
    db_session.refresh(ai_usage)
    return ai_usage

def test_ai_moderate(client):
    # Test with normal content
    response = client.post(
        "/ai/moderate",
        json={"text": "Test content"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_appropriate"] is True
    assert data["score"] > 0
    
    # Test with inappropriate content
    response = client.post(
        "/ai/moderate",
        json={"text": "This is a badword1 content"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_appropriate"] is False
    assert "badword1" in str(data.get("found_terms", []))
    
    # Test with empty content
    response = client.post(
        "/ai/moderate",
        json={"text": ""}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_appropriate"] is False
    assert "Empty or invalid text" in data.get("reason", "")

def test_subscribe(client):
    response = client.post(
        "/ai/subscribe",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_premium"] is True
    assert data["daily_limit"] == 1000
    assert data["remaining_uses"] == 1000
    assert data["premium_expires_at"] is not None

def test_verify_subscription(client):
    response = client.post("/ai/verify")
    assert response.status_code == 200
    data = response.json()
    assert data["is_premium"] is False
    assert data["daily_limit"] == 10
    assert data["remaining_uses"] == 10
    assert data["premium_expires_at"] is None

def test_subscription_status(client):
    # Test default status
    response = client.get("/ai/status")
    assert response.status_code == 200
    data = response.json()
    assert data["is_premium"] is False
    assert data["daily_limit"] == 10
    assert data["remaining_uses"] == 10
    assert data["premium_expires_at"] is None
    
    # Test after subscription (mocked)
    # Since we're not using a real database in these tests,
    # we test the subscription endpoint separately
    response = client.post(
        "/ai/subscribe",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 200
    sub_data = response.json()
    assert sub_data["is_premium"] is True
    assert sub_data["daily_limit"] == 1000
    assert sub_data["remaining_uses"] == 1000
    assert sub_data["premium_expires_at"] is not None
