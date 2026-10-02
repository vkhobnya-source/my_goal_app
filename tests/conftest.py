import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Добавляем корень проекта в пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import Base, get_db
from backend.app.models import Goal, Task
from backend.app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite://",
)
engine_options = {}
if TEST_DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if TEST_DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        engine_options["poolclass"] = StaticPool
engine = create_engine(TEST_DATABASE_URL, **engine_options)
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
        engine.dispose()


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
    # Используем контекстный менеджер для очистки после выполнения теста
    with TestClient(app) as test_client:
        yield test_client

    # Чистим переопределения после каждого теста
    app.dependency_overrides.clear()
