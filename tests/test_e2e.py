import os
import pytest
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def ensure_signed_in(driver):
    if driver.find_elements(By.ID, "app-view") and driver.find_element(
        By.ID, "app-view"
    ).is_displayed():
        return

    driver.find_element(By.ID, "auth-email").send_keys("test@test.ts")
    driver.find_element(By.ID, "auth-password").send_keys("test")
    driver.find_element(By.ID, "auth-submit").click()
    WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.ID, "app-view"))
    )


@pytest.fixture(scope="module")
def driver():
    options = webdriver.ChromeOptions()

    # Общие аргументы для стабильности в Docker и Headless режиме
    #options.add_argument("--headless=new")  # Новый, более стабильный headless режим
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")  # Задаем FULL HD разрешение экрана
    options.add_argument("--disable-web-security")  # Отключаем CORS-блокировки для тестов
    options.add_argument("--allow-running-insecure-content")

    if os.environ.get("CHROME_BIN"):
        options.binary_location = os.environ.get("CHROME_BIN")
        driver = webdriver.Chrome(options=options)
    else:
        # Локальный запуск на Windows напрямую (без Docker)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.implicitly_wait(5)
    yield driver
    driver.quit()


def test_frontend_flow(driver):
    # Если мы в Docker, фронтенд доступен по имени контейнера 'frontend', иначе 'localhost'
    base_url = "http://frontend" if os.environ.get("CHROME_BIN") else "http://localhost"
    driver.get(base_url)
    ensure_signed_in(driver)

    # Проверяем заголовок страницы
    assert "Трекер Целей и Задач" in driver.title

    # 2. Находим поля формы создания цели и заполняем их
    title_input = driver.find_element(By.ID, "goal-title")
    desc_input = driver.find_element(By.ID, "goal-desc")
    submit_button = driver.find_element(By.XPATH, "//form[@id='goal-form']/button")

    title_input.send_keys("Авто-Цель Selenium")
    desc_input.send_keys("Создано автоматически во время теста")
    submit_button.click()

    # Ждем обновления DOM и проверяем, что цель появилась на экране
    time.sleep(1)
    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    assert len(goal_items) > 0

    # Находим созданную цель по тексту и кликаем на нее
    target_goal = None
    for item in goal_items:
        if "Авто-Цель Selenium" in item.text:
            target_goal = item
            break

    assert target_goal is not None, "Цель не была найдена на UI"
    target_goal.click()

    # 3. Проверяем, что открылась панель задач и добавляем задачу
    time.sleep(0.5)
    task_input = driver.find_element(By.ID, "task-title")
    task_submit = driver.find_element(By.XPATH, "//form[@id='task-form']/button")

    task_input.send_keys("Шаг 1 для Selenium")
    task_submit.click()

    # Проверяем появление задачи на экране
    time.sleep(0.5)
    tasks = driver.find_elements(By.CLASS_NAME, "task-item")
    assert any("Шаг 1 для Selenium" in t.text for t in tasks)

def test_goal_progress_bar_updates(driver):
    # 1. Открываем приложение
    base_url = "http://frontend" if os.environ.get("CHROME_BIN") else "http://localhost"
    driver.get(base_url)
    ensure_signed_in(driver)
    # Даем бэкенду и фронтенду в докере гарантированно связаться по сети
    time.sleep(3)

    assert "Трекер Целей и Задач" in driver.title
    # 2. Создаем новую цель для проверки прогресса
    title_input = driver.find_element(By.ID, "goal-title")
    submit_button = driver.find_element(By.XPATH, "//form[@id='goal-form']/button")

    goal_name = "Цель для прогресс-бара"
    title_input.send_keys(goal_name)
    submit_button.click()
    time.sleep(1)

    # 3. Находим созданную цель по тексту и кликаем на нее
    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    target_goal = next(item for item in goal_items if goal_name in item.text)
    target_goal.click()
    time.sleep(5)

    # ВАЖНО: После клика JS мог обновить список целей.
    # Находим этот элемент в DOM заново перед проверкой прогресса!
    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    target_goal = next(item for item in goal_items if goal_name in item.text)

    # Проверяем, что изначально прогресс равен 0%
    progress_text_before = target_goal.find_element(By.CLASS_NAME, "progress-text").text
    assert "0%" in progress_text_before

    # 4. Добавляем одну подзадачу к этой цели
    task_input = driver.find_element(By.ID, "task-title")
    task_submit = driver.find_element(By.XPATH, "//form[@id='task-form']/button")
    task_input.send_keys("Выполнить тест прогресса")
    task_submit.click()
    time.sleep(0.5)

    # 5. Находим чекбокс добавленной задачи и кликаем по нему (завершаем задачу)
    task_checkbox = driver.find_element(By.CSS_SELECTOR, "#tasks-list .task-item input[type='checkbox']")
    task_checkbox.click()
    time.sleep(5)

    # ВАЖНО: Клик по чекбоксу вызвал fetchGoals() и перерисовал карточку цели слева.
    # Снова перенаходим элемент цели в DOM, чтобы избежать StaleElementReferenceException!
    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    target_goal = next(item for item in goal_items if goal_name in item.text)

    # 6. Проверяем, что прогресс-бар на карточке цели слева обновился до 100%
    progress_text_after = target_goal.find_element(By.CLASS_NAME, "progress-text").text
    assert "100%" in progress_text_after, f"Ожидалось 100%, но получили: {progress_text_after}"


def test_delete_goal_and_task(driver):
    base_url = "http://frontend" if os.environ.get("CHROME_BIN") else "http://localhost"
    driver.get(base_url)
    ensure_signed_in(driver)

    goal_name = f"Цель для удаления {time.time_ns()}"
    task_name = f"Задача для удаления {time.time_ns()}"

    title_input = driver.find_element(By.ID, "goal-title")
    title_input.send_keys(goal_name)
    driver.find_element(By.XPATH, "//form[@id='goal-form']/button").click()
    time.sleep(1)

    goal_item = next(
        item for item in driver.find_elements(By.CLASS_NAME, "goal-item")
        if goal_name in item.text
    )
    goal_item.find_element(By.CLASS_NAME, "goal-main").click()
    time.sleep(0.5)

    task_input = driver.find_element(By.ID, "task-title")
    task_input.send_keys(task_name)
    driver.find_element(By.XPATH, "//form[@id='task-form']/button").click()
    time.sleep(0.5)

    task_item = next(
        item for item in driver.find_elements(By.CLASS_NAME, "task-item")
        if task_name in item.text
    )
    task_item.find_element(By.CLASS_NAME, "task-delete-btn").click()
    time.sleep(0.5)

    remaining_tasks = [
        item for item in driver.find_elements(By.CLASS_NAME, "task-item")
        if task_name in item.text
    ]
    assert remaining_tasks == []

    goal_item = next(
        item for item in driver.find_elements(By.CLASS_NAME, "goal-item")
        if goal_name in item.text
    )
    goal_item.find_element(By.CLASS_NAME, "delete-btn").click()
    time.sleep(0.5)

    remaining_goals = [
        item for item in driver.find_elements(By.CLASS_NAME, "goal-item")
        if goal_name in item.text
    ]
    assert remaining_goals == []
    assert driver.find_element(By.ID, "tasks-container").is_displayed() is False
