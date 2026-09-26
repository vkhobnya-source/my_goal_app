import os
import time

from playwright.sync_api import Page, expect, sync_playwright


BASE_URL = "http://frontend" if os.environ.get("CHROME_BIN") else "http://localhost"


def open_page():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(BASE_URL)
    if page.locator("#auth-view").is_visible():
        page.locator("#auth-email").fill("test@test.ts")
        page.locator("#auth-password").fill("test")
        page.locator("#auth-submit").click()
        expect(page.locator("#app-view")).to_be_visible()
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
