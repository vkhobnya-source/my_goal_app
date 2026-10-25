from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .task import Task


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

