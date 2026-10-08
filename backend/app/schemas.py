from pydantic import BaseModel, ConfigDict
from typing import Optional, List


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
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class GoalAnalysis(BaseModel):
    analysis: str
    proposed_tasks: List[str]


# User schemas
class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    goals: List[Goal] = []

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None

