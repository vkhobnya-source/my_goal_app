import json

from fastapi.testclient import TestClient

from backend.app import main


def test_create_and_get_goal(client):
    # 1. Создаем цель
    response = client.post(
        "/api/goals",
        json={"title": "Тестовая цель", "description": "Описание тестовой цели"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Тестовая цель"
    assert data["id"] is not None

    # 2. Получаем список целей и проверяем, что она там есть
    response = client.get("/api/goals")
    assert response.status_code == 200
    goals = response.json()
    assert len(goals) == 1
    assert goals[0]["title"] == "Тестовая цель"

def test_create_task_for_goal(client):
    # 1. Сначала создаем цель
    goal_res = client.post("/api/goals", json={"title": "Цель для задач"})
    goal_id = goal_res.json()["id"]

    # 2. Добавляем задачу к этой цели
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Подзадача 1"}
    )
    assert task_res.status_code == 200
    task_data = task_res.json()
    assert task_data["title"] == "Подзадача 1"
    assert task_data["goal_id"] == goal_id


def test_delete_task(client):
    goal_res = client.post("/api/goals", json={"title": "Цель для удаления задачи"})
    goal_id = goal_res.json()["id"]
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Задача для удаления"},
    )
    task_id = task_res.json()["id"]

    delete_res = client.delete(f"/api/tasks/{task_id}")

    assert delete_res.status_code == 200
    assert delete_res.json()["id"] == task_id
    assert client.get(f"/api/goals/{goal_id}/tasks").json() == []


def test_delete_goal_cascades_to_tasks(client):
    goal_res = client.post("/api/goals", json={"title": "Цель с задачами для удаления"})
    goal_id = goal_res.json()["id"]
    task_res = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Задача удалится вместе с целью"},
    )
    task_id = task_res.json()["id"]

    delete_res = client.delete(f"/api/goals/{goal_id}")

    assert delete_res.status_code == 200
    assert delete_res.json()["id"] == goal_id
    assert client.get("/api/goals").json() == []
    assert client.get(f"/api/goals/{goal_id}/tasks").json() == []
    assert client.delete(f"/api/tasks/{task_id}").status_code == 404


def test_analyze_goal_returns_proposed_tasks(client, monkeypatch):
    goal_res = client.post(
        "/api/goals",
        json={"title": "Подготовиться к марафону", "description": "Пробежать 42 км"},
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

        @staticmethod
        def read():
            return json.dumps(response_body).encode("utf-8")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main, "urlopen", lambda request, timeout: FakeResponse())

    response = client.post(f"/api/goals/{goal_id}/analyze")

    assert response.status_code == 200
    assert response.json()["analysis"] == "Нужно постепенно развить выносливость."
    assert response.json()["proposed_tasks"] == [
        "Составить план тренировок",
        "Провести легкую пробежку",
    ]


def test_authentication_and_session_lifecycle(client):
    client.cookies.clear()
    assert client.get("/api/goals").status_code == 401

    registration = client.post(
        "/api/auth/register",
        json={"email": " New.User@example.com ", "password": "secure-password"},
    )
    assert registration.status_code == 201
    assert registration.json()["email"] == "new.user@example.com"
    assert client.cookies.get("goal_app_session")

    assert client.post(
        "/api/auth/register",
        json={"email": "new.user@example.com", "password": "secure-password"},
    ).status_code == 409

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": "NEW.USER@example.com", "password": "secure-password"},
    )
    assert login.status_code == 200
    assert login.json()["email"] == "new.user@example.com"


def test_test_user_can_log_in_and_log_out(client):
    client.cookies.clear()

    login = client.post(
        "/api/auth/login",
        json={"email": "test@test.ts", "password": "test"},
    )
    assert login.status_code == 200
    assert login.json()["email"] == "test@test.ts"
    assert client.cookies.get("goal_app_session")
    assert client.get("/api/auth/me").json()["email"] == "test@test.ts"
    assert client.get("/api/goals").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    invalid_login = client.post(
        "/api/auth/login",
        json={"email": "test@test.ts", "password": "wrong"},
    )
    assert invalid_login.status_code == 401


def test_users_cannot_access_each_others_goals_or_tasks(client):
    goal_id = client.post(
        "/api/goals",
        json={"title": "Private goal"},
    ).json()["id"]
    task_id = client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Private task"},
    ).json()["id"]

    other_client = TestClient(main.app)
    registration = other_client.post(
        "/api/auth/register",
        json={"email": "other-user@example.com", "password": "another-password"},
    )
    assert registration.status_code == 201
    assert other_client.get("/api/goals").json() == []
    assert other_client.get(f"/api/goals/{goal_id}/tasks").json() == []
    assert other_client.post(
        f"/api/goals/{goal_id}/tasks",
        json={"title": "Unauthorized task"},
    ).status_code == 404
    assert other_client.post(f"/api/goals/{goal_id}/analyze").status_code == 404
    assert other_client.patch(
        f"/api/tasks/{task_id}",
        json={"is_completed": True},
    ).status_code == 404
    assert other_client.delete(f"/api/tasks/{task_id}").status_code == 404
    assert other_client.delete(f"/api/goals/{goal_id}").status_code == 404
