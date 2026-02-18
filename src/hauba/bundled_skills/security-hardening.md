# Skill: security-hardening

## Capabilities
- OWASP Top 10 vulnerability prevention and remediation
- Input validation and output encoding strategies
- Secrets management and secure configuration
- Dependency auditing and vulnerability scanning
- Content Security Policy and HTTP security headers
- Rate limiting and brute-force protection

## When To Use
- Securing an application against common attack vectors
- Auditing code for security vulnerabilities
- Implementing authentication or authorization systems
- Task mentions "security", "vulnerability", "OWASP", "hardening", "audit", "XSS", "SQL injection"

## Approach

### Phase 1: Understand
- Identify the application's attack surface (user input points, APIs, file uploads)
- Review authentication and session management implementation
- Catalog third-party dependencies and their known vulnerabilities
- Map data flow for sensitive information (passwords, tokens, PII)

### Phase 2: Plan
- Prioritize vulnerabilities by exploitability and impact
- Plan input validation strategy (allowlist over denylist)
- Design secrets management (environment variables, vault, encrypted config)
- Define security headers for all HTTP responses

### Phase 3: Execute
- Add input validation on all user-facing endpoints
- Implement parameterized queries for all database access
- Set HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- Configure rate limiting on authentication and sensitive endpoints
- Add dependency vulnerability scanning to CI pipeline
- Implement proper error handling that never leaks internal details

### Phase 4: Verify
- Run dependency audit (npm audit, pip-audit, cargo audit)
- Test for SQL injection, XSS, CSRF on all input points
- Verify authentication bypass is not possible
- Check that secrets are not in logs, error messages, or version control
- Validate Content Security Policy blocks inline scripts

## Constraints
- Never store passwords in plaintext — use bcrypt, scrypt, or argon2
- Never trust client-side validation alone; always validate server-side
- Never log sensitive data (passwords, tokens, credit card numbers)
- Use constant-time comparison for secrets and tokens
- Always use HTTPS in production with proper TLS configuration

## Scale Considerations
- Implement centralized security middleware rather than per-endpoint checks
- Use Web Application Firewall (WAF) for additional protection layer
- Monitor failed authentication attempts and implement account lockout
- Rotate secrets and API keys on a regular schedule

## Error Recovery
- Vulnerability discovered in production: assess impact, patch immediately, rotate affected credentials
- Dependency vulnerability: update to patched version, or apply workaround if no patch exists
- Brute-force attempt detected: enable rate limiting, notify administrators
- Data breach: follow incident response plan, notify affected users
