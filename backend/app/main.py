import json
import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Depends, HTTPException, Request as FastAPIRequest, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database

SESSION_COOKIE = "goal_app_session"
SESSION_DURATION = 60 * 60 * 24 * 30
PASSWORD_HASH_ITERATIONS = 310_000


def initialize_database():
    models.Base.metadata.create_all(bind=database.engine)
    if "user_id" not in {
        column["name"] for column in inspect(database.engine).get_columns("goals")
    }:
        with database.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE goals ADD COLUMN user_id INTEGER REFERENCES users(id)")
            )


initialize_database()

app = FastAPI(title="Goals & Tasks Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(
    request: FastAPIRequest,
    db: Session = Depends(database.get_db),
) -> models.User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    login_session = (
        db.query(models.LoginSession)
        .filter(models.LoginSession.token_hash == token_hash)
        .first()
    )
    if not login_session or login_session.expires_at <= int(time.time()):
        if login_session:
            db.delete(login_session)
            db.commit()
        raise HTTPException(status_code=401, detail="Authentication required")
    return login_session.user


def create_login_session(
    user: models.User,
    db: Session,
    response: Response,
) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + SESSION_DURATION
    db.add(
        models.LoginSession(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user_id=user.id,
            expires_at=expires_at,
        )
    )
    db.commit()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DURATION,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
        samesite="strict",
        path="/",
    )


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    ).hex()


@app.post("/api/auth/register", response_model=schemas.User, status_code=201)
def register(
    credentials: schemas.Credentials,
    response: Response,
    db: Session = Depends(database.get_db),
):
    email = credentials.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    salt = secrets.token_bytes(16)
    user = models.User(
        email=email,
        password_salt=salt.hex(),
        password_hash=hash_password(credentials.password, salt),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        ) from error
    db.refresh(user)
    create_login_session(user, db, response)
    return user


@app.post("/api/auth/login", response_model=schemas.User)
def login(
    credentials: schemas.LoginCredentials,
    response: Response,
    db: Session = Depends(database.get_db),
):
    email = credentials.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not hmac.compare_digest(
        user.password_hash,
        hash_password(credentials.password, bytes.fromhex(user.password_salt))
        if user
        else "",
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    create_login_session(user, db, response)
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(
    request: FastAPIRequest,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    token = request.cookies[SESSION_COOKIE]
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.query(models.LoginSession).filter(
        models.LoginSession.token_hash == token_hash,
        models.LoginSession.user_id == user.id,
    ).delete()
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")


@app.get("/api/auth/me", response_model=schemas.User)
def get_me(user: models.User = Depends(get_current_user)):
    return user


@app.get("/api/goals", response_model=List[schemas.Goal])
def get_goals(
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.Goal).filter(models.Goal.user_id == user.id).all()

@app.post("/api/goals", response_model=schemas.Goal)
def create_goal(
    goal: schemas.GoalCreate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    db_goal = models.Goal(**goal.model_dump(), user_id=user.id)
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

@app.get("/api/goals/{goal_id}/tasks", response_model=List[schemas.Task])
def get_tasks(
    goal_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Task)
        .join(models.Goal)
        .filter(
            models.Task.goal_id == goal_id,
            models.Goal.user_id == user.id,
        )
        .all()
    )

@app.post("/api/goals/{goal_id}/tasks", response_model=schemas.Task)
def create_task(
    goal_id: int,
    task: schemas.TaskCreate,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    if not db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == user.id,
    ).first():
        raise HTTPException(status_code=404, detail="Goal not found")
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
    user: models.User = Depends(get_current_user),
):
    db_task = (
        db.query(models.Task)
        .join(models.Goal)
        .filter(models.Task.id == task_id, models.Goal.user_id == user.id)
        .first()
    )
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.is_completed = task_update.is_completed
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/api/tasks/{task_id}", response_model=schemas.Task)
def delete_task(
    task_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    db_task = (
        db.query(models.Task)
        .join(models.Goal)
        .filter(models.Task.id == task_id, models.Goal.user_id == user.id)
        .first()
    )
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return db_task

@app.delete("/api/goals/{goal_id}", response_model=schemas.Goal)
def delete_goal(
    goal_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    db_goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == user.id,
    ).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(db_goal)
    db.commit()
    return db_goal


@app.post("/api/goals/{goal_id}/analyze", response_model=schemas.GoalAnalysis)
def analyze_goal(
    goal_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI analysis is not configured. Set OPENROUTER_API_KEY.",
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
