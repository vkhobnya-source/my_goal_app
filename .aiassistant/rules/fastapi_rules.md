---
apply: always
---

# FastAPI Coding Standards and Architecture Rules

You are an expert Backend Engineer specializing in FastAPI and modern asynchronous Python. Follow these rules for all code generation, refactoring, and code reviews in this project.

## 1. Project Architecture & Routing
- **APIRouter**: Always modularize the application using `fastapi.APIRouter`. Group related endpoints into separate router files (e.g., `routers/users.py`, `routers/auth.py`).
- **Path Prefixes & Tags**: Always provide explicit `prefix` and `tags` when including routers in the main application instance.
- **RESTful Conventions**: Adhere strictly to REST standards (e.g., `GET /items`, `POST /items`, `GET /items/{item_id}`, `PUT /items/{item_id}`, `DELETE /items/{item_id}`). Use plural nouns for resource paths.

## 2. Dependency Injection & Type Hints
- **Modern DI Syntax**: Always use `typing.Annotated` for dependency injection. Do not use the deprecated default argument syntax (e.g., use `current_user: Annotated[User, Depends(get_current_user)]` instead of `current_user: User = Depends(get_current_user)`).
- **Type Safety**: Every router function must have explicit type hints for all parameters and an explicit `response_model` (or return type hint) specified.

## 3. Data Validation & Schemas (Pydantic v2)
- **Pydantic v2**: Use modern Pydantic v2 syntax. Prefer `Field(..., description="...")` for field validation.
- **Separation of Concerns**: Strictly separate Pydantic schemas into individual files (e.g., `schemas/user.py`). Create distinct schemas for different operations: `UserCreate`, `UserUpdate`, `UserResponse`. Never return raw database models directly to the client.

## 4. Asynchronous & Database Operations
- **Async Endpoints**: Define route handlers with `async def` only if they perform non-blocking I/O operations (e.g., async database queries, network requests using `httpx`). Use standard `def` for purely CPU-bound tasks or when using synchronous blocking libraries to prevent thread pool starvation.
- **SQLAlchemy 2.0+**: If writing database code, use SQLAlchemy 2.0 async syntax (`async_session`). Always use context managers or FastAPI dependencies to ensure database sessions are properly closed (`yield` pattern).

## 5. Error Handling & Status Codes
- **HTTPException**: Raise `fastapi.HTTPException` for expected operational errors (e.g., 404 Not Found, 400 Bad Request, 401 Unauthorized). Always provide a clear, descriptive JSON-compatible `detail` message.
- **Explicit Status Codes**: Always define the expected success status code in the decorator if it differs from 200 OK (e.g., `@router.post("/", status_code=status.HTTP_211_CREATED)`). Use the `fastapi.status` constants instead of raw integers.
