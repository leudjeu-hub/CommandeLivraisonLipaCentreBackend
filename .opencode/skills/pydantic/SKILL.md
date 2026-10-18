---

name: pydantic
description: Build robust Pydantic v2 schemas for FastAPI request validation, response serialization, configuration, nested models, and domain data validation.
compatibility: opencode
metadata:
  framework: pydantic-v2
  level: senior
-------------

# Pydantic

Use Pydantic v2 patterns.

## Schemas

Separate API schemas from database models when appropriate.

Typical structure:

```text
UserCreate
UserUpdate
UserResponse
UserListResponse
```

Do not expose database implementation details unnecessarily.

## Validation

Validate data at the API boundary.

Prefer declarative validation.

Avoid duplicating identical validation rules across routes and services.

## Serialization

Use explicit response models.

Check:

* optional fields
* nullability
* nested objects
* aliases
* serialization behavior

## Updates

Use appropriate partial-update semantics.

Do not accidentally overwrite existing values when implementing PATCH behavior.

## Configuration

Use Pydantic Settings or the project's established configuration mechanism.

Never hard-code:

* passwords
* API keys
* database credentials
* secrets

## Compatibility

Use Pydantic v2 APIs.

Do not introduce deprecated Pydantic v1 patterns into a v2 project.
