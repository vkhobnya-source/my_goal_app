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
