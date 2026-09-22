import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Если задана переменная окружения, берем путь из неё (для Docker-контейнера backend),
# иначе создаем базу локально в текущей папке проекта (для тестов и локального запуска)
if os.environ.get("RUNNING_IN_DOCKER_BACKEND") == "true":
    SQLALCHEMY_DATABASE_URL = "sqlite:////data/goals.db"
    # Гарантируем наличие папки
    os.makedirs("/data", exist_ok=True)
else:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./goals.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
