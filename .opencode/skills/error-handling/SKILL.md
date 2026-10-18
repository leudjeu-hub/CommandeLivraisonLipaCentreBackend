---

name: error-handling
description: Design consistent FastAPI error handling, HTTP exceptions, domain errors, validation responses, logging, and global exception handlers.
compatibility: opencode
metadata:
  framework: fastapi
  level: senior
-------------

# Error Handling

Use consistent error handling throughout the application.

## Layers

Distinguish:

```text
Domain Error
    ↓
Service
    ↓
API Error
    ↓
HTTP Response
```

Do not put HTTP-specific exceptions into low-level repositories unless the architecture explicitly requires it.

## HTTP Errors

Use appropriate status codes.

Do not return generic 500 errors when a meaningful client error exists.

## Validation

Allow FastAPI/Pydantic to handle normal request validation.

Do not duplicate validation unnecessarily.

## Global Handlers

Use global exception handlers when they provide consistency across the application.

Avoid catching every exception and silently hiding the root cause.

## Logging

Log unexpected errors with sufficient diagnostic context.

Never log secrets.

## Client Responses

Error responses should be:

* predictable
* documented
* useful
* free of sensitive information

Do not expose stack traces in production.
