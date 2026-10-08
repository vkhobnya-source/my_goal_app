import asyncio
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite://"
from backend.app import auth, database, main, models, schemas  # noqa: E402

if _database_url is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = _database_url


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_user(db_session, email):
    user = models.User(
        email=email,
        hashed_password=auth.get_password_hash("secret"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def current_user(db_session):
    return _make_user(db_session, "owner@example.com")


@pytest.fixture
def other_user(db_session):
    return _make_user(db_session, "other@example.com")


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


def urlopen_raising(error):
    def fail(request, timeout):
        raise error

    return fail


def create_goal(db_session, current_user, title="Learn Python", description=None):
    return main.create_goal(
        schemas.GoalCreate(title=title, description=description),
        db_session,
        current_user,
    )


# ==================== DATABASE ====================

def test_get_db_yields_session_and_closes_it(monkeypatch):
    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    fake_session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    generator = database.get_db()
    assert next(generator) is fake_session

    with pytest.raises(StopIteration):
        next(generator)
    assert fake_session.closed is True



# ==================== AUTHENTICATION ====================

def test_register_creates_user_and_returns_token(db_session):
    token = main.register(
        schemas.UserCreate(email="new@example.com", password="secret"),
        db_session,
    )

    assert token["token_type"] == "bearer"
    assert token["access_token"]
    stored = db_session.query(models.User).filter_by(email="new@example.com").first()
    assert stored is not None
    assert auth.verify_password("secret", stored.hashed_password)


def test_register_rejects_duplicate_email(db_session):
    main.register(schemas.UserCreate(email="dup@example.com", password="secret"), db_session)

    with pytest.raises(HTTPException) as error:
        main.register(
            schemas.UserCreate(email="dup@example.com", password="secret"),
            db_session,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Email already registered"


def test_login_returns_token_for_valid_credentials(db_session):
    main.register(schemas.UserCreate(email="login@example.com", password="secret"), db_session)

    token = main.login(
        schemas.UserCreate(email="login@example.com", password="secret"),
        db_session,
    )

    assert token["token_type"] == "bearer"
    assert token["access_token"]


def test_login_rejects_invalid_credentials(db_session):
    main.register(schemas.UserCreate(email="login@example.com", password="secret"), db_session)

    with pytest.raises(HTTPException) as error:
        main.login(
            schemas.UserCreate(email="login@example.com", password="wrong"),
            db_session,
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid credentials"


def test_get_current_user_returns_user_for_valid_token(db_session, current_user):
    token = auth.create_access_token({"sub": current_user.email})

    result = asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert result.id == current_user.id


def test_get_current_user_rejects_invalid_token(db_session):
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth.get_current_user(token="not-a-token", db=db_session))

    assert error.value.status_code == 401


def test_get_current_user_rejects_token_without_subject(db_session):
    token = auth.create_access_token({"foo": "bar"})

    with pytest.raises(HTTPException) as error:
        asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert error.value.status_code == 401


def test_get_current_user_rejects_unknown_user(db_session):
    token = auth.create_access_token({"sub": "ghost@example.com"})

    with pytest.raises(HTTPException) as error:
        asyncio.run(auth.get_current_user(token=token, db=db_session))

    assert error.value.status_code == 401


# ==================== GOALS ====================

def test_create_goal_sets_defaults_and_get_goals_returns_it(db_session, current_user):
    goal = create_goal(db_session, current_user, description="Practice every day")

    assert goal.title == "Learn Python"
    assert goal.description == "Practice every day"
    assert goal.is_completed is False
    assert goal.user_id == current_user.id
    assert main.get_goals(db_session, current_user) == [goal]


def test_get_goals_only_returns_owned_goals(db_session, current_user, other_user):
    create_goal(db_session, current_user, title="Mine")
    create_goal(db_session, other_user, title="Theirs")

    goals = main.get_goals(db_session, current_user)

    assert [goal.title for goal in goals] == ["Mine"]


def test_create_task_requires_an_existing_goal(db_session, current_user):
    with pytest.raises(HTTPException) as error:
        main.create_task(404, schemas.TaskCreate(title="Study"), db_session, current_user)

    assert error.value.status_code == 404
    assert error.value.detail == "Goal not found"


def test_create_task_rejects_goal_owned_by_another_user(db_session, current_user, other_user):
    goal = create_goal(db_session, other_user)

    with pytest.raises(HTTPException) as error:
        main.create_task(
            goal.id,
            schemas.TaskCreate(title="Study"),
            db_session,
            current_user,
        )

    assert error.value.status_code == 404


def test_get_tasks_rejects_foreign_goal(db_session, current_user, other_user):
    goal = create_goal(db_session, other_user)

    with pytest.raises(HTTPException) as error:
        main.get_tasks(goal.id, db_session, current_user)

    assert error.value.status_code == 404


def test_create_task_assigns_goal_and_default_status(db_session, current_user):
    goal = create_goal(db_session, current_user)

    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        current_user,
    )

    assert task.title == "Read a chapter"
    assert task.goal_id == goal.id
    assert task.is_completed is False
    assert main.get_tasks(goal.id, db_session, current_user) == [task]


def test_update_task_status_changes_completion(db_session, current_user):
    goal = create_goal(db_session, current_user)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        current_user,
    )

    updated = main.update_task_status(
        task.id,
        schemas.TaskUpdate(is_completed=True),
        db_session,
        current_user,
    )

    assert updated.is_completed is True


def test_update_missing_task_returns_not_found(db_session, current_user):
    with pytest.raises(HTTPException) as error:
        main.update_task_status(
            404,
            schemas.TaskUpdate(is_completed=True),
            db_session,
            current_user,
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_update_task_status_rejects_foreign_task(db_session, current_user, other_user):
    goal = create_goal(db_session, other_user)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        other_user,
    )

    with pytest.raises(HTTPException) as error:
        main.update_task_status(
            task.id,
            schemas.TaskUpdate(is_completed=True),
            db_session,
            current_user,
        )

    assert error.value.status_code == 403
    assert error.value.detail == "Not authorized"


def test_delete_task_removes_it(db_session, current_user):
    goal = create_goal(db_session, current_user)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        current_user,
    )

    deleted = main.delete_task(task.id, db_session, current_user)

    assert deleted.id == task.id
    assert main.get_tasks(goal.id, db_session, current_user) == []


def test_delete_missing_task_returns_not_found(db_session, current_user):
    with pytest.raises(HTTPException) as error:
        main.delete_task(404, db_session, current_user)

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_delete_task_rejects_foreign_task(db_session, current_user, other_user):
    goal = create_goal(db_session, other_user)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        other_user,
    )

    with pytest.raises(HTTPException) as error:
        main.delete_task(task.id, db_session, current_user)

    assert error.value.status_code == 403
    assert error.value.detail == "Not authorized"


def test_delete_goal_cascades_to_tasks(db_session, current_user):
    goal = create_goal(db_session, current_user)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
        current_user,
    )

    deleted = main.delete_goal(goal.id, db_session, current_user)

    assert deleted.id == goal.id
    assert db_session.get(models.Task, task.id) is None


def test_delete_missing_goal_returns_not_found(db_session, current_user):
    with pytest.raises(HTTPException) as error:
        main.delete_goal(404, db_session, current_user)

    assert error.value.status_code == 404
    assert error.value.detail == "Goal not found"


# ==================== AI ANALYSIS ====================

def test_analyze_goal_requires_existing_goal_and_api_key(db_session, current_user, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(HTTPException) as missing_goal:
        main.analyze_goal(404, db_session, current_user)
    assert missing_goal.value.status_code == 404

    goal = create_goal(db_session, current_user)
    with pytest.raises(HTTPException) as missing_key:
        main.analyze_goal(goal.id, db_session, current_user)
    assert missing_key.value.status_code == 503


def test_analyze_goal_sends_request_and_normalizes_provider_result(
    db_session, current_user, monkeypatch
):
    goal = create_goal(db_session, current_user, description="Build a daily habit")
    provider_result = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "analysis": "  Start with small steps.  ",
                            "proposed_tasks": ["  Plan a schedule  ", "Track progress"],
                        }
                    )
                }
            }
        ]
    }
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(json.dumps(provider_result).encode("utf-8"))

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setattr(main, "urlopen", fake_urlopen)

    result = main.analyze_goal(goal.id, db_session, current_user)

    assert result == {
        "analysis": "Start with small steps.",
        "proposed_tasks": ["Plan a schedule", "Track progress"],
    }
    request, timeout = requests[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert payload["model"] == "test/model"
    assert "Build a daily habit" in payload["messages"][1]["content"]
    assert timeout == 45


def test_analyze_goal_maps_provider_http_error(db_session, current_user, monkeypatch):
    goal = create_goal(db_session, current_user)
    provider_error = HTTPError(
        "https://provider.invalid",
        429,
        "Too Many Requests",
        hdrs=None,
        fp=BytesIO(b'{"error": {"message": "rate limit"}}'),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", urlopen_raising(provider_error))

    with pytest.raises(HTTPException) as error:
        main.analyze_goal(goal.id, db_session, current_user)

    assert error.value.status_code == 502
    assert "rate limit" in error.value.detail


@pytest.mark.parametrize(
    ("provider_failure", "expected_detail"),
    [
        (URLError("offline"), "AI provider could not be reached."),
        (TimeoutError(), "AI provider returned an invalid response."),
    ],
)
def test_analyze_goal_maps_connection_failures(
    db_session, current_user, monkeypatch, provider_failure, expected_detail
):
    goal = create_goal(db_session, current_user)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", urlopen_raising(provider_failure))

    with pytest.raises(HTTPException) as error:
        main.analyze_goal(goal.id, db_session, current_user)

    assert error.value.status_code == 502
    assert error.value.detail == expected_detail


@pytest.mark.parametrize(
    "provider_body",
    [
        b"not json",
        json.dumps({"choices": [{"message": {"content": "not json"}}]}).encode(),
        json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"analysis": "", "proposed_tasks": ["  "]}
                            )
                        }
                    }
                ]
            }
        ).encode(),
    ],
)
def test_analyze_goal_rejects_invalid_provider_responses(
    db_session, current_user, monkeypatch, provider_body
):
    goal = create_goal(db_session, current_user)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "urlopen",
        lambda request, timeout: FakeResponse(provider_body),
    )

    with pytest.raises(HTTPException) as error:
        main.analyze_goal(goal.id, db_session, current_user)

    assert error.value.status_code == 502
