import json

import pytest

from backend.app import main


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "api-user@example.com", "password": "secret"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_goal(client, auth_headers):
    # 1. Создаем цель
    response = client.post(
        "/api/goals",
        json={"title": "Тестовая цель", "description": "Описание тестовой цели"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Тестовая цель"
    assert data["id"] is not None

    # 2. Получаем список целей и проверяем, что она там есть
    response = client.get("/api/goals", headers=auth_headers)
    assert response.status_code == 200
    goals = response.json()
    assert len(goals) == 1
    assert goals[0]["title"] == "Тестовая цель"

def test_create_task_for_goal(client, auth_headers):
    # 1. Сначала создаем цель
    goal_res = client.post(
        "/api/goals", json={"title": "Цель для задач"}, headers=auth_headers
    )
    goal_id = goal_res.json()["id"]

    # 2. Добавляем задачу к этой цели
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Подзадача 1"},
        headers=auth_headers,
    )
    assert task_res.status_code == 200
    task_data = task_res.json()
    assert task_data["title"] == "Подзадача 1"
    assert task_data["goal_id"] == goal_id


def test_delete_task(client, auth_headers):
    goal_res = client.post(
        "/api/goals", json={"title": "Цель для удаления задачи"}, headers=auth_headers
    )
    goal_id = goal_res.json()["id"]
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Задача для удаления"},
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    delete_res = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

    assert delete_res.status_code == 200
    assert delete_res.json()["id"] == task_id
    assert client.get(f"/api/goals/{goal_id}/tasks", headers=auth_headers).json() == []


def test_delete_goal_cascades_to_tasks(client, auth_headers):
    goal_res = client.post(
        "/api/goals",
        json={"title": "Цель с задачами для удаления"},
        headers=auth_headers,
    )
    goal_id = goal_res.json()["id"]
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Задача удалится вместе с целью"},
        headers=auth_headers,
    )
    task_id = task_res.json()["id"]

    delete_res = client.delete(f"/api/goals/{goal_id}", headers=auth_headers)

    assert delete_res.status_code == 200
    assert delete_res.json()["id"] == goal_id
    assert client.get("/api/goals", headers=auth_headers).json() == []
    assert client.get(f"/api/goals/{goal_id}/tasks", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_analyze_goal_returns_proposed_tasks(client, auth_headers, monkeypatch):
    goal_res = client.post(
        "/api/goals",
        json={"title": "Подготовиться к марафону", "description": "Пробежать 42 км"},
        headers=auth_headers,
    )
    goal_id = goal_res.json()["id"]
    response_body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "analysis": "Нужно постепенно развить выносливость.",
                            "proposed_tasks": [
                                "Составить план тренировок",
                                "Провести легкую пробежку",
                            ],
                        }
                    )
                }
            }
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(response_body).encode("utf-8")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", lambda request, timeout: FakeResponse())

    response = client.post(f"/api/goals/{goal_id}/analyze", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["analysis"] == "Нужно постепенно развить выносливость."
    assert response.json()["proposed_tasks"] == [
        "Составить план тренировок",
        "Провести легкую пробежку",
    ]


def test_goals_endpoints_require_authentication(client):
    assert client.get("/api/goals").status_code == 401
    assert client.post("/api/goals", json={"title": "No auth"}).status_code == 401


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/goals",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


def test_goals_are_isolated_between_users(client):
    first = client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": "secret"},
    )
    second = client.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "secret"},
    )
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    client.post("/api/goals", json={"title": "First goal"}, headers=first_headers)

    assert len(client.get("/api/goals", headers=first_headers).json()) == 1
    assert client.get("/api/goals", headers=second_headers).json() == []
