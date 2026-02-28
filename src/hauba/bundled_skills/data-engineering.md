# Skill: data-engineering

## Capabilities
- ETL/ELT pipeline design and implementation
- Data modeling for relational and document databases
- SQL query optimization and indexing strategies
- Batch and stream processing architecture
- Data quality validation and schema evolution
- Data warehouse and lake design patterns

## When To Use
- Building data pipelines or ETL workflows
- Designing database schemas or data models
- Optimizing slow queries or data processing
- Task mentions "data pipeline", "ETL", "database", "SQL", "data model", "migration"

## Approach

### Phase 1: Understand
- Map data sources, formats, and volumes
- Identify transformation requirements and business rules
- Determine latency requirements (batch vs real-time)
- Catalog existing schemas and dependencies

### Phase 2: Plan
- Design target schema with normalization/denormalization trade-offs
- Plan transformation logic and validation rules
- Define data quality checks and alerting thresholds
- Design idempotent operations for safe re-runs

### Phase 3: Execute
- Implement source connectors with error handling and retries
- Build transformation logic with clear, testable functions
- Add schema validation at ingestion and output stages
- Implement incremental processing (timestamps, CDC, watermarks)
- Write migration scripts with rollback support

### Phase 4: Verify
- Validate row counts and checksums between source and target
- Test with edge cases: empty data, nulls, duplicates, schema drift
- Verify idempotency: running twice produces same result
- Check performance with realistic data volumes

## Constraints
- Never modify source data in place — always write to new tables/files
- Use transactions for multi-step writes to maintain consistency
- Handle schema evolution gracefully (additive changes preferred)
- Log all data quality violations, do not silently drop records
- Encrypt sensitive data (PII) at rest and in transit

## Scale Considerations
- Partition large tables by date or key range for query performance
- Use columnar formats (Parquet) for analytical workloads
- Implement backpressure for stream processing
- Monitor pipeline lag and set alerts for SLA violations

## Error Recovery
- Pipeline failure mid-run: use checkpoints and resume from last success
- Schema mismatch: validate schema before processing, fail fast
- Data corruption: maintain raw data archive, rebuild from source
- Slow queries: analyze execution plan, add indexes, consider materialized views

## Playbook: Data Pipeline

### Milestone 1: Schema Design
- Catalog source data formats, volumes, and update frequencies
- Design target schema with normalization trade-offs documented
- Define data quality rules and validation constraints
- Plan schema evolution strategy

### Milestone 2: Ingestion
- Build source connectors with retry logic and error handling
- Implement incremental extraction (CDC, watermarks, or timestamps)
- Add schema validation at ingestion boundary
- Log ingestion metrics (records, bytes, duration)

### Milestone 3: Transform
- Implement transformation functions with clear input/output contracts
- Add data cleansing (dedup, null handling, type coercion)
- Apply business rules and derived calculations
- Write unit tests for each transformation

### Milestone 4: Storage
- Implement target writer with transaction support
- Add partition strategy for query performance
- Create indexes for common query patterns
- Implement idempotent writes for safe re-runs

### Milestone 5: Validation
- Implement row count reconciliation between source and target
- Add checksum validation for critical fields
- Build data quality dashboard with pass/fail metrics
- Set up alerting for quality threshold violations

### Milestone 6: Monitoring
- Add pipeline execution logging and metrics
- Configure alerting for failures and SLA breaches
- Write operational runbook with troubleshooting steps
- Test failure recovery and checkpoint resume
