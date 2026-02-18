# Skill: debugging-and-repair

## Capabilities
- Systematic root-cause analysis for software bugs
- Stack trace parsing and error message interpretation
- Binary search bisection to isolate regressions
- Memory leak detection and resource cleanup
- Log analysis and correlation across services
- Reproducing bugs with minimal test cases

## When To Use
- Fixing a reported bug or unexpected behavior
- Investigating errors, crashes, or performance regressions
- Analyzing stack traces or error logs
- Task mentions "fix", "debug", "broken", "error", "crash", "bug", "not working"

## Approach

### Phase 1: Understand
- Read the bug report: expected vs actual behavior
- Identify the affected component and recent changes
- Gather error messages, stack traces, and logs
- Determine reproducibility: always, intermittent, environment-specific

### Phase 2: Plan
- Form hypotheses ranked by likelihood
- Identify the minimal reproduction path
- Plan diagnostic steps: add logging, write a failing test
- Determine if git bisect can isolate the introducing commit

### Phase 3: Execute
- Write a failing test that demonstrates the bug
- Add targeted logging or breakpoints at the hypothesis location
- Trace execution flow from trigger to failure point
- Isolate the root cause (distinguish symptoms from cause)
- Implement the fix with minimal code changes
- Verify the failing test now passes

### Phase 4: Verify
- Run full test suite to confirm no regressions
- Test edge cases related to the fix
- Verify in the same environment where the bug was reported
- Check that error handling is now correct, not just suppressed

## Constraints
- Never apply a fix without understanding the root cause
- Do not suppress errors or add blind try/except to mask issues
- Always write a regression test before marking the bug fixed
- Keep fixes minimal — do not refactor surrounding code in a bug fix
- Document the root cause in the commit message

## Scale Considerations
- In large codebases, use git blame and git log to find recent changes
- For distributed systems, correlate logs across services using request IDs
- Memory leaks: use profilers (memray, tracemalloc) not guesswork
- For intermittent bugs, add structured logging and analyze patterns

## Error Recovery
- Fix causes new failures: revert and re-analyze
- Cannot reproduce: gather more data, check environment differences
- Root cause is in a dependency: file upstream issue, apply workaround with comment
- Performance regression: benchmark before and after with reproducible workload
