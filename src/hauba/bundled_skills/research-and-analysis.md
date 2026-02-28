# Skill: research-and-analysis

## Capabilities
- Web research and information synthesis from multiple sources
- Technology evaluation and comparison matrices
- Codebase analysis and architecture documentation
- Competitive analysis and market research
- Knowledge extraction from documentation and code
- Report writing with structured findings and recommendations

## When To Use
- Evaluating technologies, libraries, or approaches before implementation
- Analyzing an existing codebase to understand architecture
- Researching best practices for a specific domain
- Task mentions "research", "analyze", "evaluate", "compare", "investigate", "document"

## Approach

### Phase 1: Understand
- Define the research question or analysis objective precisely
- Identify what decisions depend on this research
- Determine scope boundaries and time constraints
- List known starting points and existing knowledge

### Phase 2: Plan
- Identify authoritative sources for the domain
- Design comparison criteria and evaluation framework
- Plan information gathering strategy (docs, code, articles, benchmarks)
- Define output format (report, comparison table, recommendation)

### Phase 3: Execute
- Gather information from primary sources (official docs, source code)
- Cross-reference findings across multiple sources
- Build comparison matrices with consistent criteria
- Document trade-offs, not just advantages
- Synthesize findings into actionable recommendations
- Include evidence and references for all claims

### Phase 4: Verify
- Check that all claims have supporting evidence
- Verify information is current (check dates, version numbers)
- Confirm recommendations align with the original question
- Review for bias toward familiar technologies

## Constraints
- Cite sources for all factual claims
- Distinguish between facts and opinions clearly
- Do not recommend without stating trade-offs
- Verify version compatibility before recommending libraries
- Acknowledge uncertainty when evidence is limited

## Scale Considerations
- For large codebases, use automated tools (dependency graphs, code metrics) before manual review
- Prioritize depth on the most impactful decisions
- Create reusable evaluation templates for recurring analysis types
- Maintain a knowledge base of previous research findings

## Error Recovery
- Contradictory sources: note the disagreement, prefer primary sources
- Outdated information: check release dates, look for newer alternatives
- Analysis paralysis: set a timebox, make a recommendation with stated confidence level
- Missing information: document what is unknown and how it affects the recommendation

## Playbook: Research & Prototype

### Milestone 1: Define Question
- Clarify the research objective and what decisions it informs
- Define scope boundaries and constraints
- List known starting points and existing knowledge
- Establish evaluation criteria for candidate solutions

### Milestone 2: Gather Sources
- Search official documentation and primary sources
- Review existing implementations and case studies
- Collect benchmark data and performance characteristics
- Identify community consensus and common pitfalls

### Milestone 3: Analyze
- Build comparison matrix with consistent criteria
- Evaluate trade-offs for each option
- Identify risks and migration costs
- Rank options by fit with project requirements

### Milestone 4: Prototype
- Implement minimal working prototype of top candidate
- Exercise the key use cases and edge cases
- Measure performance against criteria
- Document integration complexity and gotchas

### Milestone 5: Evaluate
- Compare prototype results with evaluation criteria
- Identify gaps between prototype and production needs
- Assess total cost of adoption (learning, migration, maintenance)
- Make go/no-go recommendation with supporting evidence

### Milestone 6: Document
- Write research summary with methodology
- Document recommendation with trade-offs and alternatives
- Include code samples and integration guide
- Archive research materials for future reference
