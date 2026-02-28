# Skill: data-processing

## Capabilities
- Data analysis with pandas/polars (load, transform, aggregate)
- CSV, Excel, JSON, Parquet file processing
- Statistical analysis and summary statistics
- Data visualization (matplotlib, plotly, seaborn)
- Data cleaning (missing values, duplicates, type conversion)
- Pivot tables, groupby operations, and time series analysis
- Export to various formats (CSV, Excel, HTML, PDF reports)

## When To Use
- Analyzing or processing data files (CSV, Excel, JSON)
- Creating charts, graphs, or data visualizations
- Generating statistical reports or summaries
- Task mentions "data", "CSV", "Excel", "analyze", "chart", "graph", "statistics", "pandas"

## Tools Required
- pandas
- matplotlib
- openpyxl (for Excel)

## Approach

### Phase 1: Understand
- Identify data source format, size, and structure
- Determine analysis goals (summary stats, trends, comparisons)
- Check for data quality issues (missing values, inconsistent types)
- Clarify output requirements (charts, tables, reports)

### Phase 2: Plan
- Design the data processing pipeline (load → clean → transform → analyze → visualize)
- Choose appropriate aggregation methods
- Select visualization types for the data story
- Plan memory management for large datasets

### Phase 3: Execute
- Install pandas and visualization libraries if needed
- Load data with appropriate parser (csv, excel, json, parquet)
- Clean data: handle missing values, fix types, remove duplicates
- Perform analysis: groupby, pivot, statistics, correlations
- Create visualizations with clear labels, titles, and legends
- Export results in requested format

### Phase 4: Verify
- Check row counts match expectations (no unintended drops)
- Validate statistical results with sanity checks
- Ensure charts render correctly and are readable
- Confirm exported files are complete and well-formatted

## Constraints
- Always inspect data shape and dtypes before processing
- Handle missing values explicitly (never silently drop rows)
- Use appropriate statistical methods for the data distribution
- Label all chart axes, include units where applicable
- Use consistent date/time parsing (specify format explicitly)

## Scale Considerations
- For files > 500MB, use chunked reading with pandas
- Consider polars for better performance on large datasets
- Use categorical dtypes for columns with few unique values
- Prefer vectorized operations over iterating rows

## Error Recovery
- Encoding errors: try utf-8, then latin-1, then detect with chardet
- Memory error: use chunked processing or downsample
- Parse errors: specify column types explicitly, handle malformed rows
- Missing library: install on-demand with pip
