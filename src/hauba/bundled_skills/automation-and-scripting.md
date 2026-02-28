# Skill: automation-and-scripting

## Capabilities
- System automation scripts (file management, backups, monitoring)
- Batch processing workflows (rename, convert, organize files)
- Scheduled task creation (cron jobs, Windows Task Scheduler)
- CLI tool development with argument parsing
- Process management and monitoring scripts
- Environment setup and configuration automation
- Cross-platform scripting (Windows, macOS, Linux)

## When To Use
- Automating repetitive system tasks
- Creating batch processing scripts
- Building CLI tools or utility scripts
- Task mentions "automate", "script", "batch", "cron", "schedule", "CLI tool", "utility"

## Tools Required
- click or typer (for CLI tools)
- schedule (for task scheduling)

## Approach

### Phase 1: Understand
- Identify the manual process to be automated
- Map inputs, outputs, and error conditions
- Determine execution environment (OS, permissions, scheduling)
- Check for existing tools or scripts that partially solve the problem

### Phase 2: Plan
- Design the script workflow (input → validate → process → output)
- Plan error handling and logging strategy
- Define CLI arguments and configuration options
- Plan idempotency (safe to run multiple times)

### Phase 3: Execute
- Write the script with clear argument parsing
- Implement input validation and sanity checks
- Add comprehensive logging (structured, with timestamps)
- Handle errors gracefully with descriptive messages
- Make operations idempotent where possible
- Add dry-run mode for destructive operations

### Phase 4: Verify
- Test with expected inputs and verify outputs
- Test with edge cases (empty input, missing files, permissions)
- Verify error handling produces useful messages
- Test dry-run mode does not modify anything
- Confirm script runs on target platform

## Constraints
- Always validate user input before processing
- Use absolute paths for file operations in scheduled tasks
- Add dry-run mode for any destructive operations (delete, move, overwrite)
- Log all actions with timestamps for audit trail
- Handle keyboard interrupts gracefully (cleanup resources)

## Scale Considerations
- For large file operations, show progress indicators
- Use multiprocessing for CPU-bound batch operations
- Implement checkpointing for long-running batch jobs
- Use configuration files for complex parameter sets

## Error Recovery
- Permission denied: check file/directory permissions, suggest fix
- File not found: validate paths before processing, show expected location
- Process crash: implement signal handlers and cleanup hooks
- Partial completion: use checkpoints to resume from last success
