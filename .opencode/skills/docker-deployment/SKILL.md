---

name: docker-deployment
description: Containerize and deploy FastAPI applications with production-ready Docker images, environment configuration, health checks, security, and CI/CD practices.
compatibility: opencode
metadata:
  domain: deployment
  framework: docker-fastapi
  level: senior
-------------

# Docker and Deployment

Design production-ready container deployments.

## Dockerfile

Prefer:

* minimal base images
* multi-stage builds where useful
* non-root users
* deterministic dependencies
* appropriate `.dockerignore`

Do not include:

* secrets
* local development files
* `.git`
* caches

## Configuration

Inject configuration through environment variables or the deployment platform.

Do not bake secrets into images.

## Runtime

The container should run the application using the project's production ASGI configuration.

Do not use development reload mode in production.

## Health

Provide appropriate health/readiness endpoints when required.

## CI/CD

A production pipeline should consider:

```text
Build
 ↓
Test
 ↓
Security checks
 ↓
Build image
 ↓
Scan image
 ↓
Deploy
 ↓
Health check
```

## Deployment

Before changing deployment configuration:

1. Inspect the existing CI/CD pipeline.
2. Inspect Docker configuration.
3. Inspect environment variables.
4. Preserve existing deployment assumptions.

Do not make destructive infrastructure changes without explicit approval.
