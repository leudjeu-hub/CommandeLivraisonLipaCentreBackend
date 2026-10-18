---
description:  Review the selected code as a senior Python/FastAPI developer.
agent: plan
---

# Senior Code Review

Check for:

## Architecture

- separation of concerns
- dependency injection
- coupling
- SOLID violations
- unnecessary abstractions
- duplicated logic

## Python

- type hints
- Pythonic code
- error handling
- unnecessary complexity
- resource management

## FastAPI

- route design
- dependency injection
- response models
- status codes
- validation
- exception handling

## Database

- inefficient queries
- N+1 queries
- transaction handling
- session lifecycle
- indexes
- unnecessary database calls

## Async

Check for:

- blocking operations
- incorrect async usage
- unnecessary async
- sync/async mixing

## Security

Check for:

- authentication
- authorization
- injection risks
- sensitive information
- insecure configuration

## Testing

Check whether important behavior is covered.

## Output

For every finding provide:

Severity:
File:
Location:
Problem:
Why it matters:
Recommended fix:

Do not report purely stylistic preferences unless they have practical impact.