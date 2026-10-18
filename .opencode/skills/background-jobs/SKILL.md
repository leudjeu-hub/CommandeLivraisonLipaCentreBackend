---

name: background-jobs
description: Design reliable background processing for FastAPI applications including scheduled tasks, queues, retries, idempotency, long-running jobs, and failure handling.
compatibility: opencode
metadata:
  domain: background-processing
  level: senior
-------------

# Background Jobs

Use background processing when work should not block an HTTP request.

## Suitable workloads

Consider background processing for:

* long-running calculations
* file processing
* report generation
* external API synchronization
* notifications
* scheduled processing

## Important

Do not assume FastAPI BackgroundTasks are suitable for durable production jobs.

For critical or long-running workloads consider a proper worker/queue architecture.

## Jobs

Jobs should preferably be:

* idempotent
* observable
* retryable
* resumable where appropriate

## Failure Handling

Define:

* retry strategy
* maximum retries
* dead-letter behavior where appropriate
* logging
* monitoring

## Concurrency

Avoid running duplicate jobs accidentally.

Use locking or idempotency mechanisms when required.

## Database

Do not leave transactions open while performing long external operations.
