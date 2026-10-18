---
description:  GHIS - Implement the requested feature in the existing FastAPI project.
agent: build
---

# Implement Feature

Implement the requested feature in the existing FastAPI project.

## Before coding

1. Inspect the existing architecture.
2. Find similar functionality.
3. Identify affected modules.
4. Check existing tests.
5. Reuse existing patterns.

Do not introduce a new architectural pattern unless necessary.

## Implementation

Follow the existing architecture:

API
→ Service
→ Repository
→ Database

Keep FastAPI route handlers thin.

Use:

- dependency injection
- Pydantic schemas
- type hints
- existing error handling
- existing logging
- existing configuration

## Tests

Add or update tests for:

- happy path
- validation errors
- not found
- business-rule errors
- relevant edge cases

## Validation

After implementation:

1. Run tests.
2. Run linting/formatting if configured.
3. Check the git diff.
4. Check for unrelated modifications.

Do not create a git commit.

## Final response

Report:

- files changed
- implementation summary
- tests added
- commands executed
- remaining issues