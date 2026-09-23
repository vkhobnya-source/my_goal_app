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
