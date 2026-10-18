---

name: api-design
description: Design robust REST APIs with FastAPI including resources, HTTP methods, status codes, validation, pagination, filtering, versioning, and OpenAPI documentation.
compatibility: opencode
metadata:
framework: fastapi
domain: rest-api
level: senior
-------------

# API Design

Act as a senior REST API engineer.

## Resource Design

Use nouns for resources.

Prefer:

```text
GET    /users
GET    /users/{id}
POST   /users
PUT    /users/{id}
PATCH  /users/{id}
DELETE /users/{id}
```

Avoid action-heavy endpoints unless the operation is genuinely an action.

## HTTP Methods

Use HTTP methods according to their semantics.

* GET: retrieve
* POST: create or execute a non-idempotent operation
* PUT: replace
* PATCH: partial update
* DELETE: remove

## Status Codes

Use appropriate HTTP status codes.

Examples:

```text
200 OK
201 Created
202 Accepted
204 No Content
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
500 Internal Server Error
```

Do not return 200 for every situation.

## Response Models

Define explicit response schemas.

Avoid returning raw ORM/database objects when an API schema is appropriate.

## Pagination

Large collections should support pagination.

Prefer explicit parameters such as:

```text
?page=1&page_size=50
```

or cursor-based pagination where appropriate.

Never load an unbounded database collection into memory.

## Filtering

Use explicit and validated query parameters.

Avoid dynamically constructing SQL from untrusted input.

## Compatibility

Before changing an endpoint:

1. Inspect existing callers.
2. Inspect tests.
3. Inspect OpenAPI schemas.
4. Check whether clients depend on the current response.

Avoid breaking API contracts unnecessarily.
