---

name: database
description: Design and review database access for FastAPI applications using SQLAlchemy or SQLModel with correct sessions, transactions, queries, indexes, migrations, and PostgreSQL or SQLite compatibility.
compatibility: opencode
metadata:
  database: sqlalchemy-sqlmodel
  level: senior
-------------

# Database Engineering

Act as a senior database/backend engineer.

## Session Management

Use the project's established session dependency.

Never create uncontrolled global sessions.

Ensure sessions are properly closed.

## Transactions

Define clear transaction boundaries.

Avoid partially completed operations.

For multi-step writes, consider transaction consistency.

## Queries

Inspect generated queries where performance matters.

Look for:

* N+1 queries
* unnecessary queries
* repeated queries
* loading unnecessary columns
* missing indexes
* inefficient filtering

## Relationships

Use appropriate loading strategies.

Do not eagerly load large relationships without a reason.

## Indexes

Consider indexes for:

* frequently filtered columns
* foreign keys
* unique constraints
* frequently sorted columns

Do not create indexes blindly.

Consider write overhead.

## Migrations

Never silently recreate the database.

Database schema changes should use the project's migration mechanism.

For production migrations:

* consider existing data
* consider backward compatibility
* consider rollback
* consider migration ordering

## SQLite / PostgreSQL

When supporting both databases:

Check for differences in:

* SQL syntax
* data types
* concurrency
* locking
* indexes
* transaction behavior

Do not assume SQLite behavior represents PostgreSQL behavior.
