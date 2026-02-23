"""Hauba.tech — Install script server & landing page.

Serves:
  GET /              → Landing page
  GET /install.sh    → Bash installer
  GET /install.ps1   → PowerShell installer
  GET /health        → Health check
  GET /favicon.png   → Favicon (Hauba mascot)
  GET /api/version   → Latest GitHub release info (JSON, cached 5 min)
"""

import json
import os
import threading
import time
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = Path(__file__).parent

# ── GitHub release cache ──────────────────────────────────────────────────────
GITHUB_REPO = "NikeGunn/haubaa"
_release_cache: dict = {}
_release_cache_lock = threading.Lock()
_CACHE_TTL = 300  # seconds (5 min)


def _fetch_latest_release() -> dict:
    """Fetch latest release from GitHub API. Returns parsed JSON or raises."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "hauba.tech/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def get_release_info() -> dict:
    """Return cached release info, refreshing every _CACHE_TTL seconds."""
    with _release_cache_lock:
        now = time.monotonic()
        if _release_cache.get("expires", 0) > now:
            return _release_cache["data"]
        try:
            data = _fetch_latest_release()
            tag = data.get("tag_name", "v0.1.1")
            prerelease = data.get("prerelease", False)
            # Determine label: pre-release flag OR semver major == 0 → Beta
            parts = tag.lstrip("v").split(".")
            is_beta = prerelease or (parts[0] == "0")
            label = "Public Beta" if is_beta else "Stable"
            result = {"version": tag, "label": label, "prerelease": prerelease}
        except Exception as exc:
            print(f"[hauba.tech] GitHub release fetch failed: {exc}")
            result = {"version": "v0.1.1", "label": "Public Beta", "prerelease": True}
        _release_cache["data"] = result
        _release_cache["expires"] = now + _CACHE_TTL
        return result

INSTALL_SH = (BASE_DIR / "install.sh").read_text(encoding="utf-8")
INSTALL_PS1 = (BASE_DIR / "install.ps1").read_text(encoding="utf-8")

_favicon_path = BASE_DIR / "static" / "favicon.png"
FAVICON_BYTES: bytes | None = _favicon_path.read_bytes() if _favicon_path.exists() else None

LANDING_PAGE = """\
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hauba — The AI That Actually Ships Code</title>
  <meta name="description" content="One command. An AI engineering team at your service. Open-source AI agent framework that thinks before it acts.">
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --accent: #6C5CE7;
      --accent-soft: rgba(108,92,231,0.12);
      --accent-glow: rgba(108,92,231,0.25);
      --accent-text: #fff;
    }
    [data-theme="dark"] {
      --white: #f5f5f7;
      --gray-1: #b0b0b8;
      --gray-2: #6e6e78;
      --gray-3: #3a3a44;
      --gray-4: #1c1c24;
      --bg: #0a0a0f;
      --bg-card: #111118;
      --bg-elevated: #16161f;
      --border: #1f1f2a;
      --border-hover: #2e2e3c;
      --code-bg: #0d0d14;
      --shadow-panel: rgba(0,0,0,0.5);
      --glow-bg: rgba(108,92,231,0.06);
      --noise-opacity: 0.025;
      --mascot-eye: #0a0a0f;
      --mascot-mouth: #1a0505;
      --mascot-mouth-inner: #0a0000;
      --success: #4caf50;
      --fn-color: #64b5f6;
    }
    [data-theme="light"] {
      --white: #111118;
      --gray-1: #3a3a44;
      --gray-2: #6e6e78;
      --gray-3: #a0a0b0;
      --gray-4: #d0d0da;
      --bg: #f5f5f8;
      --bg-card: #ffffff;
      --bg-elevated: #f0f0f5;
      --border: #e0e0ea;
      --border-hover: #c8c8d8;
      --code-bg: #eeeef4;
      --shadow-panel: rgba(0,0,0,0.1);
      --glow-bg: rgba(108,92,231,0.04);
      --noise-opacity: 0.015;
      --mascot-eye: #1a1a2e;
      --mascot-mouth: #2a1525;
      --mascot-mouth-inner: #1a0a15;
      --success: #2e7d32;
      --fn-color: #1565c0;
      --accent-text: #fff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--white);
      min-height: 100vh; overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
      transition: background 0.3s ease, color 0.3s ease;
    }

    /* ═══ SUBTLE BG ═══ */
    .bg-noise {
      position: fixed; inset: 0; z-index: 0; pointer-events: none; opacity: var(--noise-opacity);
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
      background-repeat: repeat; background-size: 256px;
    }
    .bg-glow {
      position: fixed; top: -300px; left: 50%; transform: translateX(-50%);
      width: 800px; height: 600px; z-index: 0; pointer-events: none;
      background: radial-gradient(ellipse, var(--glow-bg) 0%, transparent 70%);
    }

    /* ═══ HERO ═══ */
    .hero {
      position: relative; z-index: 1;
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 4rem 2rem 4rem;
      text-align: center;
    }

    /* ═══ MASCOT — FIXED HOVER PANEL ═══ */
    .mascot-wrapper {
      margin-bottom: 2rem;
      position: relative; cursor: pointer;
      width: 120px; height: 148px;
    }
    .mascot-svg {
      width: 120px; height: 148px;
      filter: drop-shadow(0 0 30px var(--accent-glow));
      transition: filter 0.3s;
    }
    .mascot-wrapper:hover .mascot-svg {
      filter: drop-shadow(0 0 50px rgba(108,92,231,0.5));
    }

    /* HOVER PANEL — repositioned to the RIGHT, not top */
    .mascot-hover-panel {
      position: absolute;
      top: 50%; left: calc(100% + 16px);
      transform: translateY(-50%) scale(0.9);
      width: 240px; opacity: 0; pointer-events: none;
      transition: all 0.3s cubic-bezier(.34,1.56,.64,1);
      transform-origin: left center;
      z-index: 10;
    }
    .mascot-wrapper:hover .mascot-hover-panel {
      opacity: 1; transform: translateY(-50%) scale(1);
    }
    .mhp-inner {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 10px; padding: 0.75rem 1rem;
      font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
      text-align: left; position: relative;
      box-shadow: 0 8px 40px var(--shadow-panel);
    }
    /* Arrow pointing left toward mascot */
    .mhp-inner::after {
      content: ''; position: absolute; top: 50%; left: -7px; transform: translateY(-50%);
      width: 0; height: 0;
      border-top: 7px solid transparent; border-bottom: 7px solid transparent;
      border-right: 7px solid var(--border);
    }
    .mhp-inner::before {
      content: ''; position: absolute; top: 50%; left: -6px; transform: translateY(-50%);
      width: 0; height: 0;
      border-top: 6px solid transparent; border-bottom: 6px solid transparent;
      border-right: 6px solid var(--bg-card); z-index: 1;
    }
    .mhp-bar { display: flex; gap: 4px; margin-bottom: 6px; }
    .mhp-dot { width: 7px; height: 7px; border-radius: 50%; }
    .mhp-dot.r { background: #ff5f57; }
    .mhp-dot.y { background: #ffbd2e; }
    .mhp-dot.g { background: #28c840; }
    .mhp-file { font-size: 0.58rem; color: var(--gray-2); margin-bottom: 5px; }
    .mhp-line { margin: 1px 0; color: var(--gray-1); }
    .mhp-line .c-kw { color: var(--accent); }
    .mhp-line .c-fn { color: var(--fn-color); }
    .mhp-line .c-cm { color: var(--gray-3); }
    .mhp-status {
      margin-top: 6px; padding-top: 5px; border-top: 1px solid var(--border);
      font-size: 0.58rem; color: var(--success);
      display: flex; align-items: center; gap: 4px;
    }
    .mhp-cursor {
      display: inline-block; width: 5px; height: 0.8em;
      background: var(--accent); vertical-align: text-bottom;
      animation: cursorBlink 0.7s step-end infinite;
    }
    @keyframes cursorBlink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

    /* ═══ MASCOT ANIMATIONS ═══ */
    @keyframes bodyBounce {
      0%,100% { transform: translateY(0); }
      50% { transform: translateY(-5px); }
    }
    .mascot-body-group { animation: bodyBounce 2.2s ease-in-out infinite; }
    @keyframes eyeLook {
      0%,18% { transform: translate(0,0); }
      22%,34% { transform: translate(3px,-1px); }
      38%,52% { transform: translate(-3px,1px); }
      56%,68% { transform: translate(2px,2px); }
      72%,84% { transform: translate(-2px,-1px); }
      88%,100% { transform: translate(0,0); }
    }
    .eye-pupil { animation: eyeLook 4.5s ease-in-out infinite; }
    @keyframes blink {
      0%,40%,42%,100% { transform: scaleY(1); }
      41% { transform: scaleY(0.05); }
    }
    .eye-blink { animation: blink 4s infinite; transform-origin: center; }
    .eye-blink-r { animation: blink 4s infinite 0.6s; transform-origin: center; }
    @keyframes bellyJiggle {
      0%,100% { transform: scaleX(1) scaleY(1); }
      30% { transform: scaleX(1.015) scaleY(0.985); }
      65% { transform: scaleX(0.985) scaleY(1.015); }
    }
    .belly { animation: bellyJiggle 2.1s ease-in-out infinite; transform-origin: center 60%; }
    @keyframes armWaveL {
      0%,100% { transform: rotate(0deg); } 30% { transform: rotate(-18deg); } 65% { transform: rotate(6deg); }
    }
    @keyframes armWaveR {
      0%,100% { transform: rotate(0deg); } 30% { transform: rotate(18deg); } 65% { transform: rotate(-6deg); }
    }
    .arm-left { animation: armWaveL 2.6s ease-in-out infinite; transform-origin: 36px 70px; }
    .arm-right { animation: armWaveR 2.6s ease-in-out infinite 0.4s; transform-origin: 95px 70px; }

    /* ═══ LOGO — SUPER BOLD ═══ */
    .logo {
      font-family: 'Inter', sans-serif;
      font-size: 5.5rem; font-weight: 900; letter-spacing: -0.03em;
      color: var(--white);
      margin-bottom: 0.2rem; position: relative;
      line-height: 1;
    }
    .logo span {
      background: linear-gradient(135deg, var(--accent) 0%, #a29bfe 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .version-tag {
      display: inline-block; background: var(--accent-soft);
      border: 1px solid rgba(108,92,231,0.25); border-radius: 20px;
      padding: 0.2rem 0.8rem; font-size: 0.7rem; font-weight: 600;
      color: var(--accent); margin-bottom: 1.5rem; letter-spacing: 0.04em;
    }

    /* ═══ TAGLINE ═══ */
    .hero-tagline {
      font-size: 1.4rem; font-weight: 300; color: var(--gray-1);
      max-width: 580px; line-height: 1.6; margin-bottom: 0.6rem;
    }
    .hero-tagline strong { color: var(--white); font-weight: 600; }
    .hero-sub {
      font-size: 1rem; color: var(--gray-2); max-width: 480px;
      line-height: 1.6; margin-bottom: 2.5rem;
    }

    /* ═══ TERMINAL DEMO ═══ */
    .terminal {
      width: 100%; max-width: 540px;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 12px; overflow: hidden; margin-bottom: 2.5rem;
      text-align: left;
    }
    .terminal-bar {
      display: flex; align-items: center; gap: 6px;
      padding: 0.7rem 1rem; border-bottom: 1px solid var(--border);
      background: var(--bg-card);
    }
    .terminal-dot { width: 10px; height: 10px; border-radius: 50%; }
    .terminal-dot.r { background: #ff5f57; }
    .terminal-dot.y { background: #ffbd2e; }
    .terminal-dot.g { background: #28c840; }
    .terminal-title {
      flex: 1; text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.68rem; color: var(--gray-3);
    }
    .terminal-body {
      padding: 1.2rem 1.4rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem; line-height: 1.8;
    }
    .t-prompt { color: var(--accent); }
    .t-cmd { color: var(--white); }
    .t-comment { color: var(--gray-3); }
    .t-output { color: var(--gray-2); }
    .t-success { color: var(--success); }
    .t-cursor {
      display: inline-block; width: 8px; height: 1.1em;
      background: var(--accent); vertical-align: text-bottom;
      animation: cursorBlink 0.8s step-end infinite;
    }

    /* ═══ DOWNLOAD SECTION ═══ */
    .download-section {
      width: 100%; max-width: 540px; margin-bottom: 2.5rem;
    }
    .download-auto {
      display: flex; align-items: center; justify-content: center; gap: 0.6rem;
      padding: 0.85rem 2rem;
      background: var(--accent); color: var(--accent-text);
      border: none; border-radius: 10px; cursor: pointer;
      font-family: 'Inter', sans-serif; font-size: 0.95rem; font-weight: 700;
      transition: all 0.2s; width: 100%;
      box-shadow: 0 4px 24px var(--accent-glow);
    }
    .download-auto:hover { transform: translateY(-2px); box-shadow: 0 8px 36px rgba(108,92,231,0.35); }
    .download-auto svg { flex-shrink: 0; }
    .download-other {
      text-align: center; margin-top: 0.7rem;
      font-size: 0.75rem; color: var(--gray-3);
    }
    .download-other a { color: var(--gray-2); text-decoration: none; transition: color 0.2s; }
    .download-other a:hover { color: var(--accent); }

    /* Install options (expanded via "other platforms") */
    .install-options {
      display: none; margin-top: 1rem;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 10px; overflow: hidden;
    }
    .install-options.open { display: block; }
    .install-opt {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 1.2rem;
      border-bottom: 1px solid var(--border);
      font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    }
    .install-opt:last-child { border-bottom: none; }
    .install-opt-label { color: var(--gray-2); font-size: 0.7rem; font-weight: 600; min-width: 90px; font-family: 'Inter', sans-serif; }
    .install-opt-cmd { color: var(--accent); flex: 1; margin: 0 1rem; word-break: break-all; }
    .install-opt .copy-btn {
      background: rgba(108,92,231,0.1); border: 1px solid rgba(108,92,231,0.2);
      color: var(--accent); border-radius: 5px; padding: 0.25rem 0.55rem;
      font-size: 0.65rem; cursor: pointer; font-family: inherit; font-weight: 600;
      transition: all 0.2s; white-space: nowrap;
    }
    .install-opt .copy-btn:hover { background: rgba(108,92,231,0.2); }
    .install-opt .copy-btn.copied { background: rgba(76,175,80,0.15); border-color: #4caf50; color: #4caf50; }

    /* ═══ CTA ROW ═══ */
    .cta-row { display: flex; gap: 0.8rem; justify-content: center; margin-bottom: 3rem; }
    .cta-gh {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: var(--bg-card); border: 1px solid var(--border);
      color: var(--white); padding: 0.65rem 1.4rem; border-radius: 8px;
      text-decoration: none; font-weight: 600; font-size: 0.85rem;
      transition: all 0.2s;
    }
    .cta-gh:hover { border-color: var(--border-hover); background: var(--bg-elevated); transform: translateY(-1px); }
    .cta-docs {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: transparent; border: 1px solid var(--border);
      color: var(--gray-2); padding: 0.65rem 1.4rem; border-radius: 8px;
      text-decoration: none; font-weight: 500; font-size: 0.85rem;
      transition: all 0.2s;
    }
    .cta-docs:hover { border-color: var(--border-hover); color: var(--white); }

    /* ═══ SECTIONS ═══ */
    .section {
      position: relative; z-index: 1;
      padding: 5rem 2rem; max-width: 1000px; margin: 0 auto;
    }
    .section-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem; font-weight: 600; color: var(--accent);
      letter-spacing: 0.1em; text-transform: uppercase;
      margin-bottom: 0.5rem; text-align: center;
    }
    .section-title {
      text-align: center; font-size: 2.2rem; font-weight: 800;
      letter-spacing: -0.02em; margin-bottom: 0.5rem;
    }
    .section-subtitle {
      text-align: center; color: var(--gray-2); font-size: 0.95rem;
      margin-bottom: 3rem; max-width: 520px; margin-left: auto; margin-right: auto;
    }

    /* ═══ FEATURES ═══ */
    .features {
      display: grid; grid-template-columns: repeat(3,1fr);
      gap: 1px; background: var(--border); border-radius: 14px; overflow: hidden;
      border: 1px solid var(--border);
    }
    .feature {
      background: var(--bg-card); padding: 2rem 1.6rem;
      transition: background 0.3s;
    }
    .feature:hover { background: var(--bg-elevated); }
    .feature-icon {
      width: 40px; height: 40px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.1rem; margin-bottom: 1rem;
      background: var(--accent-soft); color: var(--accent);
    }
    .feature h3 { font-size: 0.92rem; font-weight: 700; margin-bottom: 0.4rem; }
    .feature p { font-size: 0.82rem; color: var(--gray-2); line-height: 1.6; }

    /* ═══ HOW IT WORKS ═══ */
    .steps {
      display: grid; grid-template-columns: repeat(3, 1fr);
      gap: 2rem; max-width: 800px; margin: 0 auto;
    }
    .step { text-align: center; }
    .step-num {
      width: 44px; height: 44px; border-radius: 50%;
      background: var(--accent-soft); color: var(--accent);
      display: inline-flex; align-items: center; justify-content: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem; font-weight: 700; margin-bottom: 1rem;
    }
    .step h3 { font-size: 0.9rem; font-weight: 700; margin-bottom: 0.4rem; }
    .step p { font-size: 0.8rem; color: var(--gray-2); line-height: 1.55; }

    /* ═══ ARCH ═══ */
    .arch-card {
      max-width: 680px; margin: 0 auto;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 12px; padding: 1.8rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem; line-height: 1.8; color: var(--gray-1);
    }
    .a-cm { color: var(--gray-3); }
    .a-k { color: var(--accent); }
    .a-v { color: var(--fn-color); }
    .a-t { color: var(--gray-2); }

    /* ═══ FOOTER ═══ */
    .footer {
      position: relative; z-index: 1;
      text-align: center; padding: 3rem 2rem;
      border-top: 1px solid var(--border);
    }
    .footer-links {
      display: flex; gap: 2rem; justify-content: center; margin-bottom: 1rem;
    }
    .footer-links a {
      color: var(--gray-2); text-decoration: none; font-size: 0.82rem;
      font-weight: 500; transition: color 0.2s;
    }
    .footer-links a:hover { color: var(--accent); }
    .footer-credit {
      color: var(--gray-3); font-size: 0.78rem; line-height: 1.6;
    }
    .footer-credit strong { color: var(--gray-2); font-weight: 600; }

    /* ═══ THEME TOGGLE ═══ */
    .theme-toggle {
      position: fixed; top: 1.2rem; right: 1.4rem; z-index: 200;
      width: 48px; height: 26px; border-radius: 13px;
      background: var(--bg-card); border: 1px solid var(--border);
      cursor: pointer; padding: 3px;
      transition: border-color 0.3s, background 0.3s;
      display: flex; align-items: center;
    }
    .theme-toggle:hover { border-color: var(--accent); }
    .toggle-knob {
      width: 20px; height: 20px; border-radius: 50%;
      background: var(--accent);
      transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; line-height: 1;
    }
    [data-theme="dark"] .toggle-knob { transform: translateX(0); }
    [data-theme="light"] .toggle-knob { transform: translateX(22px); }
    [data-theme="dark"] .toggle-knob::after { content: '\\263E'; color: #fff; }
    [data-theme="light"] .toggle-knob::after { content: '\\2600'; color: #fff; }

    /* transitions for cards/sections on theme switch */
    .terminal, .mhp-inner, .feature, .arch-card, .install-options, .install-opt,
    .cta-gh, .cta-docs, .download-auto, .version-tag, .footer {
      transition: background 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease;
    }

    /* ═══ SCROLL REVEAL ═══ */
    .reveal { opacity: 0; transform: translateY(20px); transition: all 0.6s ease; }
    .reveal.visible { opacity: 1; transform: translateY(0); }

    /* ═══ RESPONSIVE ═══ */
    @media (max-width: 768px) {
      .logo { font-size: 3.5rem; }
      .hero-tagline { font-size: 1.1rem; }
      .features { grid-template-columns: 1fr; }
      .steps { grid-template-columns: 1fr; gap: 1.5rem; }
      .cta-row { flex-direction: column; align-items: center; }
      .mascot-hover-panel {
        left: auto; right: calc(100% + 12px);
        transform-origin: right center;
      }
      .mascot-wrapper:hover .mascot-hover-panel {
        transform: translateY(-50%) scale(1);
      }
      .mhp-inner::after {
        left: auto; right: -7px;
        border-right: none;
        border-left: 7px solid var(--border);
      }
      .mhp-inner::before {
        left: auto; right: -6px;
        border-right: none;
        border-left: 6px solid var(--bg-card);
      }
    }
    @media (max-width: 480px) {
      .logo { font-size: 2.8rem; }
      .mascot-hover-panel { display: none; }
    }
  </style>
</head>
<body>
  <div class="bg-noise"></div>
  <div class="bg-glow"></div>

  <!-- Theme toggle -->
  <button class="theme-toggle" id="themeBtn" aria-label="Toggle dark/light mode">
    <div class="toggle-knob"></div>
  </button>

  <!-- Hero -->
  <section class="hero">

    <!-- Mascot -->
    <div class="mascot-wrapper" id="mascot">

      <!-- Code panel — opens to the RIGHT (fixes overflow bug) -->
      <div class="mascot-hover-panel">
        <div class="mhp-inner">
          <div class="mhp-bar">
            <div class="mhp-dot r"></div><div class="mhp-dot y"></div><div class="mhp-dot g"></div>
          </div>
          <div class="mhp-file">hauba/agents/director.py</div>
          <div class="mhp-line"><span class="c-kw">async def</span> <span class="c-fn">deliberate</span>(self):</div>
          <div class="mhp-line">&nbsp;&nbsp;plan = <span class="c-kw">await</span> self.<span class="c-fn">think</span>()</div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-cm"># zero hallucination gate</span></div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-kw">return</span> <span class="c-fn">verify</span>(plan)<span class="mhp-cursor"></span></div>
          <div class="mhp-status">&#x2713; All 42 tests passed &mdash; 0.8s</div>
        </div>
      </div>

      <svg class="mascot-svg" viewBox="0 0 130 158" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bG" x1="30" y1="10" x2="100" y2="148" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#a29bfe"/>
            <stop offset="50%" stop-color="#6C5CE7"/>
            <stop offset="100%" stop-color="#5541d6"/>
          </linearGradient>
          <linearGradient id="blG" x1="45" y1="65" x2="85" y2="120" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(255,255,255,0.18)"/>
            <stop offset="100%" stop-color="rgba(255,255,255,0.02)"/>
          </linearGradient>
          <radialGradient id="aura" cx="65" cy="82" r="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(108,92,231,0.18)"/>
            <stop offset="100%" stop-color="transparent"/>
          </radialGradient>
          <filter id="gF"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <ellipse cx="65" cy="86" rx="56" ry="62" fill="url(#aura)" opacity="0.5"/>
        <g class="mascot-body-group">
          <g class="arm-left">
            <path d="M36 72 Q18 62 15 76 Q12 90 26 86 Q32 84 38 78" fill="url(#bG)" opacity="0.9"/>
            <ellipse cx="15" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/>
          </g>
          <g class="arm-right">
            <path d="M94 72 Q112 62 115 76 Q118 90 104 86 Q98 84 92 78" fill="url(#bG)" opacity="0.9"/>
            <ellipse cx="115" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/>
          </g>
          <g class="belly">
            <ellipse cx="65" cy="87" rx="38" ry="48" fill="url(#bG)"/>
            <ellipse cx="65" cy="92" rx="28" ry="34" fill="url(#blG)"/>
            <ellipse cx="65" cy="104" rx="3" ry="3.5" fill="rgba(0,0,0,0.18)"/>
          </g>
          <ellipse cx="65" cy="41" rx="25" ry="24" fill="url(#bG)"/>
          <ellipse cx="60" cy="34" rx="12" ry="9" fill="rgba(255,255,255,0.07)"/>
          <g>
            <path d="M65 18 Q62 6 68 2" stroke="url(#bG)" stroke-width="2.2" fill="none" stroke-linecap="round">
              <animateTransform attributeName="transform" type="rotate" values="0 65 18;7 65 18;-7 65 18;0 65 18" dur="2.1s" repeatCount="indefinite"/>
            </path>
            <circle cx="68" cy="2" r="3.5" fill="#a29bfe" filter="url(#gF)">
              <animate attributeName="r" values="3.5;5;3.5" dur="1.6s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.75;1;0.75" dur="1.6s" repeatCount="indefinite"/>
            </circle>
          </g>
          <g class="eye-blink">
            <ellipse cx="55" cy="40" rx="8" ry="9" fill="white"/>
            <g class="eye-pupil">
              <circle cx="56.5" cy="41" r="4" fill="var(--mascot-eye)"/>
              <circle cx="57.5" cy="39" r="1.8" fill="white" opacity="0.9"/>
            </g>
          </g>
          <g class="eye-blink-r">
            <ellipse cx="75" cy="40" rx="8" ry="9" fill="white"/>
            <g class="eye-pupil">
              <circle cx="76.5" cy="41" r="4" fill="var(--mascot-eye)"/>
              <circle cx="77.5" cy="39" r="1.8" fill="white" opacity="0.9"/>
            </g>
          </g>
          <ellipse cx="65" cy="53" rx="5.5" ry="2.8" fill="var(--mascot-mouth)">
            <animate attributeName="ry" values="2.8;8;3.5;9;2.8;8.5;2.8" dur="3.2s" repeatCount="indefinite"/>
            <animate attributeName="rx" values="5.5;7;5;7.5;5.5;7;5.5" dur="3.2s" repeatCount="indefinite"/>
          </ellipse>
          <ellipse cx="65" cy="55" rx="3.5" ry="1.5" fill="var(--mascot-mouth-inner)" opacity="0.55">
            <animate attributeName="ry" values="1.5;5.5;2;6;1.5;5.5;1.5" dur="3.2s" repeatCount="indefinite"/>
          </ellipse>
          <ellipse cx="52" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
          <ellipse cx="78" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
        </g>
      </svg>
    </div>

    <h1 class="logo">H<span>AU</span>BA</h1>
    <div class="version-tag" id="versionTag" style="visibility:hidden"></div>

    <p class="hero-tagline">
      <strong>The AI that actually ships code.</strong><br>
      Not a chatbot. A full engineering team in your terminal.
    </p>
    <p class="hero-sub">
      One command deploys a Director, SubAgents, and Workers that plan, build,
      test, and deliver &mdash; with SHA-256 verified outputs. Zero hallucinations.
    </p>

    <!-- Terminal Demo -->
    <div class="terminal reveal">
      <div class="terminal-bar">
        <div class="terminal-dot r"></div>
        <div class="terminal-dot y"></div>
        <div class="terminal-dot g"></div>
        <div class="terminal-title">Terminal</div>
      </div>
      <div class="terminal-body">
        <span class="t-prompt">$</span> <span class="t-cmd">pip install hauba</span><br>
        <span class="t-prompt">$</span> <span class="t-cmd">hauba init</span><br>
        <span class="t-output">Initialized hauba workspace at ./hauba.yaml</span><br>
        <span class="t-prompt">$</span> <span class="t-cmd">hauba run <span style="color:var(--gray-1)">"build a SaaS dashboard with auth"</span></span><br>
        <span class="t-output">Director &rarr; Planning 4 milestones...</span><br>
        <span class="t-output">SubAgent-1 &rarr; Scaffolding project structure</span><br>
        <span class="t-output">Worker-3 &rarr; Implementing Stripe billing</span><br>
        <span class="t-success">&#x2713; All tasks verified. 0 hallucinations.</span><span class="t-cursor"></span>
      </div>
    </div>

    <!-- Auto-detect download -->
    <div class="download-section reveal">
      <button class="download-auto" id="downloadBtn" onclick="copyInstallCmd()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span id="downloadText">Install for your platform</span>
      </button>
      <div class="download-other">
        <a href="#" id="togglePlatforms" onclick="toggleInstallOpts(event)">All platforms</a>
        &nbsp;&middot;&nbsp;
        <a href="https://pypi.org/project/hauba/">PyPI</a>
        &nbsp;&middot;&nbsp;
        <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
      </div>
      <div class="install-options" id="installOpts">
        <div class="install-opt">
          <span class="install-opt-label">pip</span>
          <code class="install-opt-cmd">pip install hauba</code>
          <button class="copy-btn" onclick="copyCmd(this,'pip install hauba')">Copy</button>
        </div>
        <div class="install-opt">
          <span class="install-opt-label">macOS / Linux</span>
          <code class="install-opt-cmd">curl -fsSL https://hauba.tech/install.sh | sh</code>
          <button class="copy-btn" onclick="copyCmd(this,'curl -fsSL https://hauba.tech/install.sh | sh')">Copy</button>
        </div>
        <div class="install-opt">
          <span class="install-opt-label">Windows</span>
          <code class="install-opt-cmd">irm hauba.tech/install.ps1 | iex</code>
          <button class="copy-btn" onclick="copyCmd(this,'irm hauba.tech/install.ps1 | iex')">Copy</button>
        </div>
      </div>
    </div>

    <div class="cta-row reveal">
      <a href="https://github.com/NikeGunn/haubaa" class="cta-gh">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        Star on GitHub
      </a>
      <a href="https://github.com/NikeGunn/haubaa#readme" class="cta-docs">Documentation</a>
    </div>
  </section>

  <!-- Features -->
  <section class="section" id="features">
    <div class="section-label reveal">Capabilities</div>
    <h2 class="section-title reveal">Built different.</h2>
    <p class="section-subtitle reveal">Not another wrapper around an LLM. A real multi-agent operating system.</p>
    <div class="features reveal">
      <div class="feature">
        <div class="feature-icon">&#x2B21;</div>
        <h3>Multi-Agent Hierarchy</h3>
        <p>Director, SubAgents, Workers &mdash; a real org chart that plans, delegates, and executes in parallel.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x2B22;</div>
        <h3>Zero Hallucination</h3>
        <p>TaskLedger with SHA-256 hash-chain and bit-vector. Every output verified on disk before delivery.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25C6;</div>
        <h3>Fully Offline</h3>
        <p>First-class Ollama support. Air-gapped deployments. Your code stays on your machine.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25A0;</div>
        <h3>Skills &amp; Strategies</h3>
        <p>Composable .md skills and .yaml playbooks. Teach agents domain expertise in plain English.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25B2;</div>
        <h3>Think-Then-Act</h3>
        <p>Every agent deliberates before executing. Minimum think times enforced. No reckless commits.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25CB;</div>
        <h3>Zero Dependencies</h3>
        <p>No Docker, Redis, or Postgres required. SQLite for storage. pip install and go.</p>
      </div>
    </div>
  </section>

  <!-- How It Works -->
  <section class="section" id="how">
    <div class="section-label reveal">Workflow</div>
    <h2 class="section-title reveal">Three commands. Ship anything.</h2>
    <p class="section-subtitle reveal">From idea to production-ready code in minutes, not days.</p>
    <div class="steps reveal">
      <div class="step">
        <div class="step-num">1</div>
        <h3>Install</h3>
        <p>pip install hauba. No Docker, no containers, no complex setup. One command.</p>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <h3>Describe</h3>
        <p>Tell Hauba what to build in plain English. The Director plans, decomposes, and delegates.</p>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <h3>Ship</h3>
        <p>Workers execute in parallel. Every output is SHA-256 verified. Zero hallucinations, guaranteed.</p>
      </div>
    </div>
  </section>

  <!-- Architecture -->
  <section class="section" id="architecture">
    <div class="section-label reveal">Under the hood</div>
    <h2 class="section-title reveal">Architecture</h2>
    <p class="section-subtitle reveal">Python-first. Single process. Event-driven. Crash-safe.</p>
    <div class="arch-card reveal">
      <span class="a-cm"># Agent Hierarchy</span><br>
      <span class="a-k">Owner</span> <span class="a-t">(Human)</span><br>
      &nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">Director</span> <span class="a-t">(CEO)</span> <span class="a-cm">&mdash; deliberates, plans, delegates</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x251C;&#x2500;&#x2500;</span> <span class="a-k">SubAgent</span> <span class="a-t">(Team Lead)</span> <span class="a-cm">&mdash; manages milestone</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-v">&#x251C;&#x2500;&#x2500;</span> <span class="a-k">Worker</span> <span class="a-t">(Specialist)</span> <span class="a-cm">&mdash; executes in sandbox</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">CoWorker</span> <span class="a-t">(Helper)</span> <span class="a-cm">&mdash; ephemeral</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">Worker</span> ...<br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">SubAgent</span> ...<br><br>
      <span class="a-cm"># Communication: async events &mdash; full audit trail</span><br>
      <span class="a-cm"># Storage: SQLite &mdash; zero external dependencies</span><br>
      <span class="a-cm"># TaskLedger: every level &mdash; GateCheck before delivery</span>
    </div>
  </section>

  <!-- Footer -->
  <footer class="footer">
    <div class="footer-links">
      <a href="https://github.com/NikeGunn/haubaa">GitHub</a>
      <a href="https://pypi.org/project/hauba/">PyPI</a>
      <a href="https://github.com/NikeGunn/haubaa#readme">Docs</a>
      <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
    </div>
    <p class="footer-credit">
      Built by <strong>Nikhil Bhagat</strong> and community &mdash; MIT License
    </p>
  </footer>

  <script>
    /* ── THEME TOGGLE ── */
    (function() {
      var html = document.documentElement;
      var saved = localStorage.getItem('hauba-theme');
      if (saved === 'light' || saved === 'dark') html.dataset.theme = saved;
      document.getElementById('themeBtn').addEventListener('click', function() {
        var next = html.dataset.theme === 'dark' ? 'light' : 'dark';
        html.dataset.theme = next;
        localStorage.setItem('hauba-theme', next);
      });
    })();

    /* ── OS DETECTION ── */
    function detectOS() {
      const ua = navigator.userAgent || navigator.platform || '';
      if (/Win/i.test(ua)) return 'windows';
      if (/Mac/i.test(ua)) return 'macos';
      if (/Linux/i.test(ua)) return 'linux';
      if (/Android/i.test(ua)) return 'linux';
      if (/iPhone|iPad/i.test(ua)) return 'macos';
      return 'pip';
    }
    const osCommands = {
      windows: { label: 'Install for Windows', cmd: 'irm hauba.tech/install.ps1 | iex' },
      macos:   { label: 'Install for macOS',   cmd: 'curl -fsSL https://hauba.tech/install.sh | sh' },
      linux:   { label: 'Install for Linux',   cmd: 'curl -fsSL https://hauba.tech/install.sh | sh' },
      pip:     { label: 'Install with pip',     cmd: 'pip install hauba' },
    };
    const userOS = detectOS();
    const osInfo = osCommands[userOS] || osCommands.pip;
    document.getElementById('downloadText').textContent = osInfo.label;

    function copyInstallCmd() {
      const btn = document.getElementById('downloadBtn');
      const text = document.getElementById('downloadText');
      navigator.clipboard.writeText(osInfo.cmd).then(() => {
        const orig = text.textContent;
        text.textContent = 'Copied: ' + osInfo.cmd;
        btn.style.background = 'var(--success)';
        setTimeout(function() { text.textContent = orig; btn.style.background = ''; }, 2500);
      });
    }

    /* ── TOGGLE ALL PLATFORMS ── */
    function toggleInstallOpts(e) {
      e.preventDefault();
      document.getElementById('installOpts').classList.toggle('open');
    }

    /* ── COPY ── */
    function copyCmd(btn, text) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!'; btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    }

    /* ── SCROLL REVEAL ── */
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal').forEach(el => obs.observe(el));

    /* ── MASCOT CLICK ── */
    document.getElementById('mascot').addEventListener('click', function() {
      this.style.transform = 'scale(1.1) rotate(5deg)';
      setTimeout(() => this.style.transform = '', 350);
    });

    /* ── DYNAMIC VERSION FROM GITHUB RELEASES ── */
    (function() {
      fetch('/api/version')
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(info) {
          if (!info || !info.version) return;
          var el = document.getElementById('versionTag');
          if (el) { el.textContent = info.version + ' \u2014 ' + info.label; el.style.visibility = ''; }
        })
        .catch(function() { /* silently keep the default text */ });
    })();
  </script>
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
        elif self.path == "/api/version":
            info = get_release_info()
            payload = json.dumps(info, separators=(",", ":"))
            self._send_text(payload, "application/json")
        elif self.path == "/favicon.png":
            if FAVICON_BYTES:
                self._send_bytes(FAVICON_BYTES, "image/png")
            else:
                self.send_error(404)
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

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[hauba.tech] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), HaubaHandler)
    print(f"[hauba.tech] Serving on port {PORT}")
    print(f"[hauba.tech] Routes: / /install.sh /install.ps1 /health /favicon.png")
    server.serve_forever()
