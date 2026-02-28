# Skill: api-design-and-integration

## Capabilities
- REST, GraphQL, and gRPC API design with OpenAPI specifications
- Authentication flows: OAuth2, JWT, API keys, session-based
- Rate limiting, pagination, filtering, and sorting patterns
- Webhook handling and event-driven integrations
- API versioning strategies and backward compatibility
- Third-party API integration with retries and circuit breakers

## When To Use
- Designing or implementing API endpoints
- Integrating with external services or APIs
- Setting up authentication and authorization
- Task mentions "API", "REST", "GraphQL", "endpoint", "webhook", "OAuth", "integration"

## Approach

### Phase 1: Understand
- Identify resources, operations, and relationships
- Map authentication and authorization requirements
- Determine consumers (web, mobile, third-party) and their needs
- Review rate limiting and quota requirements

### Phase 2: Plan
- Design resource URLs following REST conventions
- Define request/response schemas with OpenAPI or GraphQL SDL
- Plan authentication middleware and token lifecycle
- Design error response format with consistent error codes
- Plan pagination strategy (cursor-based for large datasets)

### Phase 3: Execute
- Implement route handlers with input validation
- Add authentication middleware with proper token verification
- Implement rate limiting per endpoint or per user
- Add pagination, filtering, and sorting support
- Write integration tests for each endpoint
- Generate API documentation from code or spec

### Phase 4: Verify
- Test all HTTP methods and status codes
- Verify authentication rejects invalid tokens
- Test rate limiting triggers correctly
- Validate pagination works with edge cases (empty, single page, last page)
- Check CORS headers are configured correctly

## Constraints
- Always validate and sanitize request input before processing
- Return consistent error format across all endpoints
- Never expose internal error details or stack traces to API consumers
- Use HTTPS for all API traffic; reject plain HTTP
- Version APIs from day one (URL prefix or header)

## Scale Considerations
- Use cursor-based pagination instead of offset for large datasets
- Implement response caching with ETags or Cache-Control headers
- Consider API gateway for cross-cutting concerns (auth, rate limiting, logging)
- Design for idempotency on mutation endpoints using idempotency keys

## Error Recovery
- 5xx errors: check server logs, add retries with exponential backoff
- Authentication failures: verify token signing key rotation
- Rate limit exceeded: implement client-side backoff, request quota increase
- Integration timeout: add circuit breaker, implement fallback behavior

## Playbook: API Development

### Milestone 1: Spec Design
- Identify resources, operations, and relationships
- Design URL structure following REST conventions
- Write OpenAPI specification with request/response schemas
- Define authentication and authorization requirements

### Milestone 2: Models
- Implement database models from the spec
- Create migration scripts
- Add model validation and serialization
- Set up database connection with pooling

### Milestone 3: Endpoints
- Implement CRUD handlers for each resource
- Add input validation and error handling
- Implement pagination, filtering, and sorting
- Add request/response logging middleware

### Milestone 4: Auth
- Implement authentication middleware (JWT or session)
- Add role-based access control per endpoint
- Implement rate limiting
- Add CORS configuration

### Milestone 5: Testing
- Write unit tests for business logic
- Write integration tests for each endpoint
- Test authentication and authorization edge cases
- Test error responses and validation messages

### Milestone 6: Documentation
- Generate API documentation from OpenAPI spec
- Add usage examples for each endpoint
- Write deployment and configuration guide
- Set up monitoring and health check endpoints
