import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import timedelta

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas, database, auth, i18n

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

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/api/auth/register", response_model=schemas.Token)
def register(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    accept_language: Optional[str] = Header(default=None),
):
    """Регистрация нового пользователя"""
    lang = i18n.resolve_language(accept_language)
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail=i18n.t("email_already_registered", lang),
        )
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=schemas.Token)
def login(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    accept_language: Optional[str] = Header(default=None),
):
    """Вход в систему"""
    lang = i18n.resolve_language(accept_language)
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail=i18n.t("invalid_credentials", lang),
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ==================== GOALS ENDPOINTS ====================

@app.get("/api/goals", response_model=List[schemas.Goal])
def get_goals(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Получить все цели текущего пользователя"""
    return db.query(models.Goal).filter(models.Goal.user_id == current_user.id).all()

@app.post("/api/goals", response_model=schemas.Goal)
def create_goal(goal: schemas.GoalCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Создать новую цель"""
    db_goal = models.Goal(**goal.model_dump(), user_id=current_user.id)
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

@app.get("/api/goals/{goal_id}/tasks", response_model=List[schemas.Task])
def get_tasks(
    goal_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Получить все задачи цели"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=i18n.t("goal_not_found", lang))
    return db.query(models.Task).filter(models.Task.goal_id == goal_id).all()

@app.post("/api/goals/{goal_id}/tasks", response_model=schemas.Task)
def create_task(
    goal_id: int,
    task: schemas.TaskCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Создать новую задачу"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=i18n.t("goal_not_found", lang))
    db_task = models.Task(**task.model_dump(), goal_id=goal_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.patch("/api/tasks/{task_id}", response_model=schemas.Task)
def update_task_status(
    task_id: int,
    task_update: schemas.TaskUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Обновить статус задачи"""
    lang = i18n.resolve_language(accept_language)
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail=i18n.t("task_not_found", lang))
    
    # Проверяем, что задача принадлежит пользователю
    goal = db.query(models.Goal).filter(models.Goal.id == db_task.goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=403, detail=i18n.t("not_authorized", lang))
    
    db_task.is_completed = task_update.is_completed
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/api/tasks/{task_id}", response_model=schemas.Task)
def delete_task(
    task_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Удалить задачу"""
    lang = i18n.resolve_language(accept_language)
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail=i18n.t("task_not_found", lang))
    
    # Проверяем, что задача принадлежит пользователю
    goal = db.query(models.Goal).filter(models.Goal.id == db_task.goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=403, detail=i18n.t("not_authorized", lang))
    
    db.delete(db_task)
    db.commit()
    return db_task

@app.delete("/api/goals/{goal_id}", response_model=schemas.Goal)
def delete_goal(
    goal_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Удалить цель"""
    lang = i18n.resolve_language(accept_language)
    db_goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail=i18n.t("goal_not_found", lang))
    db.delete(db_goal)
    db.commit()
    return db_goal


@app.post("/api/goals/{goal_id}/analyze", response_model=schemas.GoalAnalysis)
def analyze_goal(
    goal_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
    accept_language: Optional[str] = Header(default=None),
):
    """Анализ цели с помощью AI"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=i18n.t("goal_not_found", lang))

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=i18n.t("ai_not_configured", lang),
        )

    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
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
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "My Goal App"),
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
        detail = i18n.t("ai_provider_http_error", lang, status=error.code)
        if provider_detail:
            detail = f"{detail} {provider_detail}"
        raise HTTPException(
            status_code=502,
            detail=detail,
        ) from error
    except URLError as error:
        raise HTTPException(
            status_code=502,
            detail=i18n.t("ai_provider_unreachable", lang),
        ) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=502,
            detail=i18n.t("ai_provider_invalid_response", lang),
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
            detail=i18n.t("ai_provider_invalid_analysis", lang),
        ) from error

    return {
        "analysis": analysis["analysis"].strip(),
        "proposed_tasks": [task.strip() for task in proposed_tasks],
    }
