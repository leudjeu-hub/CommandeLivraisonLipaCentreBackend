---

name: async-performance
description: Analyze and optimize FastAPI performance, async I/O, database access, serialization, concurrency, CPU-bound workloads, caching, and large data processing.
compatibility: opencode
metadata:
  domain: performance
  framework: fastapi
  level: senior
-------------

# Async and Performance

Optimize based on evidence.

Do not introduce complexity without a measurable reason.

## Async

Use async when the underlying operation is asynchronous.

Watch for blocking operations inside async endpoints:

* file I/O
* synchronous HTTP clients
* synchronous database operations
* CPU-heavy processing

Do not make CPU-bound code async merely by adding `async`.

## Database

Look for:

* N+1 queries
* repeated queries
* missing indexes
* unnecessary serialization
* excessive database round trips

## Large Data

For large files or datasets prefer:

* streaming
* batching
* pagination
* incremental processing

Avoid loading very large datasets into memory unnecessarily.

## JSON

For large JSON files:

* avoid repeated parsing
* process only required data
* consider incremental processing where appropriate
* avoid unnecessary transformations

## Caching

Introduce caching only when:

1. There is a measurable bottleneck.
2. Cache invalidation is understood.
3. Consistency requirements are defined.

## Performance Changes

For every optimization explain:

* current bottleneck
* evidence
* proposed change
* expected benefit
* trade-offs

Do not optimize speculative micro-benchmarks at the expense of maintainability.
