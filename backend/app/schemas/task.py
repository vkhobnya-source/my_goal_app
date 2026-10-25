from typing import Optional

from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    title: str


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    is_completed: Optional[bool] = None
    title: Optional[str] = None


class Task(TaskBase):
    id: int
    is_completed: bool
    goal_id: int

    model_config = ConfigDict(from_attributes=True)

