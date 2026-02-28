"""Hauba Browser Automation Demo — visual demonstration.

Run this script to see Hauba's BrowserTool in action with a VISIBLE browser.
It opens a local task manager app and automates interactions.

Usage:
    python scripts/demo_browser.py           # headed (default)
    python scripts/demo_browser.py --headless  # headless mode
"""

from __future__ import annotations

import asyncio
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hauba.tools.browser import PLAYWRIGHT_AVAILABLE, BrowserTool

if not PLAYWRIGHT_AVAILABLE:
    print("[ERROR] Playwright not installed.")
    print("  Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# Mini web app HTML
_APP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hauba Demo</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
        .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }
        h1 { font-size: 2.5rem; margin-bottom: 8px; background: linear-gradient(135deg, #38bdf8, #818cf8);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: #94a3b8; font-size: 1.1rem; margin-bottom: 32px; }
        .log { background: #1e293b; border-radius: 12px; padding: 20px; margin-top: 24px;
               font-family: 'Cascadia Code', monospace; font-size: 0.9rem; border: 1px solid #334155;
               max-height: 300px; overflow-y: auto; }
        .log-entry { padding: 4px 0; border-bottom: 1px solid #1e293b; }
        .log-entry.action { color: #38bdf8; }
        .log-entry.success { color: #22c55e; }
        .log-entry.info { color: #94a3b8; }
        .card { background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px;
                border: 1px solid #334155; }
        .card h2 { color: #38bdf8; margin-bottom: 12px; }
        input[type="text"] { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #475569;
                             background: #0f172a; color: #e2e8f0; font-size: 1rem; margin-bottom: 12px; }
        button { padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer;
                 font-size: 1rem; font-weight: 600; }
        .btn-primary { background: #3b82f6; color: white; }
        #task-list { list-style: none; margin-top: 16px; }
        #task-list li { padding: 12px; background: #0f172a; border-radius: 8px; margin-bottom: 8px;
                        display: flex; justify-content: space-between; border: 1px solid #334155; }
        .btn-success { background: #22c55e; color: white; padding: 8px 16px; border-radius: 6px;
                       border: none; cursor: pointer; font-weight: 600; }
        .btn-danger { background: #ef4444; color: white; padding: 8px 16px; border-radius: 6px;
                      border: none; cursor: pointer; font-weight: 600; margin-left: 8px; }
        #status { margin-top: 24px; padding: 16px; background: #1e293b; border-radius: 8px;
                  text-align: center; border: 1px solid #334155; color: #38bdf8; font-weight: 600; }
        .stats { display: flex; gap: 20px; margin-top: 20px; }
        .stat { flex: 1; text-align: center; padding: 16px; background: #1e293b; border-radius: 8px;
                border: 1px solid #334155; }
        .stat-value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
        .stat-label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hauba AI Workstation</h1>
        <p class="subtitle">Browser Automation Demo</p>

        <div class="card">
            <h2>Add Task</h2>
            <input type="text" id="task-input" placeholder="What needs to be done?" />
            <button class="btn-primary" id="add-btn" onclick="addTask()">Add Task</button>
        </div>

        <div class="card">
            <h2>Tasks</h2>
            <ul id="task-list"></ul>
        </div>

        <div class="stats">
            <div class="stat"><div class="stat-value" id="total-count">0</div><div class="stat-label">Total</div></div>
            <div class="stat"><div class="stat-value" id="active-count">0</div><div class="stat-label">Active</div></div>
            <div class="stat"><div class="stat-value" id="done-count">0</div><div class="stat-label">Done</div></div>
        </div>

        <div id="status">Waiting for Hauba...</div>

        <div class="log" id="log"></div>
    </div>

    <script>
        let tasks = [];

        function log(msg, cls) {
            const el = document.getElementById('log');
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + (cls || 'info');
            entry.textContent = new Date().toLocaleTimeString() + ' | ' + msg;
            el.appendChild(entry);
            el.scrollTop = el.scrollHeight;
        }

        function addTask() {
            const input = document.getElementById('task-input');
            const text = input.value.trim();
            if (!text) return;
            tasks.push({ text, completed: false, id: Date.now() });
            input.value = '';
            render();
            log('Task added: ' + text, 'action');
            document.getElementById('status').textContent = 'Task added: ' + text;
        }

        function toggleTask(id) {
            const task = tasks.find(t => t.id === id);
            if (task) { task.completed = !task.completed; render();
                log(task.completed ? 'Completed: ' + task.text : 'Reopened: ' + task.text, 'success');
                document.getElementById('status').textContent = task.completed ? 'Task completed!' : 'Task reopened'; }
        }

        function deleteTask(id) {
            tasks = tasks.filter(t => t.id !== id);
            render(); log('Task deleted', 'action');
        }

        function render() {
            const list = document.getElementById('task-list');
            list.innerHTML = tasks.map(t => `
                <li style="${t.completed ? 'opacity:0.5; text-decoration:line-through;' : ''}">
                    <span>${t.text}</span>
                    <div>
                        <button class="btn-success" onclick="toggleTask(${t.id})">${t.completed ? 'Undo' : 'Done'}</button>
                        <button class="btn-danger" onclick="deleteTask(${t.id})">Del</button>
                    </div>
                </li>
            `).join('');
            const total = tasks.length, done = tasks.filter(t => t.completed).length;
            document.getElementById('total-count').textContent = total;
            document.getElementById('active-count').textContent = total - done;
            document.getElementById('done-count').textContent = done;
        }

        document.getElementById('task-input').addEventListener('keypress', e => { if (e.key === 'Enter') addTask(); });
        log('Demo app loaded, waiting for automation...', 'info');
    </script>
</body>
</html>
"""


class _DemoHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_APP_HTML.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        pass


def _print_step(step: int, msg: str) -> None:
    print(f"\n  \033[36m[Step {step}]\033[0m {msg}")


async def run_demo(headless: bool = False) -> None:
    """Run the visual browser automation demo."""
    # Start local server
    server = HTTPServer(("127.0.0.1", 0), _DemoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"

    print("\n" + "=" * 60)
    print("  \033[1;36mHauba AI Workstation — Browser Automation Demo\033[0m")
    print("=" * 60)
    print(f"\n  Local server: {url}")
    print(f"  Browser mode: {'headless' if headless else 'HEADED (visible)'}")

    # Create browser tool
    browser = BrowserTool(session_name="demo", headless=headless, stealth=False)

    try:
        # Step 1: Navigate
        _print_step(1, "Navigating to demo app...")
        result = await browser.execute(action="navigate", url=url)
        print(f"    -> {result.output}")
        await asyncio.sleep(1)

        # Step 2: Extract page title
        _print_step(2, "Reading page content...")
        result = await browser.execute(action="extract", selector="h1")
        print(f"    -> Found: {result.output}")
        await asyncio.sleep(0.5)

        # Step 3: Add tasks
        tasks = [
            "Build REST API with FastAPI",
            "Write Playwright integration tests",
            "Deploy to Railway with CI/CD",
            "Add video editing pipeline",
        ]
        _print_step(3, f"Adding {len(tasks)} tasks...")
        for i, task in enumerate(tasks, 1):
            await browser.execute(action="type", selector="#task-input", text=task)
            await browser.execute(action="click", selector="#add-btn")
            print(f"    -> [{i}/{len(tasks)}] Added: {task}")
            await asyncio.sleep(0.5)

        # Step 4: Verify stats
        _print_step(4, "Verifying task count...")
        total = await browser.execute(action="extract", selector="#total-count")
        print(f"    -> Total tasks: {total.output}")
        await asyncio.sleep(0.5)

        # Step 5: Complete first two tasks
        _print_step(5, "Completing tasks...")
        for i in range(2):
            await browser.execute(
                action="click", selector=f"#task-list li:nth-child({i + 1}) .btn-success"
            )
            print(f"    -> Completed task {i + 1}")
            await asyncio.sleep(0.5)

        # Step 6: Check stats
        _print_step(6, "Checking completion stats...")
        done = await browser.execute(action="extract", selector="#done-count")
        active = await browser.execute(action="extract", selector="#active-count")
        print(f"    -> Done: {done.output}, Active: {active.output}")
        await asyncio.sleep(0.5)

        # Step 7: Scroll
        _print_step(7, "Scrolling page...")
        await browser.execute(action="scroll", direction="down", amount=200)
        print("    -> Scrolled down 200px")
        await asyncio.sleep(0.5)

        # Step 8: Screenshot
        screenshots_dir = Path.home() / ".hauba" / "agents" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        shot_path = str(screenshots_dir / "demo_screenshot.png")
        _print_step(8, "Taking screenshot...")
        result = await browser.execute(action="screenshot", path=shot_path)
        print(f"    -> {result.output}")
        await asyncio.sleep(0.5)

        # Step 9: Execute JavaScript
        _print_step(9, "Running JavaScript...")
        result = await browser.execute(
            action="evaluate",
            script="JSON.stringify({tasks: document.querySelectorAll('#task-list li').length, url: location.href})",
        )
        print(f"    -> {result.output}")

        # Done
        print("\n" + "=" * 60)
        print("  \033[1;32mDemo complete! All browser actions successful.\033[0m")
        print("=" * 60)

        if not headless:
            print("\n  \033[33mBrowser window will close in 5 seconds...\033[0m")
            await asyncio.sleep(5)

    finally:
        await browser.close()
        server.shutdown()


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    asyncio.run(run_demo(headless=headless))
