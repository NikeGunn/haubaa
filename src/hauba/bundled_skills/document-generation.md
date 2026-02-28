# Skill: document-generation

## Capabilities
- PDF generation with reportlab or weasyprint
- Markdown to HTML/PDF conversion
- PowerPoint presentation creation (python-pptx)
- Excel spreadsheet generation with formatting (openpyxl)
- LaTeX document compilation
- Template-based document rendering (Jinja2)
- Invoice, report, and certificate generation

## When To Use
- Creating PDF documents, reports, or invoices
- Generating presentations or spreadsheets programmatically
- Converting between document formats
- Task mentions "PDF", "document", "report", "presentation", "spreadsheet", "invoice", "slides"

## Tools Required
- reportlab (for PDF)
- python-pptx (for presentations)
- openpyxl (for Excel)
- jinja2 (for templates)

## Approach

### Phase 1: Understand
- Identify document type and target format
- Determine content structure (sections, tables, charts, images)
- Map data sources for dynamic content
- Clarify branding requirements (fonts, colors, logos)

### Phase 2: Plan
- Design document layout and page structure
- Plan content flow (header, body, footer, page breaks)
- Choose the right library for the document type
- Design reusable templates for recurring document types

### Phase 3: Execute
- Install document generation libraries if needed
- Create document structure (pages, slides, sheets)
- Populate with content: text, tables, images, charts
- Apply formatting: fonts, colors, alignment, borders
- Add headers, footers, page numbers where applicable
- Save to target format with proper metadata

### Phase 4: Verify
- Open generated document and verify visual layout
- Check all dynamic data is populated correctly
- Verify page breaks and section formatting
- Confirm file size is reasonable
- Test with edge cases (long text, many pages, special characters)

## Constraints
- Use UTF-8 encoding for all text content
- Handle special characters and non-Latin scripts
- Keep file sizes reasonable (optimize images before embedding)
- Use vector graphics (SVG) over raster for scalable quality
- Include proper metadata (title, author, creation date)

## Scale Considerations
- For bulk document generation, use template caching
- Stream large PDFs to disk instead of building in memory
- Use async generation for multiple independent documents
- Implement document signing for official documents

## Error Recovery
- Font not found: fall back to built-in fonts (Helvetica, Times)
- Image load failure: use placeholder image, log warning
- Template error: validate template syntax before rendering
- PDF corruption: regenerate from scratch, check library version
