import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database, models
from .routers.auth import router as auth_router
from .routers.goals import router as goals_router
from .routers.tasks import router as tasks_router

# Автоматически создаем таблицы при запуске
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Goals & Tasks Tracker API")

# Настройка CORS — доверенные origins задаются через переменную окружения
origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== API ROUTERS ====================

app.include_router(auth_router)
app.include_router(goals_router)
app.include_router(tasks_router)
