# Skill: web-scraping

## Capabilities
- Web page scraping with BeautifulSoup and requests
- Dynamic page scraping with Playwright (JavaScript-rendered content)
- Data extraction from HTML tables, lists, and structured content
- Pagination handling and multi-page scraping
- Rate limiting and respectful crawling
- JSON API response parsing
- Data export to CSV, JSON, or database

## When To Use
- Extracting data from web pages
- Scraping structured content (tables, listings, products)
- Automating data collection from websites
- Task mentions "scrape", "crawl", "extract from web", "website data", "BeautifulSoup"

## Tools Required
- beautifulsoup4
- requests
- lxml

## Approach

### Phase 1: Understand
- Identify target URLs and data structure
- Check robots.txt and terms of service
- Determine if content is static HTML or JavaScript-rendered
- Map the data extraction points (CSS selectors, XPath)

### Phase 2: Plan
- Choose scraping method (requests+BS4 for static, Playwright for dynamic)
- Design data extraction selectors
- Plan pagination and rate limiting strategy
- Define output schema and storage format

### Phase 3: Execute
- Install scraping libraries if needed
- Fetch pages with appropriate headers (User-Agent, Accept)
- Parse HTML and extract data using selectors
- Handle pagination (next page links, page numbers, infinite scroll)
- Clean and structure extracted data
- Export to requested format (CSV, JSON, database)

### Phase 4: Verify
- Check extracted data completeness (expected row count)
- Validate data types and format consistency
- Verify no duplicate records
- Confirm pagination captured all pages

## Constraints
- Always respect robots.txt and rate limits
- Add delays between requests (minimum 1 second)
- Set a proper User-Agent header (identify the scraper)
- Handle HTTP errors gracefully (retry 429/503, skip 404)
- Never scrape personal/private data without authorization

## Scale Considerations
- Use connection pooling for multiple requests to same host
- Implement exponential backoff for rate-limited responses
- Cache responses to avoid re-fetching during development
- Use async requests for scraping multiple independent pages

## Error Recovery
- 403 Forbidden: check User-Agent, try with cookies/session
- 429 Rate Limited: increase delay, implement exponential backoff
- Connection timeout: retry with longer timeout, check network
- Parse error: inspect page structure, update selectors
