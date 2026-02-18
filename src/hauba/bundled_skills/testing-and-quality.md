# Skill: testing-and-quality

## Capabilities
- Test strategy design across the full testing pyramid
- Unit testing with mocking, fixtures, and parameterized tests
- Integration testing for APIs, databases, and external services
- End-to-end testing with browser automation
- Test-driven development (TDD) workflow
- Code coverage analysis and quality metrics

## When To Use
- Writing tests for new or existing functionality
- Setting up a testing framework or CI test pipeline
- Improving code coverage or test reliability
- Task mentions "test", "TDD", "coverage", "quality", "unit test", "integration test"

## Approach

### Phase 1: Understand
- Identify what needs testing and the risk profile
- Map dependencies that need mocking vs real integration
- Determine the testing framework and tooling already in use
- Review existing test patterns in the codebase

### Phase 2: Plan
- Prioritize: test critical paths and edge cases first
- Design test fixtures for common setup and teardown
- Plan mock strategies for external dependencies
- Set coverage targets per module

### Phase 3: Execute
- Write tests following Arrange-Act-Assert pattern
- Create reusable fixtures for database, API clients, and configs
- Mock external dependencies at the boundary, not deep inside
- Use parameterized tests for input variations
- Add integration tests for cross-module workflows
- Configure coverage reporting in CI

### Phase 4: Verify
- Run full test suite and confirm all tests pass
- Check coverage report for untested critical paths
- Verify tests are deterministic (no flaky tests)
- Ensure tests run in isolation (no shared mutable state)

## Constraints
- Tests must be deterministic — no reliance on timing or external state
- Never test implementation details; test behavior and contracts
- Mock at boundaries, not deep in the call stack
- Each test should test one thing with a clear assertion
- Keep test execution fast — mock slow operations in unit tests

## Scale Considerations
- Organize tests into fast (unit) and slow (integration) suites
- Run unit tests on every commit, integration tests on PR/merge
- Use test parallelization for large test suites
- Implement test data factories instead of hardcoded fixtures

## Error Recovery
- Flaky test: isolate, add logging, fix root cause (timing, state leakage)
- Slow test suite: profile, split into parallel shards, mock slow deps
- Coverage drop: identify uncovered paths, prioritize by risk
- Test environment issues: use containers or in-memory databases for isolation
