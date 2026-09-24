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
