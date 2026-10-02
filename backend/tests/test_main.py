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
from backend.app import main, models, schemas  # noqa: E402

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


def create_goal(db_session, title="Learn Python", description=None):
    return main.create_goal(
        schemas.GoalCreate(title=title, description=description),
        db_session,
    )


def test_create_goal_sets_defaults_and_get_goals_returns_it(db_session):
    goal = create_goal(db_session, description="Practice every day")

    assert goal.title == "Learn Python"
    assert goal.description == "Practice every day"
    assert goal.is_completed is False
    assert main.get_goals(db_session) == [goal]


def test_create_task_requires_an_existing_goal(db_session):
    with pytest.raises(HTTPException) as error:
        main.create_task(404, schemas.TaskCreate(title="Study"), db_session)

    assert error.value.status_code == 404
    assert error.value.detail == "Goal not found"


def test_create_task_assigns_goal_and_default_status(db_session):
    goal = create_goal(db_session)

    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
    )

    assert task.title == "Read a chapter"
    assert task.goal_id == goal.id
    assert task.is_completed is False
    assert main.get_tasks(goal.id, db_session) == [task]


def test_update_task_status_changes_completion(db_session):
    goal = create_goal(db_session)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
    )

    updated = main.update_task_status(
        task.id,
        schemas.TaskUpdate(is_completed=True),
        db_session,
    )

    assert updated.is_completed is True


def test_update_missing_task_returns_not_found(db_session):
    with pytest.raises(HTTPException) as error:
        main.update_task_status(
            404,
            schemas.TaskUpdate(is_completed=True),
            db_session,
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_delete_task_removes_it(db_session):
    goal = create_goal(db_session)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
    )

    deleted = main.delete_task(task.id, db_session)

    assert deleted.id == task.id
    assert main.get_tasks(goal.id, db_session) == []


def test_delete_missing_task_returns_not_found(db_session):
    with pytest.raises(HTTPException) as error:
        main.delete_task(404, db_session)

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_delete_goal_cascades_to_tasks(db_session):
    goal = create_goal(db_session)
    task = main.create_task(
        goal.id,
        schemas.TaskCreate(title="Read a chapter"),
        db_session,
    )

    deleted = main.delete_goal(goal.id, db_session)

    assert deleted.id == goal.id
    assert db_session.get(models.Task, task.id) is None


def test_delete_missing_goal_returns_not_found(db_session):
    with pytest.raises(HTTPException) as error:
        main.delete_goal(404, db_session)

    assert error.value.status_code == 404
    assert error.value.detail == "Goal not found"


def test_analyze_goal_requires_existing_goal_and_api_key(db_session, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(HTTPException) as missing_goal:
        main.analyze_goal(404, db_session)
    assert missing_goal.value.status_code == 404

    goal = create_goal(db_session)
    with pytest.raises(HTTPException) as missing_key:
        main.analyze_goal(goal.id, db_session)
    assert missing_key.value.status_code == 503


def test_analyze_goal_sends_request_and_normalizes_provider_result(
    db_session, monkeypatch
):
    goal = create_goal(db_session, description="Build a daily habit")
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

    result = main.analyze_goal(goal.id, db_session)

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


def test_analyze_goal_maps_provider_http_error(db_session, monkeypatch):
    goal = create_goal(db_session)
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
        main.analyze_goal(goal.id, db_session)

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
    db_session, monkeypatch, provider_failure, expected_detail
):
    goal = create_goal(db_session)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", urlopen_raising(provider_failure))

    with pytest.raises(HTTPException) as error:
        main.analyze_goal(goal.id, db_session)

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
    db_session, monkeypatch, provider_body
):
    goal = create_goal(db_session)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "urlopen",
        lambda request, timeout: FakeResponse(provider_body),
    )

    with pytest.raises(HTTPException) as error:
        main.analyze_goal(goal.id, db_session)

    assert error.value.status_code == 502
