import os
import sys
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Добавляем корень проекта в пути
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import Base, get_db
from backend.app.models import Goal, Task
from backend.app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def e2e_stack():
    custom_url = os.getenv("E2E_BASE_URL")
    in_container = os.getenv("CHROME_BIN")

    if not custom_url and not in_container:
        command = [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.e2e.yml",
            "up",
            "-d",
            "--build",
            "backend-e2e",
            "frontend-e2e",
        ]
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                "Could not start the isolated E2E stack:\n"
                f"{result.stdout}\n{result.stderr}"
            )

    base_url = custom_url or (
        "http://frontend-e2e"
        if in_container
        else f"http://localhost:{os.getenv('E2E_FRONTEND_PORT', '8081')}"
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            with urlopen(base_url, timeout=2):
                break
        except (OSError, URLError) as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"E2E frontend did not become available at {base_url}"
                ) from error
            time.sleep(1)


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
