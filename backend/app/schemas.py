from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class User(BaseModel):
    id: int
    email: str

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    is_completed: bool


class Task(TaskBase):
    id: int
    is_completed: bool
    goal_id: int

    # Новый стандарт Pydantic v2 вместо class Config
    model_config = ConfigDict(from_attributes=True)


class GoalBase(BaseModel):
    title: str
    description: Optional[str] = None


class GoalCreate(GoalBase):
    pass


class Goal(GoalBase):
    id: int
    is_completed: bool
    tasks: List[Task] = []

    # Новый стандарт Pydantic v2 вместо class Config
    model_config = ConfigDict(from_attributes=True)


class GoalAnalysis(BaseModel):
    analysis: str
    proposed_tasks: List[str]
