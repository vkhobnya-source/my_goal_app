import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture(scope="module")
def driver():
    options = webdriver.ChromeOptions()
    # МЫ УБРАЛИ --headless! Теперь вы будете видеть окно браузера во время теста.
    options.add_argument("--window-size=1280,800")

    # Автоматически скачиваем и запускаем правильный ChromeDriver под ваш Windows Chrome
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


def test_frontend_flow(driver):
    # Тесты на Windows стучатся на локальный порт Nginx
    base_url = "http://localhost/goals"
    driver.get(base_url)

    assert "Трекер Целей и Задач" in driver.title

    title_input = driver.find_element(By.ID, "goal-title")
    desc_input = driver.find_element(By.ID, "goal-desc")
    submit_button = driver.find_element(By.XPATH, "//form[@id='goal-form']/button")

    title_input.send_keys("Авто-Цель Selenium")
    desc_input.send_keys("Создано автоматически во время теста")
    submit_button.click()

    # Умное ожидание появления карточки на Windows-скоростях
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "goal-item"))
    )

    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    assert len(goal_items) > 0


def test_goal_progress_bar_updates(driver):
    base_url = "http://localhost"
    driver.get(base_url)

    title_input = driver.find_element(By.ID, "goal-title")
    submit_button = driver.find_element(By.XPATH, "//form[@id='goal-form']/button")

    goal_name = "Цель для прогресс-бара"
    title_input.send_keys(goal_name)
    submit_button.click()

    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "goal-item"))
    )

    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    target_goal = next(item for item in goal_items if goal_name in item.text)
    target_goal.click()

    progress_text_before = target_goal.find_element(By.CLASS_NAME, "progress-text").text
    assert "0%" in progress_text_before

    task_input = driver.find_element(By.ID, "task-title")
    task_submit = driver.find_element(By.XPATH, "//form[@id='task-form']/button")
    task_input.send_keys("Выполнить тест прогресса")
    task_submit.click()

    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "task-item"))
    )

    task_checkbox = driver.find_element(By.CSS_SELECTOR, "#tasks-list .task-item input[type='checkbox']")
    task_checkbox.click()

    time.sleep(0.5)

    # Перенаходим цель, так как DOM обновился
    goal_items = driver.find_elements(By.CLASS_NAME, "goal-item")
    target_goal = next(item for item in goal_items if goal_name in item.text)

    progress_text_after = target_goal.find_element(By.CLASS_NAME, "progress-text").text
    assert "100%" in progress_text_after
