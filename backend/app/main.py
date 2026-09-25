import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database

# Автоматически создаем таблицы при запуске
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Goals & Tasks Tracker API")

# Настройка CORS, чтобы React (обычно порт 5173 или 3000) мог делать запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/goals", response_model=List[schemas.Goal])
def get_goals(db: Session = Depends(database.get_db)):
    return db.query(models.Goal).all()

@app.post("/api/goals", response_model=schemas.Goal)
def create_goal(goal: schemas.GoalCreate, db: Session = Depends(database.get_db)):
    db_goal = models.Goal(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

@app.get("/api/goals/{goal_id}/tasks", response_model=List[schemas.Task])
def get_tasks(goal_id: int, db: Session = Depends(database.get_db)):
    return db.query(models.Task).filter(models.Task.goal_id == goal_id).all()

@app.post("/api/goals/{goal_id}/tasks", response_model=schemas.Task)
def create_task(goal_id: int, task: schemas.TaskCreate, db: Session = Depends(database.get_db)):
    if not db.query(models.Goal).filter(models.Goal.id == goal_id).first():
        raise HTTPException(status_code=404, detail="Goal not found")
    db_task = models.Task(**task.model_dump(), goal_id=goal_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.patch("/api/tasks/{task_id}", response_model=schemas.Task)
def update_task_status(task_id: int, task_update: schemas.TaskUpdate, db: Session = Depends(database.get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.is_completed = task_update.is_completed
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/api/tasks/{task_id}", response_model=schemas.Task)
def delete_task(task_id: int, db: Session = Depends(database.get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return db_task

@app.delete("/api/goals/{goal_id}", response_model=schemas.Goal)
def delete_goal(goal_id: int, db: Session = Depends(database.get_db)):
    db_goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(db_goal)
    db.commit()
    return db_goal


@app.post("/api/goals/{goal_id}/analyze", response_model=schemas.GoalAnalysis)
def analyze_goal(goal_id: int, db: Session = Depends(database.get_db)):
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI analysis is not configured. Set DEEPSEEK_API_KEY.",
        )

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    prompt = (
        "Analyze this personal goal and propose practical, ordered tasks to reach it. "
        "Return strict JSON with exactly two fields: "
        '"analysis" (a concise explanation) and '
        '"proposed_tasks" (an array of 3 to 7 short task strings). '
        "Do not include markdown.\n\n"
        f"Goal: {goal.title}\n"
        f"Description: {goal.description or 'No description provided'}"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a practical goal-planning assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    request = Request(
        os.getenv(
            "DEEPSEEK_API_URL",
            "https://api.deepseek.com/chat/completions",
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        provider_detail = ""
        try:
            error_body = json.loads(error.read().decode("utf-8"))
            provider_detail = error_body.get("error", {}).get("message", "")
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        detail = f"AI provider request failed with status {error.code}."
        if provider_detail:
            detail = f"{detail} {provider_detail}"
        raise HTTPException(
            status_code=502,
            detail=detail,
        ) from error
    except URLError as error:
        raise HTTPException(
            status_code=502,
            detail="AI provider could not be reached.",
        ) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=502,
            detail="AI provider returned an invalid response.",
        ) from error

    try:
        content = result["choices"][0]["message"]["content"]
        analysis = json.loads(content)
        proposed_tasks = analysis["proposed_tasks"]
        if (
            not isinstance(analysis["analysis"], str)
            or not isinstance(proposed_tasks, list)
            or not proposed_tasks
            or not all(isinstance(task, str) and task.strip() for task in proposed_tasks)
        ):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=502,
            detail="AI provider returned an invalid goal analysis.",
        ) from error

    return {
        "analysis": analysis["analysis"].strip(),
        "proposed_tasks": [task.strip() for task in proposed_tasks],
    }
