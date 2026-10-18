---

name: observability
description: Implement production observability for FastAPI applications using structured logging, metrics, tracing, health checks, request correlation, and operational diagnostics.
compatibility: opencode
metadata:
  domain: observability
  level: senior
-------------

# Observability

Design applications that can be diagnosed in production.

## Logging

Prefer structured logging.

Include useful context such as:

* request ID
* operation
* user ID when appropriate
* resource ID
* duration
* error information

Never log secrets.

## Health Checks

Distinguish between:

```text
Liveness
Readiness
```

Liveness should determine whether the process is alive.

Readiness should determine whether the application can serve traffic.

## Metrics

Useful metrics can include:

* request count
* latency
* error rate
* database latency
* background-job duration
* queue depth
* external service failures

## Tracing

When distributed systems are involved, consider distributed tracing.

Preserve correlation IDs across service boundaries.

## Diagnostics

Production errors should contain enough context to identify:

* what failed
* where it failed
* when it failed
* correlation/request ID

Do not expose internal diagnostics to API clients.
