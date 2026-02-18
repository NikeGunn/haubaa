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
