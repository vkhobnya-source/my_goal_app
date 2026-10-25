from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, database, i18n, models, schemas

router = APIRouter(prefix="/api", tags=["Tasks"])


@router.get("/goals/{goal_id}/tasks", response_model=List[schemas.Task])
def get_tasks(
    goal_id: int,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    accept_language: Optional[str] = Header(default=None),
) -> List[schemas.Task]:
    """Получить все задачи цели"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("goal_not_found", lang),
        )
    return db.query(models.Task).filter(models.Task.goal_id == goal_id).all()


@router.post("/goals/{goal_id}/tasks", response_model=schemas.Task)
def create_task(
    goal_id: int,
    task: schemas.TaskCreate,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    accept_language: Optional[str] = Header(default=None),
) -> schemas.Task:
    """Создать новую задачу"""
    lang = i18n.resolve_language(accept_language)
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("goal_not_found", lang),
        )
    db_task = models.Task(**task.model_dump(), goal_id=goal_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.put("/tasks/{task_id}", response_model=schemas.Task)
@router.patch("/tasks/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    accept_language: Optional[str] = Header(default=None),
) -> schemas.Task:
    """Обновить задачу"""
    lang = i18n.resolve_language(accept_language)
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("task_not_found", lang),
        )

    # Проверяем, что задача принадлежит пользователю
    goal = db.query(models.Goal).filter(models.Goal.id == db_task.goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=i18n.t("not_authorized", lang),
        )

    if task_update.title is not None:
        db_task.title = task_update.title
    if task_update.is_completed is not None:
        db_task.is_completed = task_update.is_completed
    db.commit()
    db.refresh(db_task)
    return db_task


@router.delete("/tasks/{task_id}", response_model=schemas.Task)
def delete_task(
    task_id: int,
    db: Annotated[Session, Depends(database.get_db)],
    current_user: Annotated[models.User, Depends(auth.get_current_user)],
    accept_language: Optional[str] = Header(default=None),
) -> schemas.Task:
    """Удалить задачу"""
    lang = i18n.resolve_language(accept_language)
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=i18n.t("task_not_found", lang),
        )

    # Проверяем, что задача принадлежит пользователю
    goal = db.query(models.Goal).filter(models.Goal.id == db_task.goal_id, models.Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=i18n.t("not_authorized", lang),
        )

    db.delete(db_task)
    db.commit()
    return db_task
