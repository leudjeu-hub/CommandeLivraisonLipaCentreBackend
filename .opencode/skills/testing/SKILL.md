---

name: testing
description: Create and maintain professional pytest test suites for FastAPI applications including API, service, repository, integration, async, database, and authentication tests.
compatibility: opencode
metadata:
framework: pytest
level: senior
-------------

# Testing

Use pytest.

## Test Layers

Prefer appropriate levels:

```text
Unit Tests
    ↓
Service Tests
    ↓
Repository Tests
    ↓
API Tests
    ↓
Integration Tests
```

Do not make every test an API integration test.

## API Tests

Test:

* status codes
* response schemas
* validation
* authentication
* authorization
* error responses

## Service Tests

Test business rules independently from HTTP.

## Database Tests

Use isolated test databases or transactions.

Never run destructive tests against production databases.

## Fixtures

Reuse existing fixtures.

Avoid duplicated fixture setup.

Keep fixtures understandable.

## Test Cases

Cover:

* happy path
* invalid input
* boundary values
* missing resources
* conflicts
* authorization failures
* database errors where relevant

## Async

Use the project's established async testing strategy.

Do not mix sync and async test clients incorrectly.

## Completion

After implementation:

1. Run targeted tests.
2. Run the complete test suite when practical.
3. Investigate failures.
4. Never remove tests merely to make the suite pass.

Never claim tests passed unless they were actually executed.
