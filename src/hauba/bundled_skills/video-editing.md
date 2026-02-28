# Skill: video-editing

## Capabilities
- Video trimming, cutting, and concatenation using MoviePy
- Adding transitions, effects, and overlays
- Subtitle generation and embedding (SRT/ASS format)
- Audio extraction, mixing, and replacement
- Video format conversion and resolution scaling
- Thumbnail generation from video frames
- Batch video processing for multiple files

## When To Use
- Editing or processing video files
- Adding subtitles, effects, or transitions to video
- Converting between video formats
- Task mentions "video", "edit video", "trim", "subtitle", "moviepy", "mp4", "effects"

## Tools Required
- moviepy
- imageio[ffmpeg]

## Approach

### Phase 1: Understand
- Identify source video format, resolution, and duration
- Determine the desired output (format, quality, effects)
- Check if FFmpeg is available (moviepy requirement)
- Map the editing timeline: what happens when

### Phase 2: Plan
- Break edits into sequential operations (trim → effect → subtitle → export)
- Plan memory usage for large video files (stream vs load)
- Define output parameters (codec, bitrate, resolution, fps)
- Prepare subtitle data if needed

### Phase 3: Execute
- Install moviepy and imageio[ffmpeg] if not present
- Load video clip(s) with MoviePy
- Apply edits: trim, concatenate, add effects, overlays
- Generate or embed subtitles
- Write output file with specified format and quality
- Generate thumbnail if requested

### Phase 4: Verify
- Check output file exists and has expected duration
- Verify file size is reasonable (not 0 bytes, not excessively large)
- Spot-check first/last frame for correctness
- Confirm audio is present if expected

## Constraints
- Always check disk space before processing large videos
- Use streaming/chunked processing for videos over 1GB
- Never overwrite source files — write to new output path
- Handle common codec issues gracefully (fallback to libx264/aac)
- Close all video clips after processing to free memory

## Scale Considerations
- For batch processing, use sequential processing to avoid memory exhaustion
- Prefer GPU-accelerated codecs when available (nvenc)
- Use lower preview resolution for iterating on effects, full res for final export
- Consider ffmpeg directly for simple operations (faster than MoviePy)

## Error Recovery
- FFmpeg not found: install via `imageio[ffmpeg]` or system package manager
- Codec error: fall back to H.264/AAC (most compatible)
- Out of memory: reduce resolution or process in segments
- Corrupted source video: try ffmpeg repair first (`ffmpeg -i input -c copy output`)
