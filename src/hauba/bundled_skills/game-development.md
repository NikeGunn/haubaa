# Skill: Game Development

## Capabilities
- Build 2D and 3D games using Python game frameworks
- Create game assets (sprites, textures, sounds) programmatically
- Implement game mechanics: physics, collision, AI, pathfinding
- Build game UIs: menus, HUDs, inventories, dialogs
- Create game levels and procedural content generation
- Package games for distribution (executable, web, mobile)
- Integrate with game engines via scripting (Godot GDScript, Blender Game)
- Build multiplayer networking (WebSocket, UDP)

## When To Use
- User asks to create a game or game prototype
- User mentions game engines, game mechanics, or game design
- User wants to build interactive experiences
- User asks about Pygame, Godot, Phaser, or other game frameworks
- User wants procedural level generation
- User needs game AI (pathfinding, state machines, behavior trees)

## Approach

### Phase 1: UNDERSTAND
- What type of game? (2D platformer, puzzle, RPG, FPS, etc.)
- Target platform? (desktop, web, mobile)
- What framework/engine preference? (Pygame, Godot, Phaser.js)
- Art style? (pixel art, vector, 3D)
- Multiplayer? (local, online)

### Phase 2: PLAN
- Choose appropriate framework:
  - **Pygame** — Best for Python 2D games, easy setup
  - **Arcade** — Modern Python game library, hardware-accelerated
  - **Godot** — Full game engine with Python-like GDScript
  - **Phaser** — JavaScript 2D game framework for web
  - **Three.js** — JavaScript 3D for web games
  - **Ursina** — Python 3D game engine (Panda3D wrapper)
- Plan game architecture: scenes, entities, systems
- Plan asset pipeline: how to generate/load sprites, sounds
- Plan game loop: input → update → render

### Phase 3: IMPLEMENT
- Set up project structure
- Implement core game loop
- Create game entities (player, enemies, items)
- Implement game mechanics (movement, collision, scoring)
- Add UI elements (menus, HUD, game over screen)
- Generate or create placeholder art assets
- Add sound effects and music (programmatic or downloaded)
- Package for distribution

### Phase 4: VERIFY
- Run the game and test all mechanics
- Check for crashes, memory leaks, performance issues
- Test edge cases (boundary conditions, rapid input)
- Verify packaging works on target platform

### Phase 5: DELIVER
- Provide runnable game with instructions
- Include README with controls and setup
- List any dependencies and how to install them

## Constraints
- Start with Pygame for simple 2D games (most portable, no install hassle)
- Use procedural art generation when possible (no external assets needed)
- Keep games self-contained (single file or folder, no complex build)
- Handle window close/exit gracefully (no orphan processes)
- Cap frame rate to prevent CPU burn (60 FPS default)
- Use delta time for frame-independent movement
- Never hardcode screen resolution — use constants

## Common Pygame Template

```python
import pygame
import sys

# Initialize
pygame.init()
SCREEN_W, SCREEN_H = 800, 600
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("My Game")
clock = pygame.time.Clock()
FPS = 60

# Game state
player = pygame.Rect(SCREEN_W // 2, SCREEN_H // 2, 40, 40)
speed = 5

# Game loop
running = True
while running:
    dt = clock.tick(FPS) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]: player.x -= speed
    if keys[pygame.K_RIGHT]: player.x += speed
    if keys[pygame.K_UP]: player.y -= speed
    if keys[pygame.K_DOWN]: player.y += speed

    screen.fill((20, 20, 40))
    pygame.draw.rect(screen, (0, 200, 100), player)
    pygame.display.flip()

pygame.quit()
sys.exit()
```

## Scale Considerations
- For larger games, use Entity-Component-System (ECS) pattern
- Use sprite sheets for animation (tile-based for efficiency)
- Implement spatial partitioning for collision (grid, quadtree)
- Use object pooling for bullets, particles, effects
- Separate game logic from rendering for testability
- Use state machines for game states (menu, playing, paused, game over)

## Error Recovery
- Game crashes → check pygame.error, missing assets, division by zero
- Performance issues → profile with cProfile, reduce draw calls
- Audio issues → check mixer initialization, sample rate compatibility
- Asset loading failures → use try/except with fallback placeholder art
