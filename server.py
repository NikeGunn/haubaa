"""Hauba.tech — Install script server & landing page.

Serves:
  GET /              → Landing page
  GET /install.sh    → Bash installer
  GET /install.ps1   → PowerShell installer
  GET /health        → Health check
"""

import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = Path(__file__).parent

INSTALL_SH = (BASE_DIR / "install.sh").read_text(encoding="utf-8")
INSTALL_PS1 = (BASE_DIR / "install.ps1").read_text(encoding="utf-8")

LANDING_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hauba — AI Agent Operating System</title>
  <meta name="description" content="One command. An AI engineering team at your service. Open-source AI agent framework.">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
      background: #0a0a0a;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }
    .container { max-width: 700px; text-align: center; }
    .logo {
      font-size: 3rem;
      font-weight: 800;
      background: linear-gradient(135deg, #00d4ff, #7b2fff, #ff2d87);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 0.5rem;
    }
    .tagline {
      font-size: 1.1rem;
      color: #888;
      margin-bottom: 2rem;
    }
    .highlight { color: #00d4ff; }
    .install-box {
      background: #111;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 1.5rem;
      margin: 1.5rem 0;
      text-align: left;
    }
    .install-box .label {
      font-size: 0.75rem;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 0.5rem;
    }
    .install-box code {
      display: block;
      font-size: 0.95rem;
      color: #00d4ff;
      padding: 0.5rem 0;
      word-break: break-all;
    }
    .features {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
      margin: 2rem 0;
      text-align: left;
    }
    .feature {
      background: #111;
      border: 1px solid #222;
      border-radius: 6px;
      padding: 1rem;
    }
    .feature h3 { font-size: 0.85rem; color: #00d4ff; margin-bottom: 0.3rem; }
    .feature p { font-size: 0.8rem; color: #888; }
    .links { margin-top: 2rem; }
    .links a {
      color: #7b2fff;
      text-decoration: none;
      margin: 0 1rem;
      font-size: 0.9rem;
    }
    .links a:hover { color: #00d4ff; }
    .badge {
      display: inline-block;
      background: #1a1a2e;
      border: 1px solid #333;
      border-radius: 4px;
      padding: 0.2rem 0.6rem;
      font-size: 0.7rem;
      color: #00d4ff;
      margin: 0.5rem 0.25rem;
    }
    @media (max-width: 600px) {
      .features { grid-template-columns: 1fr; }
      .logo { font-size: 2rem; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1 class="logo">HAUBA</h1>
    <p class="tagline">One command. An <span class="highlight">AI engineering team</span> at your service.</p>

    <div>
      <span class="badge">Python 3.11+</span>
      <span class="badge">Open Source</span>
      <span class="badge">MIT License</span>
      <span class="badge">Offline Capable</span>
    </div>

    <div class="install-box">
      <div class="label">macOS / Linux</div>
      <code>curl -fsSL https://hauba.tech/install.sh | sh</code>
    </div>

    <div class="install-box">
      <div class="label">Windows (PowerShell)</div>
      <code>irm hauba.tech/install.ps1 | iex</code>
    </div>

    <div class="install-box">
      <div class="label">pip</div>
      <code>pip install hauba</code>
    </div>

    <div class="features">
      <div class="feature">
        <h3>Multi-Agent Teams</h3>
        <p>Director, SubAgents, Workers — like a real engineering company.</p>
      </div>
      <div class="feature">
        <h3>Zero Hallucination</h3>
        <p>TaskLedger with SHA-256 hash-chain guarantees every output is verified.</p>
      </div>
      <div class="feature">
        <h3>Works Offline</h3>
        <p>Full support for Ollama local models. No internet required.</p>
      </div>
      <div class="feature">
        <h3>Skills &amp; Strategies</h3>
        <p>Composable .md skills and .yaml cognitive playbooks.</p>
      </div>
    </div>

    <div class="links">
      <a href="https://github.com/NikeGunn/haubaa">GitHub</a>
      <a href="https://pypi.org/project/hauba/">PyPI</a>
      <a href="https://github.com/NikeGunn/haubaa#readme">Docs</a>
      <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
    </div>
  </div>
</body>
</html>
"""


class HaubaHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/install.sh":
            self._send_text(INSTALL_SH, "text/plain")
        elif self.path == "/install.ps1":
            self._send_text(INSTALL_PS1, "text/plain")
        elif self.path == "/health":
            self._send_text('{"status":"ok"}', "application/json")
        elif self.path == "/" or self.path == "":
            self._send_text(LANDING_PAGE, "text/html")
        else:
            self.send_error(404)

    def _send_text(self, content: str, content_type: str) -> None:
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[hauba.tech] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), HaubaHandler)
    print(f"[hauba.tech] Serving on port {PORT}")
    print(f"[hauba.tech] Routes: / /install.sh /install.ps1 /health")
    server.serve_forever()
