describe("Goals and Tasks Tracker", () => {
  // Keep track of goals created by the current test so they can be removed
  // from the shared database after the test finishes.
  let createdGoalIds = [];

  beforeEach(() => {
    // Start every test with an empty list of test-owned goals.
    createdGoalIds = [];

    // Open the application before each scenario.
    cy.visit("/");
  });

  afterEach(() => {
    // Cypress commands are asynchronous, so use cy.then() to enqueue cleanup
    // after all commands from the test have completed.
    cy.then(() => {
      // Delete every goal created by this test. Deleting a goal also removes
      // its tasks through the application's normal delete behavior.
      createdGoalIds.forEach((goalId) => {
        cy.request({
          method: "DELETE",
          url: `/api/goals/${goalId}`,
          // Cleanup should not hide the original test failure if the record
          // was already removed by the scenario.
          failOnStatusCode: false,
        });
      });
    });
  });

  function createGoal(title, description = "") {
    // Intercept goal creation so the test can wait for the API response and
    // remember the database ID returned by the backend.
    cy.intercept("POST", "/api/goals").as("createGoal");

    // Fill in the goal form. The description is optional, therefore it is
    // typed only when the helper receives a non-empty value.
    cy.get("#goal-title").type(title);
    if (description) {
      cy.get("#goal-desc").type(description);
    }

    // Submit the form and wait until the backend confirms the new goal.
    cy.get("#goal-form").submit();
    cy.wait("@createGoal").then(({ response }) => {
      createdGoalIds.push(response.body.id);
    });

    // Verify that the newly created goal was rendered in the goal list.
    cy.contains(".goal-item", title).should("be.visible");
  }

  it("creates a goal, adds a task, and updates progress", () => {
    // Use unique names so this test cannot accidentally select data left
    // by another run or another test.
    const goalTitle = `Cypress goal ${Date.now()}`;
    const taskTitle = `Cypress task ${Date.now()}`;

    // Create a goal and select it to open its task panel.
    createGoal(goalTitle, "Created by Cypress");
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();

    // The task panel should be visible and should identify the selected goal.
    cy.get("#tasks-container").should("be.visible");
    cy.get("#selected-goal-title").should("contain", goalTitle);

    // Add one task to the selected goal.
    cy.get("#task-title").type(taskTitle);
    cy.get("#task-form").submit();

    // Locate the task and save it as an alias for the following assertions.
    cy.contains(".task-item", taskTitle).as("task");
    cy.get("@task").should("be.visible");

    // A newly added, incomplete task should produce zero percent progress.
    cy.contains(".goal-item", goalTitle)
      .find(".progress-text")
      .should("contain", "0%");

    // Complete the task and verify both the goal progress and completed style.
    cy.get("@task").find('input[type="checkbox"]').check();
    cy.contains(".goal-item", goalTitle)
      .find(".progress-text")
      .should("contain", "100%");
    cy.get("@task").find("span").should("have.class", "completed");
  });

  it("deletes a task and a goal", () => {
    // Generate unique records for this deletion scenario.
    const goalTitle = `Cypress delete goal ${Date.now()}`;
    const taskTitle = `Cypress delete task ${Date.now()}`;

    // Create and select a goal before adding a task to it.
    createGoal(goalTitle);
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();
    cy.get("#task-title").type(taskTitle);
    cy.get("#task-form").submit();

    // Delete the task and verify that it disappears from the task list.
    cy.contains(".task-item", taskTitle)
      .find(".task-delete-btn")
      .click();
    cy.contains(".task-item", taskTitle).should("not.exist");

    // Delete the goal and verify that the task panel closes and the
    // initial "select a goal" placeholder becomes visible again.
    cy.contains(".goal-item", goalTitle).find(".delete-btn").click();
    cy.contains(".goal-item", goalTitle).should("not.exist");
    cy.get("#tasks-container").should("not.be.visible");
    cy.get("#no-selection").should("be.visible");
  });

  it("shows AI suggestions and adds a suggested task", () => {
    // Create a goal that will be used to test the AI-assisted task flow.
    const goalTitle = `Cypress AI goal ${Date.now()}`;
    const suggestedTask = "Create an action plan";

    createGoal(goalTitle);
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();

    // Mock the external AI request. This keeps the test deterministic,
    // avoids network usage, and verifies how the frontend handles a valid
    // backend response.
    cy.intercept("POST", /\/api\/goals\/\d+\/analyze/, {
      statusCode: 200,
      body: {
        analysis: "Break the goal into practical steps.",
        proposed_tasks: [suggestedTask, "Review the result"],
      },
    }).as("analyzeGoal");

    // Request suggestions and wait until the intercepted response is received.
    cy.get("#analyze-goal-button").click();
    cy.wait("@analyzeGoal");

    // Verify that the analysis text and proposed tasks are displayed.
    cy.get("#goal-analysis")
      .should("be.visible")
      .and("contain", "Break the goal");

    // Add one suggested task. The button should become disabled and change
    // its label so the same suggestion cannot be added twice.
    cy.contains(".suggested-tasks li", suggestedTask)
      .find("button")
      .click()
      .should("have.text", "Added")
      .and("be.disabled");

    // Confirm that the suggested task was added to the real task list.
    cy.contains(".task-item", suggestedTask).should("be.visible");
  });
});
