# Skill: full-stack-engineering

## Capabilities
- End-to-end application architecture from requirements to deployment
- Backend API design with database schema and authentication
- Frontend UI implementation with responsive design and state management
- Monorepo and microservice project structure setup
- Full testing pyramid: unit, integration, E2E
- Production deployment configuration with CI/CD

## When To Use
- Building a complete web application or SaaS product
- Creating a full-stack project from scratch
- Setting up a new service with both API and UI layers
- Task mentions "build", "create app", "full-stack", "SaaS", "web application"

## Approach

### Phase 1: Understand
- Identify core entities, user roles, and business workflows
- Map data relationships and access patterns
- Determine technology constraints (language, framework, hosting)
- Clarify authentication and authorization requirements

### Phase 2: Plan
- Design database schema with migrations strategy
- Define API contract (endpoints, request/response shapes)
- Plan frontend page structure and component hierarchy
- Set up project structure: monorepo vs separate repos
- Choose patterns: MVC, Clean Architecture, or Domain-Driven Design

### Phase 3: Execute
- Scaffold project with package manager, linter, formatter configs
- Implement database models and migration scripts
- Build API endpoints with input validation and error handling
- Create frontend pages, components, and API client
- Add authentication flow (signup, login, session/JWT management)
- Write tests at each layer

### Phase 4: Verify
- Run full test suite and check coverage
- Verify API responses match contract
- Test authentication and authorization edge cases
- Validate frontend renders correctly and handles error states
- Check for OWASP Top 10 vulnerabilities

## Constraints
- Never store secrets in source code or environment files committed to git
- Always use parameterized queries — never string-concatenate SQL
- Validate all user input on both client and server side
- Use HTTPS in production; set secure cookie flags
- Follow the principle of least privilege for database users and API scopes

## Scale Considerations
- For 100K+ line codebases, modularize into bounded contexts or packages
- Use database connection pooling and query optimization early
- Implement caching at API layer for read-heavy endpoints
- Plan for horizontal scaling: stateless services, external session store
- Use feature flags for gradual rollout of new functionality

## Error Recovery
- Database migration failure: roll back transaction, fix schema, retry
- Build failure: check dependency versions, clear caches, rebuild
- Authentication flow broken: verify token signing keys and expiry config
- Frontend build errors: check TypeScript types, missing imports, CSS conflicts
