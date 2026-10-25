# AGENTS.md - Project Notes

## What this is
Goals and Tasks Tracker - full-stack app:
- Backend: FastAPI (backend/app/: main.py, auth.py, database.py, i18n.py, models.py, schemas.py), SQLite / PostgreSQL.
- Frontend: static - frontend/index.html (HTML + inline JS + i18n), frontend/style.css, nginx (default.conf, default.e2e.conf).
- Tests: pytest (tests/test_api.py, tests/test_e2e.py - Selenium, tests/test_playwright.py - Playwright), Cypress (cypress/e2e/goals.cy.js).

## Run
- Dev: docker compose up --build -> frontend http://localhost, backend :8000.
- E2E: docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d backend-e2e frontend-e2e -> frontend http://localhost:8081, backend :8000 (sqlite /tmp/goals-e2e.db).

## Tests
- Backend: python -m pytest tests/test_api.py.
- E2E: python -m pytest tests/test_e2e.py tests/test_playwright.py (frontend: http://localhost:8081).
- Cypress: npx cypress run (baseUrl http://localhost).

## Frontend specifics
- Vanilla JS inline in index.html; i18n via translations (en/ru) + data-i18n, data-i18n-placeholder.
- Dark theme: CSS vars (:root) + [data-theme="dark"]; toggle #theme-toggle_btn; localStorage key theme; prefers-color-scheme fallback.

## AI rules

### FastAPI Coding Standards and Architecture Rules (apply: always)

You are an expert Backend Engineer specializing in FastAPI and modern asynchronous Python. Follow these rules for all code generation, refactoring, and code reviews in this project.

1. **Project Architecture & Routing**
   - **APIRouter**: Always modularize the application using `fastapi.APIRouter`. Group related endpoints into separate router files (e.g., `routers/users.py`, `routers/auth.py`).
   - **Path Prefixes & Tags**: Always provide explicit `prefix` and `tags` when including routers in the main application instance.
   - **RESTful Conventions**: Adhere strictly to REST standards (e.g., `GET /items`, `POST /items`, `GET /items/{item_id}`, `PUT /items/{item_id}`, `DELETE /items/{item_id}`). Use plural nouns for resource paths.

2. **Dependency Injection & Type Hints**
   - **Modern DI Syntax**: Always use `typing.Annotated` for dependency injection. Do not use the deprecated default argument syntax (e.g., use `current_user: Annotated[User, Depends(get_current_user)]` instead of `current_user: User = Depends(get_current_user)`).
   - **Type Safety**: Every router function must have explicit type hints for all parameters and an explicit `response_model` (or return type hint) specified.

3. **Data Validation & Schemas (Pydantic v2)**
   - **Pydantic v2**: Use modern Pydantic v2 syntax. Prefer `Field(..., description="...")` for field validation.
   - **Separation of Concerns**: Strictly separate Pydantic schemas into individual files (e.g., `schemas/user.py`). Create distinct schemas for different operations: `UserCreate`, `UserUpdate`, `UserResponse`. Never return raw database models directly to the client.

4. **Asynchronous & Database Operations**
   - **Async Endpoints**: Define route handlers with `async def` only if they perform non-blocking I/O operations (e.g., async database queries, network requests using `httpx`). Use standard `def` for purely CPU-bound tasks or when using synchronous blocking libraries to prevent thread pool starvation.
   - **SQLAlchemy 2.0+**: If writing database code, use SQLAlchemy 2.0 async syntax (`async_session`). Always use context managers or FastAPI dependencies to ensure database sessions are properly closed (`yield` pattern).

5. **Error Handling & Status Codes**
   - **HTTPException**: Raise `fastapi.HTTPException` for expected operational errors (e.g., 404 Not Found, 400 Bad Request, 401 Unauthorized). Always provide a clear, descriptive JSON-compatible `detail` message.
   - **Explicit Status Codes**: Always define the expected success status code in the decorator if it differs from 200 OK (e.g., `@router.post("/", status_code=status.HTTP_211_CREATED)`). Use `fastapi.status` constants instead of raw integers.

### JavaScript / TypeScript Coding Standards and Rules (apply: always)

You are an expert Frontend and Node.js developer. Always follow these rules when writing JavaScript/TypeScript code:

1. **Code Style & Modern Features**
   - **Standards**: Write clean, modern ECMAScript (ES6+) code.
   - **Variables**: Always use `const` by default. Use `let` only if re-assignment is explicitly required. Never use `var`.
   - **Functions**: Prefer arrow functions (`const myFunc = () => {}`) for callbacks and short methods, but use standard function declarations for top-level component/module definitions.
   - **Modules**: Use ES Modules (`import`/`export`) instead of CommonJS (`require`).

2. **Asynchronous Operations**
   - **Async/Await**: Always prefer `async/await` over raw Promises (`.then()/.catch()`).
   - **Error Handling**: Wrap asynchronous operations in `try/catch` blocks to ensure robust error handling.

3. **DOM & Performance (For Frontend)**
   - **Optional Chaining**: Use optional chaining (`user?.profile?.name`) and nullish coalescing (`??`) to prevent runtime crashes from undefined properties.
   - **Array Methods**: Prefer declarative array methods like `.map()`, `.filter()`, and `.reduce()` over imperative `for` loops.

4. **Quality & Linting**
   - **Linting**: Write code that conforms to standard ESLint rules.
   - **Formatting**: Keep code clean, avoiding trailing spaces and keeping lines under 100 characters.

## Gotchas
- File tools (read/write/edit) can fail with SchemaError - use PowerShell/python to edit files.
- Emoji via bash/PowerShell get mangled - use HTML entities (&#x1F319;) or JS unicode escapes (\uD83C\uDF19).
- Edit CSS/JS via here-string + Set-Content -NoNewline; keep CRLF line endings.
- E2E fixture e2e_stack in tests/conftest.py starts docker compose stack automatically.
