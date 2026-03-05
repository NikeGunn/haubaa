# Skill: 3D Modeling & Blender Automation

## Capabilities
- Create 3D models, scenes, and animations using Blender's Python API (bpy)
- Render images and animations via Blender command-line interface
- Generate parametric 3D objects (meshes, curves, NURBS)
- Apply materials, textures, and lighting
- Create procedural geometry with geometry nodes via Python
- Export to standard formats (OBJ, FBX, GLB/glTF, STL, USD)
- Batch processing of 3D assets (resize, convert, optimize)
- Create architectural visualizations and product renders

## When To Use
- User asks to create 3D models, scenes, or animations
- User asks to render images or video from 3D scenes
- User mentions Blender, 3D, modeling, rendering, meshes
- User needs procedural geometry or parametric models
- User wants to automate Blender workflows
- User needs 3D file format conversion
- User wants to create game assets or architectural renders

## Approach

### Phase 1: UNDERSTAND
- What 3D object/scene needs to be created?
- What output format is needed? (PNG render, GLB export, FBX, etc.)
- Does the user have Blender installed? Check with `blender --version`
- Are there reference images or specific dimensions?

### Phase 2: PLAN
- Design the Blender Python script (bpy API)
- Plan object hierarchy: meshes, materials, lights, camera
- Choose appropriate rendering engine (Eevee for fast, Cycles for quality)
- Plan export format and settings

### Phase 3: IMPLEMENT
- Write a standalone Blender Python script
- Run via: `blender --background --python script.py`
- Use bpy API for all operations:
  - `bpy.ops.mesh.primitive_*_add()` for basic shapes
  - `bpy.data.materials.new()` for materials
  - `bpy.ops.render.render()` for rendering
  - `bpy.ops.export_scene.*()` for exports
- Install Blender if needed: `pip install bpy` or system package manager

### Phase 4: VERIFY
- Check that output files exist and are valid
- Preview renders if possible
- Verify file sizes are reasonable
- Test exports open in other tools

### Phase 5: DELIVER
- Provide the generated files (renders, 3D models)
- Include the Blender script for reproducibility
- Document any manual setup steps

## Constraints
- Always use `--background` flag for headless Blender execution
- Prefer Eevee renderer for speed unless photorealism is required
- Keep polygon counts reasonable for game assets (< 100K tris)
- Use PBR materials for compatibility with game engines
- Export glTF/GLB for web, FBX for game engines, OBJ for general use
- Clean up Blender's default scene before adding new objects

## Common Blender Python Patterns

```python
# Headless Blender script template
import bpy

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create object
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
obj = bpy.context.active_object

# Add material
mat = bpy.data.materials.new(name="Material")
mat.use_nodes = True
obj.data.materials.append(mat)

# Set up camera
bpy.ops.object.camera_add(location=(5, -5, 5))
cam = bpy.context.active_object
cam.rotation_euler = (1.1, 0, 0.8)
bpy.context.scene.camera = cam

# Set up light
bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

# Render settings
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.filepath = '/tmp/render.png'
bpy.ops.render.render(write_still=True)
```

## Scale Considerations
- For complex scenes (>50 objects), batch-create with loops
- Use instancing for repeated objects (particles, arrays)
- For animations, set keyframes programmatically via `obj.keyframe_insert()`
- Large renders: use Cycles GPU if available, reduce samples for drafts
