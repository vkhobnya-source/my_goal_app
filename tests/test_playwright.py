import os
import time
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv(
    "PLAYWRIGHT_BASE_URL",
    "http://frontend" if os.environ.get("CHROME_BIN") else "http://localhost",
)
API_URL = os.getenv("PLAYWRIGHT_API_URL")
TEST_EMAIL = f"playwright-{uuid4().hex}@example.test"
TEST_PASSWORD = f"pw-{uuid4().hex}"
test_user_registered = False


def open_page():
    global test_user_registered

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    if API_URL:
        api_url = urlsplit(API_URL)

        def route_api(route):
            request_url = urlsplit(route.request.url)
            route.continue_(
                url=urlunsplit(
                    (
                        api_url.scheme,
                        api_url.netloc,
                        request_url.path,
                        request_url.query,
                        request_url.fragment,
                    )
                )
            )

        page.route("**/api/**", route_api)
    page.goto(BASE_URL)
    if page.locator("#auth-view").is_visible():
        if not test_user_registered:
            page.locator("#auth-mode-toggle").click()
        page.locator("#auth-email").fill(TEST_EMAIL)
        page.locator("#auth-password").fill(TEST_PASSWORD)
        page.locator("#auth-submit").click()
        expect(page.locator("#app-view")).to_be_visible()
        test_user_registered = True
    return playwright, browser, page


def test_goal_task_progress_and_deletion():
    playwright, browser, page = open_page()
    goal_name = f"Playwright goal {time.time_ns()}"
    task_name = f"Playwright task {time.time_ns()}"

    try:
        expect(page).to_have_title("Трекер Целей и Задач")
        page.locator("#goal-title").fill(goal_name)
        page.locator("#goal-desc").fill("Created by Playwright")
        page.locator("#goal-form button").click()

        goal = page.locator(".goal-item", has_text=goal_name)
        expect(goal).to_be_visible()
        goal.locator(".goal-main").click()
        expect(page.locator("#tasks-container")).to_be_visible()

        page.locator("#task-title").fill(task_name)
        page.locator("#task-form button").click()
        task = page.locator(".task-item", has_text=task_name)
        expect(task).to_be_visible()

        expect(goal.locator(".progress-text")).to_contain_text("0%")
        task.locator("input[type='checkbox']").check()
        expect(goal.locator(".progress-text")).to_contain_text("100%")

        task.locator(".task-delete-btn").click()
        expect(page.locator(".task-item", has_text=task_name)).to_have_count(0)

        goal.locator(".delete-btn").click()
        expect(page.locator(".goal-item", has_text=goal_name)).to_have_count(0)
        expect(page.locator("#tasks-container")).to_be_hidden()
    finally:
        browser.close()
        playwright.stop()


def test_ai_suggestions_can_be_added_as_tasks():
    playwright, browser, page = open_page()
    goal_name = f"Playwright AI goal {time.time_ns()}"
    suggested_task = "Create a weekly action plan"

    try:
        page.locator("#goal-title").fill(goal_name)
        page.locator("#goal-form button").click()

        goal = page.locator(".goal-item", has_text=goal_name)
        goal.locator(".goal-main").click()

        def mock_analysis(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=(
                    '{"analysis":"Break the goal into practical steps.",'
                    f'"proposed_tasks":["{suggested_task}","Review progress"]}}'
                ),
            )

        page.route("**/api/goals/*/analyze", mock_analysis)
        page.locator("#analyze-goal-button").click()

        analysis = page.locator("#goal-analysis")
        expect(analysis).to_be_visible()
        expect(analysis).to_contain_text("Break the goal into practical steps.")
        suggested = analysis.locator(".suggested-tasks li").filter(has_text=suggested_task)
        expect(suggested).to_be_visible()

        suggested.locator("button").click()
        expect(suggested.locator("button")).to_have_text("Добавлено")
        expect(page.locator(".task-item", has_text=suggested_task)).to_be_visible()

        goal.locator(".delete-btn").click()
    finally:
        browser.close()
        playwright.stop()
