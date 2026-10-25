import json
import os
from typing import Annotated, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, database, i18n, models, schemas

router = APIRouter(prefix="/api", tags=["Goals"])


@router.get("/goals", response_model=List[schemas.Goal])
def get_goals(
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
) -> List[schemas.Goal]:
    """Получить все цели текущего пользователя"""
    return db.query(models.Goal).filter(models.Goal.user_id == current_user.id).all()


@router.post("/goals", response_model=schemas.Goal)
def create_goal(
    goal: schemas.GoalCreate,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
) -> schemas.Goal:
    """Создать новую цель"""
    db_goal = models.Goal(**goal.model_dump(), user_id=current_user.id)
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@router.delete("/goals/{goal_id}", response_model=schemas.Goal)
def delete_goal(
    goal_id: int,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
) -> schemas.Goal:
    """Удалить цель"""
    lang = i18n.resolve_language(None)
    db_goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not db_goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("goal_not_found", lang),
        )
    db.delete(db_goal)
    db.commit()
    return db_goal


@router.post("/goals/{goal_id}/analyze", response_model=schemas.GoalAnalysis)
def analyze_goal(
    goal_id: int,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    accept_language: Optional[str] = Header(default=None),
) -> schemas.GoalAnalysis:
    """Анализ цели с помощью AI"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("goal_not_found", lang),
        )

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
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
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from error
    except URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=i18n.t("ai_provider_unreachable", lang),
        ) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
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
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=i18n.t("ai_provider_invalid_analysis", lang),
        ) from error

    return {
        "analysis": analysis["analysis"].strip(),
        "proposed_tasks": [task.strip() for task in proposed_tasks],
    }
