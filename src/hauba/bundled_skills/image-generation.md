# Skill: image-generation

## Capabilities
- Image manipulation with PIL/Pillow (resize, crop, rotate, filter)
- Creating images from scratch (banners, thumbnails, social media graphics)
- Adding text, watermarks, and overlays to images
- Image format conversion (PNG, JPEG, WebP, SVG)
- Batch image processing and optimization
- Color manipulation (adjust brightness, contrast, saturation)
- Creating composite images and collages

## When To Use
- Creating or editing images programmatically
- Generating thumbnails, banners, or social media graphics
- Processing batches of images (resize, optimize, convert)
- Task mentions "image", "picture", "thumbnail", "banner", "resize", "watermark", "pillow"

## Tools Required
- Pillow
- cairosvg (optional, for SVG support)

## Approach

### Phase 1: Understand
- Identify source image format and dimensions
- Determine target output (format, dimensions, quality)
- Map required transformations (resize, crop, text, overlay)
- Check if vector/SVG support is needed

### Phase 2: Plan
- Design the image composition (layers, text placement, colors)
- Choose appropriate resampling method for quality
- Plan text rendering (font, size, color, position)
- Define output quality settings (JPEG quality, PNG compression)

### Phase 3: Execute
- Install Pillow if not present
- Open/create image with PIL/Pillow
- Apply transformations in correct order (resize before text overlay)
- Add text with appropriate font and anti-aliasing
- Apply filters or effects if requested
- Save with optimized settings for target format

### Phase 4: Verify
- Check output file exists and has expected dimensions
- Verify visual quality meets requirements
- Confirm file size is optimized for target use (web, print)
- Validate format-specific requirements (transparency for PNG, no alpha for JPEG)

## Constraints
- Always use RGB mode for JPEG output (convert from RGBA if needed)
- Use LANCZOS resampling for downscaling (best quality)
- Never upscale images beyond 200% (quality degrades)
- Handle EXIF rotation when processing photos
- Close image objects after processing to free memory

## Scale Considerations
- For batch processing, process one image at a time to limit memory
- Use WebP format for web images (best size/quality ratio)
- Implement progressive JPEG for large web images
- Cache font objects when rendering text on multiple images

## Error Recovery
- Unsupported format: convert to common format first (PNG/JPEG)
- Font not found: fall back to default PIL font
- Memory error: reduce image dimensions or process in tiles
- Corrupted image: try re-opening with error recovery mode
