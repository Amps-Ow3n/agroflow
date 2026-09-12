# Feature 21 — Security, Privacy & Operational Controls

Security chain: authentication → active user → membership → verified organization → responsibility → permission → resource authorization.

Controls implemented: password hashing, JWT validation, HttpOnly session cookies, CSRF protection, organization/resource isolation, controlled evidence access, path traversal prevention, upload limits/allowlists, rate limiting for login/registration, security headers, sanitized error logging, privacy notice/access endpoint, and security tests.

The frontend is not treated as a security boundary; authorization is enforced server-side.

Phase A rate limiting is process-local and must be replaced by a shared limiter before horizontal scaling.
