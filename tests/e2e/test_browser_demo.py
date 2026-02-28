"""End-to-end Playwright browser tests — real browser, real interactions.

These tests spin up a local HTTP server with a mini web app and use
Hauba's BrowserTool to navigate, click, type, extract, and screenshot.

Run with:
    pytest tests/e2e/test_browser_demo.py -v --headed   # visible browser
    pytest tests/e2e/test_browser_demo.py -v             # headless (CI)

Mark: requires playwright chromium to be installed.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from hauba.tools.browser import PLAYWRIGHT_AVAILABLE, BrowserTool

# Skip entire module if Playwright is not installed
pytestmark = pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")

# ---------- Local test web app ----------

_APP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hauba Demo App</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
        .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }
        h1 { font-size: 2.5rem; margin-bottom: 8px; background: linear-gradient(135deg, #38bdf8, #818cf8);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: #94a3b8; font-size: 1.1rem; margin-bottom: 32px; }
        .card { background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px;
                border: 1px solid #334155; }
        .card h2 { color: #38bdf8; margin-bottom: 12px; font-size: 1.3rem; }
        input[type="text"] { width: 100%; padding: 12px 16px; border-radius: 8px; border: 1px solid #475569;
                             background: #0f172a; color: #e2e8f0; font-size: 1rem; margin-bottom: 12px; }
        button { padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer;
                 font-size: 1rem; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-success { background: #22c55e; color: white; }
        .btn-danger { background: #ef4444; color: white; margin-left: 8px; }
        #task-list { list-style: none; margin-top: 16px; }
        #task-list li { padding: 12px 16px; background: #0f172a; border-radius: 8px;
                        margin-bottom: 8px; display: flex; justify-content: space-between;
                        align-items: center; border: 1px solid #334155; }
        #task-list li .task-text { flex: 1; }
        #task-list li.completed .task-text { text-decoration: line-through; color: #64748b; }
        .status-bar { margin-top: 24px; padding: 16px; background: #1e293b;
                      border-radius: 8px; text-align: center; border: 1px solid #334155; }
        #status { color: #38bdf8; font-weight: 600; }
        #task-count { color: #94a3b8; font-size: 0.9rem; margin-top: 8px; }
        .stats { display: flex; gap: 20px; margin-top: 20px; }
        .stat { flex: 1; text-align: center; padding: 16px; background: #1e293b;
                border-radius: 8px; border: 1px solid #334155; }
        .stat-value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
        .stat-label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hauba AI Workstation</h1>
        <p class="subtitle">Task Manager Demo &mdash; Powered by Playwright</p>

        <div class="card">
            <h2>Add Task</h2>
            <input type="text" id="task-input" placeholder="What needs to be done?" />
            <button class="btn-primary" id="add-btn" onclick="addTask()">Add Task</button>
        </div>

        <div class="card">
            <h2>Tasks</h2>
            <ul id="task-list"></ul>
            <div id="empty-msg" style="color: #64748b; text-align: center; padding: 20px;">
                No tasks yet. Add one above!
            </div>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-count">0</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="active-count">0</div>
                <div class="stat-label">Active</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="done-count">0</div>
                <div class="stat-label">Completed</div>
            </div>
        </div>

        <div class="status-bar">
            <div id="status">Ready</div>
            <div id="task-count">0 tasks</div>
        </div>
    </div>

    <script>
        let tasks = [];

        function addTask() {
            const input = document.getElementById('task-input');
            const text = input.value.trim();
            if (!text) return;

            tasks.push({ text, completed: false, id: Date.now() });
            input.value = '';
            render();
            updateStatus('Task added: ' + text);
        }

        function toggleTask(id) {
            const task = tasks.find(t => t.id === id);
            if (task) {
                task.completed = !task.completed;
                render();
                updateStatus(task.completed ? 'Task completed!' : 'Task reopened');
            }
        }

        function deleteTask(id) {
            tasks = tasks.filter(t => t.id !== id);
            render();
            updateStatus('Task deleted');
        }

        function render() {
            const list = document.getElementById('task-list');
            const empty = document.getElementById('empty-msg');

            if (tasks.length === 0) {
                list.innerHTML = '';
                empty.style.display = 'block';
            } else {
                empty.style.display = 'none';
                list.innerHTML = tasks.map(t => `
                    <li class="${t.completed ? 'completed' : ''}">
                        <span class="task-text">${t.text}</span>
                        <div>
                            <button class="btn-success" onclick="toggleTask(${t.id})">
                                ${t.completed ? 'Undo' : 'Done'}
                            </button>
                            <button class="btn-danger" onclick="deleteTask(${t.id})">Del</button>
                        </div>
                    </li>
                `).join('');
            }

            const total = tasks.length;
            const done = tasks.filter(t => t.completed).length;
            const active = total - done;

            document.getElementById('total-count').textContent = total;
            document.getElementById('active-count').textContent = active;
            document.getElementById('done-count').textContent = done;
            document.getElementById('task-count').textContent = `${total} task${total !== 1 ? 's' : ''}`;
        }

        function updateStatus(msg) {
            document.getElementById('status').textContent = msg;
        }

        // Handle Enter key
        document.getElementById('task-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addTask();
        });
    </script>
</body>
</html>
"""


class _DemoHandler(SimpleHTTPRequestHandler):
    """Serve the demo HTML from memory."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_APP_HTML.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress server logs during tests


@pytest.fixture(scope="module")
def demo_server() -> Generator[str, None, None]:
    """Start a local HTTP server with the demo app."""
    server = HTTPServer(("127.0.0.1", 0), _DemoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    yield url
    server.shutdown()


@pytest.fixture
def browser_tool(request: pytest.FixtureRequest) -> BrowserTool:
    """Create a BrowserTool. Use --headed flag to see the browser."""
    headed = request.config.getoption("--headed", default=False)
    return BrowserTool(
        session_name="e2e-test",
        headless=not headed,
        stealth=False,
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --headed flag for visible browser tests."""
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser tests in headed mode (visible browser window)",
    )


# ---------- Tests ----------


class TestBrowserNavigate:
    """Test navigating to the demo app."""

    async def test_navigate_to_demo(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Navigate to the demo app and verify the page loads."""
        try:
            result = await browser_tool.execute(action="navigate", url=demo_server)
            assert result.success, f"Navigate failed: {result.error}"
            assert "Navigated to" in result.output
        finally:
            await browser_tool.close()

    async def test_extract_page_title(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Extract the page heading text."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(action="extract", selector="h1")
            assert result.success
            assert "Hauba AI Workstation" in result.output
        finally:
            await browser_tool.close()

    async def test_extract_subtitle(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Extract the subtitle text."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(action="extract", selector=".subtitle")
            assert result.success
            assert "Playwright" in result.output
        finally:
            await browser_tool.close()


class TestBrowserInteraction:
    """Test clicking, typing, and form interactions."""

    async def test_type_into_input(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Type a task name into the input field."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(
                action="type", selector="#task-input", text="Build a REST API"
            )
            assert result.success
            assert "Typed" in result.output
        finally:
            await browser_tool.close()

    async def test_add_task_via_button(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Type a task and click the Add button."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            await browser_tool.execute(
                action="type", selector="#task-input", text="Deploy to production"
            )
            result = await browser_tool.execute(action="click", selector="#add-btn")
            assert result.success

            # Verify the task appears in the list
            extract = await browser_tool.execute(action="extract", selector="#task-list")
            assert extract.success
            assert "Deploy to production" in extract.output
        finally:
            await browser_tool.close()

    async def test_add_multiple_tasks(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Add multiple tasks and verify the counter updates."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)

            tasks = ["Write unit tests", "Set up CI/CD", "Update README"]
            for task in tasks:
                await browser_tool.execute(action="type", selector="#task-input", text=task)
                await browser_tool.execute(action="click", selector="#add-btn")

            # Check total count
            count = await browser_tool.execute(action="extract", selector="#total-count")
            assert count.success
            assert "3" in count.output

            # Check all tasks are in the list
            list_text = await browser_tool.execute(action="extract", selector="#task-list")
            for task in tasks:
                assert task in list_text.output
        finally:
            await browser_tool.close()

    async def test_complete_task(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Add a task, then mark it as done."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)

            # Add a task
            await browser_tool.execute(action="type", selector="#task-input", text="Fix login bug")
            await browser_tool.execute(action="click", selector="#add-btn")

            # Click "Done" button on the task
            result = await browser_tool.execute(action="click", selector="#task-list .btn-success")
            assert result.success

            # Verify done count updated
            done = await browser_tool.execute(action="extract", selector="#done-count")
            assert done.success
            assert "1" in done.output

            # Verify status message
            status = await browser_tool.execute(action="extract", selector="#status")
            assert status.success
            assert "completed" in status.output.lower()
        finally:
            await browser_tool.close()


class TestBrowserScreenshot:
    """Test screenshot capability."""

    async def test_screenshot_demo_app(
        self, browser_tool: BrowserTool, demo_server: str, tmp_path: Path
    ) -> None:
        """Take a screenshot of the demo app."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)

            # Add some tasks for a nice screenshot
            for task in ["Build API", "Write Tests", "Deploy"]:
                await browser_tool.execute(action="type", selector="#task-input", text=task)
                await browser_tool.execute(action="click", selector="#add-btn")

            # Take screenshot
            shot_path = str(tmp_path / "hauba_demo.png")
            result = await browser_tool.execute(action="screenshot", path=shot_path)
            assert result.success
            assert Path(shot_path).exists()
            assert Path(shot_path).stat().st_size > 1000  # should be a real image
        finally:
            await browser_tool.close()


class TestBrowserAdvanced:
    """Test advanced browser features — scroll, evaluate, wait."""

    async def test_evaluate_javascript(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Execute JavaScript in the page context."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(
                action="evaluate", script="document.title || 'Hauba Demo App'"
            )
            assert result.success
            assert "Hauba" in result.output
        finally:
            await browser_tool.close()

    async def test_scroll_page(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Scroll the page down and back up."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)

            down = await browser_tool.execute(action="scroll", direction="down", amount=300)
            assert down.success
            assert "Scrolled down" in down.output

            up = await browser_tool.execute(action="scroll", direction="up", amount=300)
            assert up.success
            assert "Scrolled up" in up.output
        finally:
            await browser_tool.close()

    async def test_wait_for_element(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Wait for an element to be visible."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(action="wait", selector="h1", timeout=5000)
            assert result.success
            assert "visible" in result.output.lower()
        finally:
            await browser_tool.close()

    async def test_extract_full_page(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Extract all text content from the page."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            result = await browser_tool.execute(action="extract")
            assert result.success
            assert "Hauba AI Workstation" in result.output
            assert "Task Manager Demo" in result.output
        finally:
            await browser_tool.close()

    async def test_page_info(self, browser_tool: BrowserTool, demo_server: str) -> None:
        """Get current page URL and title."""
        try:
            await browser_tool.execute(action="navigate", url=demo_server)
            info = await browser_tool.get_page_info()
            assert demo_server in info["url"]
        finally:
            await browser_tool.close()


class TestBrowserFullWorkflow:
    """Full end-to-end workflow — like a real Hauba session."""

    async def test_full_task_management_workflow(
        self, browser_tool: BrowserTool, demo_server: str, tmp_path: Path
    ) -> None:
        """Complete workflow: navigate, add tasks, complete one, screenshot."""
        try:
            # 1. Navigate to the app
            nav = await browser_tool.execute(action="navigate", url=demo_server)
            assert nav.success

            # 2. Verify the page loaded
            title = await browser_tool.execute(action="extract", selector="h1")
            assert "Hauba AI Workstation" in title.output

            # 3. Add three tasks
            task_names = [
                "Design database schema",
                "Implement REST API endpoints",
                "Write integration tests",
            ]
            for name in task_names:
                await browser_tool.execute(action="type", selector="#task-input", text=name)
                await browser_tool.execute(action="click", selector="#add-btn")

            # 4. Verify all tasks appear
            tasks = await browser_tool.execute(action="extract", selector="#task-list")
            for name in task_names:
                assert name in tasks.output

            # 5. Verify stats
            total = await browser_tool.execute(action="extract", selector="#total-count")
            assert "3" in total.output

            active = await browser_tool.execute(action="extract", selector="#active-count")
            assert "3" in active.output

            # 6. Complete the first task
            await browser_tool.execute(
                action="click", selector="#task-list li:first-child .btn-success"
            )

            # 7. Verify done count
            done = await browser_tool.execute(action="extract", selector="#done-count")
            assert "1" in done.output

            # 8. Take final screenshot
            shot = str(tmp_path / "workflow_complete.png")
            result = await browser_tool.execute(action="screenshot", path=shot)
            assert result.success
            assert Path(shot).exists()

            # 9. Check status bar
            status = await browser_tool.execute(action="extract", selector="#status")
            assert status.success

        finally:
            await browser_tool.close()
