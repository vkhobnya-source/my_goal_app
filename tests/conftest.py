import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем корень проекта в пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import Base, get_db
from backend.app.models import Goal, Task, User
from backend.app.main import app, hash_password

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/goals_test",
)
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Создаем таблицы в изолированной базе данных
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    # Надежное переопределение зависимости для FastAPI
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    test_password = "test"
    test_salt = b"test-user-salt!"
    db_session.add(
        User(
            email="test@test.ts",
            password_salt=test_salt.hex(),
            password_hash=hash_password(test_password, test_salt),
        )
    )
    db_session.commit()

    # Используем контекстный менеджер для очистки после выполнения теста
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/register",
            json={"email": "test-user@example.com", "password": "test-password-123"},
        )
        assert response.status_code == 201
        yield test_client

    # Чистим переопределения после каждого теста
    app.dependency_overrides.clear()
