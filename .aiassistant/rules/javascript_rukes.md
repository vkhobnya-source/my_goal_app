---
apply: always
---

# JavaScript / TypeScript Coding Standards and Rules

You are an expert Frontend and Node.js developer. Always follow these rules when writing JavaScript/TypeScript code:

## 1. Code Style & Modern Features
- **Standards**: Write clean, modern ECMAScript (ES6+) code. 
- **Variables**: Always use `const` by default. Use `let` only if re-assignment is explicitly required. Never use `var`.
- **Functions**: Prefer arrow functions (`const myFunc = () => {}`) for callbacks and short methods, but use standard function declarations for top-level component/module definitions.
- **Modules**: Use ES Modules (`import`/`export`) instead of CommonJS (`require`).

## 2. Asynchronous Operations
- **Async/Await**: Always prefer `async/await` over raw Promises (`.then()/.catch()`).
- **Error Handling**: Wrap asynchronous operations in `try/catch` blocks to ensure robust error handling.

## 3. DOM & Performance (For Frontend)
- **Optional Chaining**: Use optional chaining (`user?.profile?.name`) and nullish coalescing (`??`) to prevent runtime crashes from undefined properties.
- **Array Methods**: Prefer declarative array methods like `.map()`, `.filter()`, and `.reduce()` over imperative `for` loops.

## 4. Quality & Linting
- **Linting**: Write code that conforms to standard ESLint rules. 
- **Formatting**: Keep code clean, avoiding trailing spaces and keeping lines under 100 characters.
