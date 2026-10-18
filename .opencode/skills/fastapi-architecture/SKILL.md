---

name: fastapi-architecture
description: Design and implement maintainable FastAPI applications using clean separation between API routes, dependencies, services, repositories, schemas, models, and infrastructure.
compatibility: opencode
metadata:
    framework: fastapi
    language: python
    level: senior
-------------

# FastAPI Architecture

Act as a senior Python/FastAPI architect.

## Principles

Prefer a clear separation of:

```text
API Layer
    ↓
Dependencies
    ↓
Service Layer
    ↓
Repository Layer
    ↓
Database / External Services
```

Keep route handlers thin.

Routes should handle:

* HTTP concerns
* dependency injection
* request validation
* calling services
* response generation

Business logic belongs in services.

Database access belongs in repositories when the project uses a repository abstraction.

## Before changing architecture

1. Inspect the existing project.
2. Identify the current architecture.
3. Find similar implementations.
4. Reuse established patterns.
5. Avoid unnecessary rewrites.

Do not introduce Clean Architecture, CQRS, repositories, factories, or other abstractions merely for theoretical purity.

Prefer the simplest architecture that fits the project.

## Dependency Injection

Use FastAPI dependency injection for:

* database sessions
* authentication
* authorization
* services
* repositories
* configuration

Avoid creating global database sessions.

## Maintainability

Prefer:

* small focused modules
* explicit dependencies
* type hints
* dependency inversion where useful
* testable business logic
* clear boundaries

Avoid:

* fat route handlers
* global mutable state
* hidden dependencies
* circular imports
* unnecessary abstractions
* duplicated business logic

## Changes

When implementing a feature:

1. Inspect existing architecture.
2. Identify affected layers.
3. Implement the smallest appropriate change.
4. Add tests.
5. Verify compatibility with existing APIs.
