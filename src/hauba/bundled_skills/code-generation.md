# Skill: code-generation

## Capabilities
- Write production-quality code in Python, JavaScript/TypeScript, Go, Rust, and more
- Apply design patterns: SOLID, DRY, composition over inheritance
- Generate type-safe code with comprehensive error handling
- Create tests alongside implementation code
- Produce well-structured modules with clear separation of concerns

## When To Use
- Writing new functions, classes, or modules from specifications
- Implementing algorithms or business logic
- Generating boilerplate code (models, serializers, routes)
- Task mentions "write code", "implement", "generate", "create function", "add feature"

## Approach

### Phase 1: Understand
- Parse the specification or requirements precisely
- Identify input/output types and edge cases
- Determine which language features and patterns are appropriate
- Check for existing code to integrate with or extend

### Phase 2: Plan
- Choose the right data structures and algorithms
- Design the public API (function signatures, class interfaces)
- Plan error handling strategy (exceptions vs Result types)
- Identify what tests are needed

### Phase 3: Execute
- Write the implementation following language idioms
- Add type annotations / type hints on all public interfaces
- Include input validation at boundaries
- Write docstrings for public APIs
- Implement corresponding unit tests

### Phase 4: Verify
- Run linter and type checker
- Execute tests and confirm they pass
- Review for common anti-patterns
- Check that error messages are descriptive and actionable

## Constraints
- Never use `eval()`, `exec()`, or dynamic code execution with user input
- Always handle nullable/optional values explicitly
- Do not suppress or swallow exceptions without logging
- Avoid mutable global state
- Keep functions under 50 lines; extract helpers for complex logic

## Scale Considerations
- For large modules, split into sub-modules with clear interfaces
- Use lazy imports for expensive dependencies
- Profile hot paths before optimizing
- Prefer generators/iterators over materializing large lists in memory

## Error Recovery
- Type errors: check function signatures and input types
- Import errors: verify package is installed and path is correct
- Logic errors: add logging at decision points, write failing test first
- Performance issues: profile with cProfile/py-spy, optimize the bottleneck
