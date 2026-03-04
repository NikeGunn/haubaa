#!/usr/bin/env python3
"""Generate terminal-style animated GIF demos for Hauba README.

Creates simulated terminal recordings as animated GIFs showing:
1. hauba-init.gif     — Setup wizard flow
2. hauba-run.gif      — Running a task with interactive UI
3. hauba-agent.gif    — Daemon polling and executing
4. hauba-whatsapp.gif — WhatsApp bot interaction
5. hauba-compose.gif  — Declarative team execution
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
ASSETS_DIR = Path(__file__).parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# Terminal dimensions
TERM_WIDTH = 820
TERM_HEIGHT = 520
PADDING = 20
LINE_HEIGHT = 22
TITLE_BAR_HEIGHT = 36

# Colors (dark terminal theme)
BG_COLOR = (30, 30, 46)        # Dark background
TITLE_BG = (49, 50, 68)        # Title bar
TEXT_COLOR = (205, 214, 244)    # Default text
GREEN = (166, 227, 161)        # Success/prompt
YELLOW = (249, 226, 175)       # Highlights
CYAN = (137, 220, 235)         # Commands
MAGENTA = (245, 194, 231)      # Accents
RED = (243, 139, 168)          # Errors
BLUE = (137, 180, 250)         # Info
DIM = (108, 112, 134)          # Dim/comments
WHITE = (255, 255, 255)

# Dots for macOS-style title bar
DOT_RED = (237, 106, 94)
DOT_YELLOW = (245, 191, 79)
DOT_GREEN = (98, 187, 70)


def get_font(size: int = 14, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a monospace font, falling back to default if unavailable."""
    font_candidates = [
        "C:/Windows/Fonts/consola.ttf",        # Consolas (Windows)
        "C:/Windows/Fonts/consolab.ttf",       # Consolas Bold
        "C:/Windows/Fonts/lucon.ttf",          # Lucida Console
        "C:/Windows/Fonts/cour.ttf",           # Courier New
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    if bold:
        font_candidates.insert(0, "C:/Windows/Fonts/consolab.ttf")

    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


FONT = get_font(14)
FONT_BOLD = get_font(14, bold=True)
FONT_TITLE = get_font(13)


def create_terminal_frame(
    lines: list[tuple[str, tuple[int, int, int]]],
    title: str = "Terminal",
    cursor_line: int | None = None,
    cursor_col: int | None = None,
) -> Image.Image:
    """Create a single terminal frame with styled text lines."""
    img = Image.new("RGB", (TERM_WIDTH, TERM_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([(0, 0), (TERM_WIDTH, TITLE_BAR_HEIGHT)], fill=TITLE_BG)

    # Window dots
    dot_y = TITLE_BAR_HEIGHT // 2
    draw.ellipse([(12, dot_y - 6), (24, dot_y + 6)], fill=DOT_RED)
    draw.ellipse([(32, dot_y - 6), (44, dot_y + 6)], fill=DOT_YELLOW)
    draw.ellipse([(52, dot_y - 6), (64, dot_y + 6)], fill=DOT_GREEN)

    # Title text
    draw.text((TERM_WIDTH // 2 - 40, 10), title, fill=DIM, font=FONT_TITLE)

    # Terminal content
    y = TITLE_BAR_HEIGHT + PADDING
    for i, (text, color) in enumerate(lines):
        if y + LINE_HEIGHT > TERM_HEIGHT - 10:
            break
        draw.text((PADDING, y), text, fill=color, font=FONT)

        # Blinking cursor
        if cursor_line == i and cursor_col is not None:
            cx = PADDING + cursor_col * 8
            draw.rectangle([(cx, y), (cx + 8, y + LINE_HEIGHT - 4)], fill=TEXT_COLOR)

        y += LINE_HEIGHT

    # Subtle border
    draw.rectangle([(0, 0), (TERM_WIDTH - 1, TERM_HEIGHT - 1)], outline=(69, 71, 90), width=1)

    return img


def typing_frames(
    prefix_lines: list[tuple[str, tuple[int, int, int]]],
    prompt: str,
    command: str,
    prompt_color: tuple[int, int, int] = GREEN,
) -> list[tuple[Image.Image, int]]:
    """Generate frames simulating typing a command character by character."""
    frames = []
    for i in range(len(command) + 1):
        partial = command[:i]
        lines = prefix_lines + [(prompt + partial, prompt_color)]
        cursor_col = len(prompt) + i
        frame = create_terminal_frame(
            lines, title="Terminal", cursor_line=len(prefix_lines), cursor_col=cursor_col
        )
        frames.append((frame, 60 if i < len(command) else 400))
    return frames


def static_frame(
    lines: list[tuple[str, tuple[int, int, int]]],
    duration: int = 800,
    title: str = "Terminal",
) -> tuple[Image.Image, int]:
    """Create a static frame held for a duration."""
    return (create_terminal_frame(lines, title=title), duration)


def save_gif(frames: list[tuple[Image.Image, int]], filename: str) -> None:
    """Save frames as an animated GIF."""
    path = ASSETS_DIR / filename
    images = [f[0] for f in frames]
    durations = [f[1] for f in frames]

    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    size_kb = path.stat().st_size / 1024
    print(f"  Created {path.name} ({size_kb:.0f} KB, {len(images)} frames)")


# ============================================================
# GIF 1: hauba init
# ============================================================
def generate_init_gif() -> None:
    """Generate the hauba init demo GIF."""
    print("Generating hauba-init.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # Frame 1: Empty terminal with prompt
    prompt_lines: list[tuple[str, tuple[int, int, int]]] = []
    frames.extend(typing_frames(prompt_lines, "$ ", "hauba init"))

    # Frame 2: Banner appears
    banner_lines: list[tuple[str, tuple[int, int, int]]] = [
        ("$ hauba init", GREEN),
        ("", TEXT_COLOR),
        ("  Welcome to Hauba AI Workstation", CYAN),
        ("  ================================", DIM),
        ("", TEXT_COLOR),
        ("  Select your LLM provider:", TEXT_COLOR),
        ("", TEXT_COLOR),
        ("  > Anthropic (Claude)        [recommended]", YELLOW),
        ("    OpenAI (GPT-4o, o3)", DIM),
        ("    Ollama (local, free)", DIM),
        ("    Azure OpenAI", DIM),
    ]
    frames.append(static_frame(banner_lines, 1500))

    # Frame 3: Selected Anthropic
    selected_lines: list[tuple[str, tuple[int, int, int]]] = [
        ("$ hauba init", GREEN),
        ("", TEXT_COLOR),
        ("  Welcome to Hauba AI Workstation", CYAN),
        ("  ================================", DIM),
        ("", TEXT_COLOR),
        ("  Provider: Anthropic (Claude)", GREEN),
        ("", TEXT_COLOR),
        ("  Enter API key: sk-ant-***************", TEXT_COLOR),
        ("", TEXT_COLOR),
        ("  Model: claude-sonnet-4-5-20250929", BLUE),
        ("", TEXT_COLOR),
        ("  Config saved to ~/.hauba/settings.json", GREEN),
        ("  17 skills loaded", CYAN),
        ("  Ready! Run: hauba run \"your task\"", YELLOW),
    ]
    frames.append(static_frame(selected_lines, 2500))

    save_gif(frames, "hauba-init.gif")


# ============================================================
# GIF 2: hauba run (main demo)
# ============================================================
def generate_run_gif() -> None:
    """Generate the hauba run demo GIF."""
    print("Generating hauba-run.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # Typing the command
    frames.extend(typing_frames(
        [], "$ ", 'hauba run "build a REST API with auth and tests"'
    ))

    # Thinking phase
    frames.append(static_frame([
        ('$ hauba run "build a REST API with auth and tests"', GREEN),
        ("", TEXT_COLOR),
        ("  Thinking...", YELLOW),
        ("  Matched skills: full-stack-engineering, api-design, testing", CYAN),
    ], 1200))

    # Planning phase
    plan_lines: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba run "build a REST API with auth and tests"', GREEN),
        ("", TEXT_COLOR),
        ("  Plan", YELLOW),
        ("  ----", DIM),
        ("  1. Set up FastAPI project structure", TEXT_COLOR),
        ("  2. Create user model with SQLAlchemy", TEXT_COLOR),
        ("  3. Implement JWT authentication", TEXT_COLOR),
        ("  4. Build CRUD endpoints", TEXT_COLOR),
        ("  5. Add input validation (Pydantic)", TEXT_COLOR),
        ("  6. Write pytest test suite", TEXT_COLOR),
        ("  7. Verify all tests pass", TEXT_COLOR),
        ("", TEXT_COLOR),
        ("  Proceed? [Y/n]", CYAN),
    ]
    frames.append(static_frame(plan_lines, 2000))

    # Executing phase
    exec_lines: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba run "build a REST API with auth and tests"', GREEN),
        ("", TEXT_COLOR),
        ("  Executing (3/7)...", YELLOW),
        ("", TEXT_COLOR),
        ("  [bash] mkdir -p src/api src/models src/auth", DIM),
        ("  [file] src/api/main.py                   CREATED", GREEN),
        ("  [file] src/models/user.py                CREATED", GREEN),
        ("  [file] src/auth/jwt_handler.py            WRITING", YELLOW),
        ("", TEXT_COLOR),
        ("  Files: 3 created, 0 modified", BLUE),
    ]
    frames.append(static_frame(exec_lines, 1500))

    # More execution
    exec2_lines: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba run "build a REST API with auth and tests"', GREEN),
        ("", TEXT_COLOR),
        ("  Executing (6/7)...", YELLOW),
        ("", TEXT_COLOR),
        ("  [file] src/auth/jwt_handler.py            CREATED", GREEN),
        ("  [file] src/api/routes.py                  CREATED", GREEN),
        ("  [file] src/api/schemas.py                 CREATED", GREEN),
        ("  [file] tests/test_auth.py                 CREATED", GREEN),
        ("  [file] tests/test_routes.py               WRITING", YELLOW),
        ("  [bash] pip install fastapi uvicorn sqlalchemy", DIM),
        ("", TEXT_COLOR),
        ("  Files: 7 created, 0 modified", BLUE),
    ]
    frames.append(static_frame(exec2_lines, 1500))

    # Verification & completion
    done_lines: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba run "build a REST API with auth and tests"', GREEN),
        ("", TEXT_COLOR),
        ("  Verifying...", YELLOW),
        ("  [bash] pytest tests/ -v", DIM),
        ("  tests/test_auth.py::test_login         PASSED", GREEN),
        ("  tests/test_auth.py::test_register      PASSED", GREEN),
        ("  tests/test_routes.py::test_create_user  PASSED", GREEN),
        ("  tests/test_routes.py::test_get_users    PASSED", GREEN),
        ("  4 passed in 1.2s", GREEN),
        ("", TEXT_COLOR),
        ("  Task completed successfully!", GREEN),
        ("  7 files created | 4 tests passing | 0 errors", CYAN),
        ("", TEXT_COLOR),
        ("  Send follow-up or press Ctrl+C to exit", DIM),
    ]
    frames.append(static_frame(done_lines, 3000))

    save_gif(frames, "hauba-run.gif")


# ============================================================
# GIF 3: hauba agent (daemon)
# ============================================================
def generate_agent_gif() -> None:
    """Generate the hauba agent daemon demo GIF."""
    print("Generating hauba-agent.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # Typing command
    frames.extend(typing_frames([], "$ ", "hauba agent --server https://hauba.tech"))

    # Daemon starts
    daemon_start: list[tuple[str, tuple[int, int, int]]] = [
        ("$ hauba agent --server https://hauba.tech", GREEN),
        ("", TEXT_COLOR),
        ("  Hauba Daemon v0.7.1", CYAN),
        ("  ====================", DIM),
        ("  Server:   https://hauba.tech", TEXT_COLOR),
        ("  Owner:    dev-nikhil", TEXT_COLOR),
        ("  Provider: anthropic (claude-sonnet-4-5)", TEXT_COLOR),
        ("  Polling every 10s...", DIM),
        ("", TEXT_COLOR),
        ("  [10:23:01] Polling... no tasks", DIM),
        ("  [10:23:11] Polling... no tasks", DIM),
    ]
    frames.append(static_frame(daemon_start, 1500))

    # Task received
    task_received: list[tuple[str, tuple[int, int, int]]] = [
        ("$ hauba agent --server https://hauba.tech", GREEN),
        ("", TEXT_COLOR),
        ("  Hauba Daemon v0.7.1", CYAN),
        ("  ====================", DIM),
        ("  [10:23:01] Polling... no tasks", DIM),
        ("  [10:23:11] Polling... no tasks", DIM),
        ("  [10:23:21] Task received!", YELLOW),
        ("", TEXT_COLOR),
        ("  Task: build a portfolio website with dark mode", WHITE),
        ("  From: WhatsApp (+977-981-234-5678)", BLUE),
        ("  Claiming task...", YELLOW),
        ("  Executing with CopilotEngine...", CYAN),
    ]
    frames.append(static_frame(task_received, 2000))

    # Execution with progress
    exec_progress: list[tuple[str, tuple[int, int, int]]] = [
        ("$ hauba agent --server https://hauba.tech", GREEN),
        ("", TEXT_COLOR),
        ("  [10:23:21] Task: build a portfolio website", WHITE),
        ("  [10:23:22] Claimed successfully", GREEN),
        ("  [10:23:23] Executing...", YELLOW),
        ("", TEXT_COLOR),
        ("  Progress: [==============      ] 70%", CYAN),
        ("  Files: index.html, style.css, app.js", DIM),
        ("  Cost estimate: $0.12", DIM),
        ("", TEXT_COLOR),
        ("  [10:23:45] Task completed!", GREEN),
        ("  [10:23:45] Notified via WhatsApp", GREEN),
        ("  [10:23:55] Polling... no tasks", DIM),
    ]
    frames.append(static_frame(exec_progress, 2500))

    save_gif(frames, "hauba-agent.gif")


# ============================================================
# GIF 4: WhatsApp Bot
# ============================================================
def generate_whatsapp_gif() -> None:
    """Generate the WhatsApp bot interaction demo GIF."""
    print("Generating hauba-whatsapp.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # WhatsApp-style chat simulation
    chat1: list[tuple[str, tuple[int, int, int]]] = [
        ("  WhatsApp  <->  Hauba Bot", CYAN),
        ("  " + "=" * 40, DIM),
        ("", TEXT_COLOR),
        ("  You: build me a React dashboard with charts", WHITE),
        ("", TEXT_COLOR),
        ("  Hauba: Got it! I've queued your task.", GREEN),
        ("  Task ID: abc-1234", DIM),
        ("  Your local agent will pick it up shortly.", GREEN),
    ]
    frames.append(static_frame(chat1, 2000, title="WhatsApp Chat"))

    # Progress update
    chat2: list[tuple[str, tuple[int, int, int]]] = [
        ("  WhatsApp  <->  Hauba Bot", CYAN),
        ("  " + "=" * 40, DIM),
        ("", TEXT_COLOR),
        ("  You: build me a React dashboard with charts", WHITE),
        ("  Hauba: Got it! I've queued your task.", GREEN),
        ("", TEXT_COLOR),
        ("  Hauba: Progress update (70%)", YELLOW),
        ("  Creating components: Dashboard, Chart, Sidebar", DIM),
        ("", TEXT_COLOR),
        ("  Hauba: Done! Your dashboard is ready.", GREEN),
        ("  5 files created in ~/projects/dashboard/", CYAN),
        ("  Cost: $0.08", DIM),
    ]
    frames.append(static_frame(chat2, 2000, title="WhatsApp Chat"))

    # Commands
    chat3: list[tuple[str, tuple[int, int, int]]] = [
        ("  WhatsApp  <->  Hauba Bot", CYAN),
        ("  " + "=" * 40, DIM),
        ("", TEXT_COLOR),
        ("  You: /tasks", WHITE),
        ("", TEXT_COLOR),
        ("  Hauba: Your tasks:", GREEN),
        ("  [abc-1234] React dashboard     COMPLETED", GREEN),
        ("  [def-5678] API integration     RUNNING", YELLOW),
        ("", TEXT_COLOR),
        ("  You: /cancel def-5678", WHITE),
        ("  Hauba: Task def-5678 cancelled.", RED),
        ("", TEXT_COLOR),
        ("  You: /usage", WHITE),
        ("  Hauba: Tasks: 12 | Cost: $1.24 | Avg: $0.10", BLUE),
    ]
    frames.append(static_frame(chat3, 2500, title="WhatsApp Chat"))

    save_gif(frames, "hauba-whatsapp.gif")


# ============================================================
# GIF 5: hauba compose
# ============================================================
def generate_compose_gif() -> None:
    """Generate the hauba compose demo GIF."""
    print("Generating hauba-compose.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # Show the yaml first
    yaml_lines: list[tuple[str, tuple[int, int, int]]] = [
        ("  # hauba.yaml", DIM),
        ('  team: "my-saas"', TEXT_COLOR),
        ('  model: "claude-sonnet-4-5-20250929"', TEXT_COLOR),
        ("", TEXT_COLOR),
        ("  agents:", CYAN),
        ('    architect:  "Senior Software Architect"', TEXT_COLOR),
        ('    backend:    "Backend Engineer"      [depends: architect]', TEXT_COLOR),
        ('    frontend:   "Frontend Engineer"     [depends: architect]', TEXT_COLOR),
        ('    devops:     "DevOps Engineer"       [depends: backend, frontend]', TEXT_COLOR),
    ]
    frames.append(static_frame(yaml_lines, 2000, title="hauba.yaml"))

    # Running compose
    frames.extend(typing_frames(
        [], "$ ", 'hauba compose up "build a SaaS with auth and billing"'
    ))

    # Execution
    compose_exec: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba compose up "build a SaaS with auth and billing"', GREEN),
        ("", TEXT_COLOR),
        ("  Team: my-saas (4 agents)", CYAN),
        ("  Execution order (respecting dependencies):", DIM),
        ("", TEXT_COLOR),
        ("  [1/4] architect  Planning system design...     DONE", GREEN),
        ("  [2/4] backend    Building API + auth...        RUNNING", YELLOW),
        ("  [2/4] frontend   Building React UI...          RUNNING", YELLOW),
        ("  [4/4] devops     Waiting for backend, frontend...", DIM),
        ("", TEXT_COLOR),
        ("  Parallel execution: backend + frontend", BLUE),
    ]
    frames.append(static_frame(compose_exec, 2000))

    # Completion
    compose_done: list[tuple[str, tuple[int, int, int]]] = [
        ('$ hauba compose up "build a SaaS with auth and billing"', GREEN),
        ("", TEXT_COLOR),
        ("  Team: my-saas (4 agents)", CYAN),
        ("", TEXT_COLOR),
        ("  [1/4] architect  System design              DONE", GREEN),
        ("  [2/4] backend    FastAPI + JWT + Stripe      DONE", GREEN),
        ("  [3/4] frontend   Next.js + Tailwind          DONE", GREEN),
        ("  [4/4] devops     Docker + CI/CD              DONE", GREEN),
        ("", TEXT_COLOR),
        ("  All 4 agents completed successfully!", GREEN),
        ("  Output: ./output/my-saas/", CYAN),
        ("  22 files created | 0 errors", YELLOW),
    ]
    frames.append(static_frame(compose_done, 2500))

    save_gif(frames, "hauba-compose.gif")


# ============================================================
# GIF 6: Architecture overview (animated diagram)
# ============================================================
def generate_architecture_gif() -> None:
    """Generate the architecture overview GIF."""
    print("Generating hauba-architecture.gif...")

    frames: list[tuple[Image.Image, int]] = []

    # Step 1: User sends task
    step1: list[tuple[str, tuple[int, int, int]]] = [
        ("  Hauba Architecture — Queue + Poll", CYAN),
        ("  " + "=" * 42, DIM),
        ("", TEXT_COLOR),
        ("  STEP 1: User sends a task", YELLOW),
        ("", TEXT_COLOR),
        ('  WhatsApp: "build me a landing page"', WHITE),
        ("       |", DIM),
        ("       v", DIM),
        ("  [Server: hauba.tech]", BLUE),
        ("       |", DIM),
        ("       v", DIM),
        ("  Task Queue: [task_abc queued]", MAGENTA),
    ]
    frames.append(static_frame(step1, 2000))

    # Step 2: Daemon polls
    step2: list[tuple[str, tuple[int, int, int]]] = [
        ("  Hauba Architecture — Queue + Poll", CYAN),
        ("  " + "=" * 42, DIM),
        ("", TEXT_COLOR),
        ("  STEP 2: Local daemon polls & claims", YELLOW),
        ("", TEXT_COLOR),
        ("  User's Machine               Server", TEXT_COLOR),
        ("  +--------------+       +--------------+", DIM),
        ("  | hauba agent  | ----> | /queue/poll   |", GREEN),
        ("  |  (your key)  | <---- | task_abc      |", GREEN),
        ("  +--------------+       +--------------+", DIM),
        ("", TEXT_COLOR),
        ("  Builds on YOUR machine with YOUR API key", CYAN),
    ]
    frames.append(static_frame(step2, 2500))

    # Step 3: Execution & notification
    step3: list[tuple[str, tuple[int, int, int]]] = [
        ("  Hauba Architecture — Queue + Poll", CYAN),
        ("  " + "=" * 42, DIM),
        ("", TEXT_COLOR),
        ("  STEP 3: Execute locally, notify remotely", YELLOW),
        ("", TEXT_COLOR),
        ("  hauba agent", GREEN),
        ("    -> CopilotEngine.execute(task)", WHITE),
        ("    -> [bash] [files] [git] [web]", DIM),
        ("    -> Reports progress to server", BLUE),
        ("    -> Task completed!", GREEN),
        ("", TEXT_COLOR),
        ("  Server notifies WhatsApp/Telegram/Discord", MAGENTA),
        ("  User gets results on their phone!", CYAN),
    ]
    frames.append(static_frame(step3, 2500))

    save_gif(frames, "hauba-architecture.gif")


# ============================================================
# Main
# ============================================================
def main() -> None:
    """Generate all demo GIFs."""
    print("Generating Hauba demo GIFs...\n")

    generate_init_gif()
    generate_run_gif()
    generate_agent_gif()
    generate_whatsapp_gif()
    generate_compose_gif()
    generate_architecture_gif()

    print(f"\nAll GIFs saved to {ASSETS_DIR}/")
    print("Add to README.md with: ![Demo](assets/hauba-run.gif)")


if __name__ == "__main__":
    main()
