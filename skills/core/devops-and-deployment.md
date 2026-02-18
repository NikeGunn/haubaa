# Skill: devops-and-deployment

## Capabilities
- Docker containerization and multi-stage builds
- CI/CD pipeline configuration (GitHub Actions, GitLab CI)
- Kubernetes deployment manifests and Helm charts
- Monitoring and alerting setup (Prometheus, Grafana)
- Secrets management and environment configuration
- Zero-downtime deployment strategies (blue-green, canary, rolling)

## When To Use
- Setting up deployment infrastructure for a project
- Creating or modifying CI/CD pipelines
- Containerizing an application with Docker
- Task mentions "deploy", "Docker", "CI/CD", "Kubernetes", "monitoring", "infrastructure"

## Approach

### Phase 1: Understand
- Identify the application stack and runtime requirements
- Determine deployment target (cloud, VPS, serverless, on-prem)
- Map environment configurations (dev, staging, production)
- Review current deployment process and pain points

### Phase 2: Plan
- Design Dockerfile with minimal image size (multi-stage builds)
- Plan CI/CD stages: lint, test, build, deploy
- Define environment variables and secrets management approach
- Choose deployment strategy based on uptime requirements
- Plan monitoring dashboards and alert thresholds

### Phase 3: Execute
- Write Dockerfile with proper layer caching and security hardening
- Configure CI/CD pipeline with parallel stages where possible
- Set up environment-specific configuration files
- Implement health check endpoints for orchestrator probes
- Configure logging aggregation and metrics collection
- Write deployment scripts or Kubernetes manifests

### Phase 4: Verify
- Build and run container locally to verify it works
- Run CI pipeline on a test branch
- Verify health checks return correct status
- Test rollback procedure works correctly
- Confirm monitoring captures key metrics

## Constraints
- Never hardcode secrets in Dockerfiles, CI configs, or source code
- Always pin dependency versions in production images
- Run containers as non-root user
- Use specific image tags, never `latest` in production
- Keep CI pipeline under 10 minutes for fast feedback

## Scale Considerations
- Use horizontal pod autoscaling based on CPU/memory or custom metrics
- Implement resource limits and requests for containers
- Set up log rotation to prevent disk exhaustion
- Use CDN for static assets to reduce origin server load

## Error Recovery
- Build failure: check dependency versions, clear CI cache, rebuild
- Deployment rollback: use deployment history to revert to last known good
- Container crash loop: check logs, verify health check, review resource limits
- Certificate expiry: automate renewal with cert-manager or Let's Encrypt
