describe("Трекер целей и задач", () => {
  let createdGoalIds = [];

  beforeEach(() => {
    createdGoalIds = [];
    cy.visit("/");
  });

  afterEach(() => {
    cy.then(() => {
      createdGoalIds.forEach((goalId) => {
        cy.request({
          method: "DELETE",
          url: `/api/goals/${goalId}`,
          failOnStatusCode: false,
        });
      });
    });
  });

  function createGoal(title, description = "") {
    cy.intercept("POST", "/api/goals").as("createGoal");
    cy.get("#goal-title").type(title);
    if (description) {
      cy.get("#goal-desc").type(description);
    }
    cy.get("#goal-form").submit();
    cy.wait("@createGoal").then(({ response }) => {
      createdGoalIds.push(response.body.id);
    });
    cy.contains(".goal-item", title).should("be.visible");
  }

  it("создаёт цель, добавляет задачу и обновляет прогресс", () => {
    const goalTitle = `Cypress goal ${Date.now()}`;
    const taskTitle = `Cypress task ${Date.now()}`;

    createGoal(goalTitle, "Цель создана Cypress");
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();

    cy.get("#tasks-container").should("be.visible");
    cy.get("#selected-goal-title").should("contain", goalTitle);
    cy.get("#task-title").type(taskTitle);
    cy.get("#task-form").submit();

    cy.contains(".task-item", taskTitle).as("task");
    cy.get("@task").should("be.visible");
    cy.contains(".goal-item", goalTitle)
      .find(".progress-text")
      .should("contain", "0%");

    cy.get("@task").find('input[type="checkbox"]').check();
    cy.contains(".goal-item", goalTitle)
      .find(".progress-text")
      .should("contain", "100%");
    cy.get("@task").find("span").should("have.class", "completed");
  });

  it("удаляет задачу и цель", () => {
    const goalTitle = `Cypress delete goal ${Date.now()}`;
    const taskTitle = `Cypress delete task ${Date.now()}`;

    createGoal(goalTitle);
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();
    cy.get("#task-title").type(taskTitle);
    cy.get("#task-form").submit();

    cy.contains(".task-item", taskTitle)
      .find(".task-delete-btn")
      .click();
    cy.contains(".task-item", taskTitle).should("not.exist");

    cy.contains(".goal-item", goalTitle).find(".delete-btn").click();
    cy.contains(".goal-item", goalTitle).should("not.exist");
    cy.get("#tasks-container").should("not.be.visible");
    cy.get("#no-selection").should("be.visible");
  });

  it("показывает AI-предложения и добавляет предложенную задачу", () => {
    const goalTitle = `Cypress AI goal ${Date.now()}`;
    const suggestedTask = "Составить план действий";

    createGoal(goalTitle);
    cy.contains(".goal-item", goalTitle).find(".goal-main").click();
    cy.intercept("POST", /\/api\/goals\/\d+\/analyze/, {
      statusCode: 200,
      body: {
        analysis: "Разбейте цель на последовательные практические шаги.",
        proposed_tasks: [suggestedTask, "Проверить результат"],
      },
    }).as("analyzeGoal");

    cy.get("#analyze-goal-button").click();
    cy.wait("@analyzeGoal");
    cy.get("#goal-analysis")
      .should("be.visible")
      .and("contain", "Разбейте цель");
    cy.contains(".suggested-tasks li", suggestedTask)
      .find("button")
      .click()
      .should("have.text", "Добавлено")
      .and("be.disabled");
    cy.contains(".task-item", suggestedTask).should("be.visible");
  });
});
