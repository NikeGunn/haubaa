# Skill: refactoring-and-migration

## Capabilities
- Safe large-scale code refactoring with incremental delivery
- Strangler fig pattern for gradual system replacement
- Database migration scripts with rollback support
- API versioning and backward-compatible changes
- Dependency upgrades and breaking change management
- Feature flag driven migrations for zero-downtime transitions

## When To Use
- Refactoring existing code to improve structure or performance
- Migrating between frameworks, databases, or architectures
- Upgrading dependencies with breaking changes
- Task mentions "refactor", "migrate", "upgrade", "restructure", "modernize", "rewrite"

## Approach

### Phase 1: Understand
- Map the current architecture and identify dependencies
- Identify the pain points driving the refactoring
- Catalog all callers and consumers of the code being changed
- Assess test coverage of the affected areas

### Phase 2: Plan
- Design the target state with clear boundaries
- Plan incremental steps (each step is deployable on its own)
- Identify the migration path: parallel run, strangler fig, or big bang
- Define rollback plan for each step
- Ensure adequate test coverage before starting

### Phase 3: Execute
- Add tests for existing behavior before changing anything
- Make one change at a time with passing tests at each step
- Use feature flags to toggle between old and new implementations
- Migrate data with scripts that are idempotent and reversible
- Update documentation and API clients incrementally
- Remove old code only after new code is verified in production

### Phase 4: Verify
- Run full test suite after each incremental change
- Verify backward compatibility for public APIs
- Test rollback procedure works correctly
- Confirm performance is equal or better than before
- Check that no consumers are broken

## Constraints
- Never refactor and add features in the same change
- Always have passing tests before and after each step
- Do not delete old code until new code is verified in production
- Keep each commit small and focused on one logical change
- Maintain backward compatibility unless explicitly breaking (with version bump)

## Scale Considerations
- For 100K+ line refactors, use automated codemods where possible
- Run old and new implementations in parallel to compare outputs
- Use feature flags to gradually shift traffic to new implementation
- Monitor error rates and performance during migration

## Error Recovery
- Migration breaks consumers: revert to previous version, fix compatibility
- Data migration error: restore from backup, fix migration script, re-run
- Performance regression: profile both old and new code, optimize hot paths
- Incomplete migration: maintain compatibility shim until migration is complete

## Playbook: Code Review & Refactor

### Milestone 1: Audit
- Run static analysis and collect code metrics (complexity, duplication, coverage)
- Identify code smells, anti-patterns, and technical debt
- Map dependency graph and circular dependencies
- Document current architecture strengths and weaknesses

### Milestone 2: Identify Debt
- Rank issues by impact (bug risk, maintenance cost, performance)
- Group related issues into refactoring themes
- Estimate effort for each refactoring item
- Create prioritized backlog with justification

### Milestone 3: Plan Refactor
- Design target state for each refactoring theme
- Plan incremental steps (each deployable independently)
- Identify tests needed before refactoring
- Define rollback strategy for each step

### Milestone 4: Execute
- Add test coverage for code being refactored
- Apply refactoring one step at a time with passing tests
- Update documentation and type hints
- Review each step for correctness before proceeding

### Milestone 5: Test
- Run full test suite and confirm all pass
- Verify behavior is unchanged (regression testing)
- Check that performance is equal or better
- Validate API compatibility for public interfaces

### Milestone 6: Measure
- Re-run code metrics and compare with baseline
- Document what was changed and why
- Update architecture documentation
- Record lessons learned for future refactoring
