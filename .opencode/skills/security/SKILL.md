---

name: security
description: Secure FastAPI applications against authentication, authorization, injection, insecure object access, secret exposure, unsafe file handling, CORS, and common web vulnerabilities.
compatibility: opencode
metadata:
  domain: application-security
  framework: fastapi
  level: senior
-------------

# FastAPI Security

Act as a senior application-security engineer.

## Authentication

Review:

* password handling
* token handling
* session handling
* token expiration
* refresh mechanisms
* authentication dependencies

Never store plaintext passwords.

## Authorization

Check every protected resource.

Pay particular attention to:

* IDOR
* privilege escalation
* missing ownership checks
* role checks

Authentication does not automatically provide authorization.

## Input Validation

Check for:

* SQL injection
* command injection
* path traversal
* unsafe deserialization
* malicious file uploads

Use parameterized database queries.

## Secrets

Never expose:

* API keys
* passwords
* JWT secrets
* database credentials
* access tokens

Do not print secrets in logs.

## CORS

Review:

* allowed origins
* credentials
* methods
* headers

Avoid unrestricted CORS in production unless explicitly justified.

## Files

For file uploads/downloads check:

* path traversal
* file type validation
* file size limits
* filename handling
* storage isolation

## Error Responses

Do not expose internal stack traces or sensitive implementation details.

## Security Review

Report findings with:

```text
Severity
Location
Issue
Impact
Recommendation
```
