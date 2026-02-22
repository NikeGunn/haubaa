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
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hauba — AI Agent Operating System</title>
  <meta name="description" content="One command. An AI engineering team at your service. Open-source AI agent framework.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    /* ═══════ THEME TOKENS ═══════ */
    [data-theme="dark"] {
      --cyan: #00d4ff; --purple: #7b2fff; --pink: #ff2d87; --green: #00ff88;
      --bg: #050508; --bg-card: #0f0f1a; --bg-card-hover: #141425;
      --border: #1a1a2e; --border-hover: #2a2a4e;
      --text: #f0f0f5; --text-dim: #8888aa; --text-muted: #44445a;
      --grid-color: rgba(123,47,255,0.035);
      --glow-top: rgba(123,47,255,0.09);
      --glow-bot: rgba(255,45,135,0.05);
      --code-bg: #0a0a15;
    }
    [data-theme="light"] {
      --cyan: #0099cc; --purple: #6020cc; --pink: #cc1a6e; --green: #00aa55;
      --bg: #f4f4f8; --bg-card: #ffffff; --bg-card-hover: #f0f0fa;
      --border: #ddddf0; --border-hover: #bbbbdd;
      --text: #111118; --text-dim: #555570; --text-muted: #9999b0;
      --grid-color: rgba(100,80,200,0.04);
      --glow-top: rgba(100,80,200,0.06);
      --glow-bot: rgba(200,40,100,0.03);
      --code-bg: #eeeef8;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--text);
      min-height: 100vh; overflow-x: hidden;
      transition: background 0.35s, color 0.35s;
    }

    /* ═══════ BG EFFECTS ═══════ */
    .bg-grid {
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background-image:
        linear-gradient(var(--grid-color) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
      background-size: 60px 60px;
    }
    .bg-glow {
      position: fixed; top: -220px; left: 50%; transform: translateX(-50%);
      width: 900px; height: 700px; z-index: 0; pointer-events: none;
      background: radial-gradient(ellipse, var(--glow-top) 0%, transparent 70%);
    }
    .bg-glow-bot {
      position: fixed; bottom: -300px; left: 50%; transform: translateX(-50%);
      width: 1000px; height: 500px; z-index: 0; pointer-events: none;
      background: radial-gradient(ellipse, var(--glow-bot) 0%, transparent 65%);
    }

    /* ═══════ THEME TOGGLE (top-right corner) ═══════ */
    .theme-toggle {
      position: fixed; top: 1.1rem; right: 1.4rem; z-index: 200;
      width: 44px; height: 24px; border-radius: 12px;
      background: var(--bg-card); border: 1px solid var(--border);
      cursor: pointer; transition: all 0.3s;
      display: flex; align-items: center; padding: 2px;
    }
    .theme-toggle:hover { border-color: var(--purple); }
    .toggle-knob {
      width: 18px; height: 18px; border-radius: 50%;
      background: linear-gradient(135deg, var(--purple), var(--cyan));
      transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
      display: flex; align-items: center; justify-content: center;
      font-size: 0.6rem;
    }
    [data-theme="light"] .toggle-knob { transform: translateX(20px); }
    .toggle-knob::after {
      content: '🌙';
      font-size: 10px;
    }
    [data-theme="light"] .toggle-knob::after { content: '☀️'; }

    /* ═══════ HERO ═══════ */
    .hero {
      position: relative; z-index: 1;
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 5rem 2rem 4rem;
      text-align: center;
    }

    /* ═══════ MASCOT — SMALLER + HOVER OVERHAUL ═══════ */
    .mascot-wrapper {
      margin-bottom: 1.8rem;
      position: relative; cursor: pointer;
      width: 130px; height: 158px;
    }
    .mascot-svg {
      width: 130px; height: 158px;
      filter: drop-shadow(0 0 28px rgba(0,212,255,0.25));
      transition: filter 0.3s;
    }
    .mascot-wrapper:hover .mascot-svg {
      filter: drop-shadow(0 0 48px rgba(123,47,255,0.55));
    }

    /* ── HOVER BUBBLE (code review panel) ── */
    .mascot-hover-panel {
      position: absolute; bottom: 168px; left: 50%; transform: translateX(-50%) scale(0.85);
      width: 230px; opacity: 0; pointer-events: none;
      transition: all 0.35s cubic-bezier(.34,1.56,.64,1);
      transform-origin: bottom center;
    }
    .mascot-wrapper:hover .mascot-hover-panel {
      opacity: 1; transform: translateX(-50%) scale(1);
    }
    .mhp-inner {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 10px; padding: 0.7rem 0.9rem;
      font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
      text-align: left; position: relative;
      box-shadow: 0 8px 40px rgba(123,47,255,0.25);
    }
    .mhp-inner::after {
      content: ''; position: absolute; bottom: -7px; left: 50%; transform: translateX(-50%);
      width: 0; height: 0;
      border-left: 7px solid transparent; border-right: 7px solid transparent;
      border-top: 7px solid var(--border);
    }
    .mhp-inner::before {
      content: ''; position: absolute; bottom: -6px; left: 50%; transform: translateX(-50%);
      width: 0; height: 0;
      border-left: 6px solid transparent; border-right: 6px solid transparent;
      border-top: 6px solid var(--bg-card); z-index: 1;
    }
    .mhp-bar {
      display: flex; gap: 4px; margin-bottom: 6px;
    }
    .mhp-dot { width: 7px; height: 7px; border-radius: 50%; }
    .mhp-dot.r { background: #ff5f57; }
    .mhp-dot.y { background: #ffbd2e; }
    .mhp-dot.g { background: #28c840; }
    .mhp-file { font-size: 0.58rem; color: var(--text-muted); margin-bottom: 5px; }
    .mhp-line { margin: 1px 0; color: var(--text-dim); }
    .mhp-line .c-kw { color: var(--purple); }
    .mhp-line .c-fn { color: var(--cyan); }
    .mhp-line .c-str { color: var(--green); }
    .mhp-line .c-cm { color: var(--text-muted); }
    .mhp-status {
      margin-top: 6px; padding-top: 5px; border-top: 1px solid var(--border);
      font-size: 0.58rem; color: var(--green);
      display: flex; align-items: center; gap: 4px;
    }
    .mhp-status::before { content: '✓'; font-weight: 700; }
    /* typing cursor in panel */
    .mhp-cursor {
      display: inline-block; width: 5px; height: 0.8em;
      background: var(--cyan); vertical-align: text-bottom;
      animation: cursorBlink 0.7s step-end infinite;
    }
    @keyframes cursorBlink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

    /* ── MASCOT ANIMATIONS ── */
    @keyframes bodyBounce {
      0%,100% { transform: translateY(0); }
      50% { transform: translateY(-5px); }
    }
    .mascot-body-group { animation: bodyBounce 2.2s ease-in-out infinite; }

    @keyframes eyeLook {
      0%,18%   { transform: translate(0,0); }
      22%,34%  { transform: translate(3px,-1px); }
      38%,52%  { transform: translate(-3px,1px); }
      56%,68%  { transform: translate(2px,2px); }
      72%,84%  { transform: translate(-2px,-1px); }
      88%,100% { transform: translate(0,0); }
    }
    .eye-pupil { animation: eyeLook 4.5s ease-in-out infinite; }

    @keyframes blink {
      0%,40%,42%,100% { transform: scaleY(1); }
      41% { transform: scaleY(0.05); }
    }
    .eye-blink   { animation: blink 4s infinite; transform-origin: center; }
    .eye-blink-r { animation: blink 4s infinite 0.6s; transform-origin: center; }

    @keyframes bellyJiggle {
      0%,100% { transform: scaleX(1) scaleY(1); }
      30% { transform: scaleX(1.015) scaleY(0.985); }
      65% { transform: scaleX(0.985) scaleY(1.015); }
    }
    .belly { animation: bellyJiggle 2.1s ease-in-out infinite; transform-origin: center 60%; }

    @keyframes armWaveL {
      0%,100% { transform: rotate(0deg); }
      30% { transform: rotate(-18deg); }
      65% { transform: rotate(6deg); }
    }
    @keyframes armWaveR {
      0%,100% { transform: rotate(0deg); }
      30% { transform: rotate(18deg); }
      65% { transform: rotate(-6deg); }
    }
    .arm-left  { animation: armWaveL 2.6s ease-in-out infinite; transform-origin: 36px 70px; }
    .arm-right { animation: armWaveR 2.6s ease-in-out infinite 0.4s; transform-origin: 95px 70px; }

    /* ═══════ LOGO ═══════ */
    .logo {
      font-family: 'JetBrains Mono', monospace;
      font-size: 4rem; font-weight: 900; letter-spacing: 0.15em;
      background: linear-gradient(135deg, var(--cyan) 0%, var(--purple) 50%, var(--pink) 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text; margin-bottom: 0.3rem; position: relative;
    }
    .logo::after {
      content: 'HAUBA'; position: absolute; left: 0; top: 0;
      background: linear-gradient(135deg, var(--cyan), var(--purple), var(--pink));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
      filter: blur(28px); opacity: 0.35; z-index: -1;
    }
    .version-tag {
      display: inline-block; background: rgba(123,47,255,0.12);
      border: 1px solid rgba(123,47,255,0.28); border-radius: 20px;
      padding: 0.18rem 0.75rem; font-size: 0.68rem; font-weight: 600;
      color: var(--purple); margin-bottom: 1.4rem; letter-spacing: 0.05em;
    }

    /* ═══════ TYPEWRITER TAGLINE ═══════ */
    .tagline-wrap { margin-bottom: 0.8rem; min-height: 2.2rem; }
    .tagline {
      font-size: 1.25rem; color: var(--text-dim);
      max-width: 560px; line-height: 1.6; font-weight: 400;
    }
    .tagline .typed-static { color: var(--text); font-weight: 600; }
    .tagline .typed-part {
      color: var(--cyan); font-weight: 700;
      border-right: 2px solid var(--cyan);
      white-space: nowrap; overflow: hidden;
      animation: cursorBlink 0.75s step-end infinite;
    }

    /* ═══════ THRILLING POWER LINES ═══════ */
    .power-lines {
      display: flex; flex-direction: column; gap: 0.35rem;
      margin-bottom: 2.5rem; align-items: center;
    }
    .power-line {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
      opacity: 0; transform: translateX(-20px);
      transition: opacity 0.5s ease, transform 0.5s ease;
      display: flex; align-items: center; gap: 0.5rem;
    }
    .power-line.visible { opacity: 1; transform: translateX(0); }
    .power-line .pl-icon { font-size: 0.85rem; }
    .power-line.c1 .pl-text { color: var(--cyan); }
    .power-line.c2 .pl-text { color: var(--purple); }
    .power-line.c3 .pl-text { color: var(--pink); }
    .power-line.c4 .pl-text { color: var(--green); }
    .power-line.c5 .pl-text {
      background: linear-gradient(90deg, var(--cyan), var(--purple), var(--pink));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    /* shimmer on hover */
    .power-line:hover .pl-text {
      animation: shimmer 0.6s ease;
    }
    @keyframes shimmer {
      0%  { filter: brightness(1); }
      50% { filter: brightness(1.8) drop-shadow(0 0 6px currentColor); }
      100%{ filter: brightness(1); }
    }

    /* ═══════ BADGES ═══════ */
    .badges { display: flex; gap: 0.45rem; flex-wrap: wrap; justify-content: center; margin-bottom: 2.5rem; }
    .badge {
      display: flex; align-items: center; gap: 0.35rem;
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 20px;
      padding: 0.3rem 0.8rem; font-size: 0.7rem; color: var(--text-dim); font-weight: 500;
      transition: all 0.2s;
    }
    .badge:hover { border-color: var(--border-hover); color: var(--text); }
    .bdot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; }
    .bdot.g { background: var(--green); }
    .bdot.c { background: var(--cyan); }
    .bdot.p { background: var(--purple); }
    .bdot.k { background: var(--pink); }

    /* ═══════ INSTALL TABS ═══════ */
    .install-section { width: 100%; max-width: 560px; margin-bottom: 2.8rem; }
    .install-tabs { display: flex; border-bottom: 1px solid var(--border); }
    .install-tab {
      padding: 0.55rem 1.1rem; font-size: 0.76rem; color: var(--text-muted);
      cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s;
      font-weight: 500; background: none; border-top: none; border-left: none; border-right: none;
      font-family: inherit;
    }
    .install-tab:hover { color: var(--text-dim); }
    .install-tab.active { color: var(--cyan); border-bottom-color: var(--cyan); }
    .install-panel {
      display: none; background: var(--code-bg); border: 1px solid var(--border);
      border-top: none; border-radius: 0 0 10px 10px; padding: 1rem 1.4rem; position: relative;
    }
    .install-panel.active { display: block; }
    .install-panel code { font-family: 'JetBrains Mono', monospace; font-size: 0.84rem; color: var(--cyan); display: block; word-break: break-all; }
    .copy-btn {
      position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
      background: rgba(123,47,255,0.12); border: 1px solid rgba(123,47,255,0.25);
      color: var(--purple); border-radius: 6px; padding: 0.3rem 0.65rem;
      font-size: 0.68rem; cursor: pointer; font-family: inherit; font-weight: 600; transition: all 0.2s;
    }
    .copy-btn:hover { background: rgba(123,47,255,0.22); color: var(--text); }
    .copy-btn.copied { background: rgba(0,255,136,0.12) !important; border-color: var(--green) !important; color: var(--green) !important; }

    /* ═══════ CTA ═══════ */
    .cta-group { display: flex; gap: 0.9rem; justify-content: center; margin-bottom: 4rem; }
    .cta-primary {
      display: inline-flex; align-items: center; gap: 0.45rem;
      background: linear-gradient(135deg, var(--purple), var(--pink));
      color: white; padding: 0.72rem 1.7rem; border-radius: 8px;
      text-decoration: none; font-weight: 600; font-size: 0.88rem;
      transition: all 0.2s; box-shadow: 0 4px 20px rgba(123,47,255,0.28);
    }
    .cta-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(123,47,255,0.42); }
    .cta-secondary {
      display: inline-flex; align-items: center; gap: 0.45rem;
      background: transparent; border: 1px solid var(--border); color: var(--text-dim);
      padding: 0.72rem 1.7rem; border-radius: 8px; text-decoration: none;
      font-weight: 500; font-size: 0.88rem; transition: all 0.2s;
    }
    .cta-secondary:hover { border-color: var(--border-hover); color: var(--text); }

    /* ═══════ SECTIONS ═══════ */
    .section { position: relative; z-index: 1; padding: 4rem 2rem; }
    .section-title { text-align: center; font-size: 1.9rem; font-weight: 800; margin-bottom: 0.45rem; }
    .section-subtitle { text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2.8rem; }

    /* ═══════ FEATURES ═══════ */
    .features { display: grid; grid-template-columns: repeat(3,1fr); gap: 1.1rem; max-width: 880px; margin: 0 auto; }
    .feature {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 1.4rem; transition: all 0.3s; position: relative; overflow: hidden;
    }
    .feature::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, var(--cyan), transparent);
      opacity: 0; transition: opacity 0.3s;
    }
    .feature:hover { border-color: var(--border-hover); background: var(--bg-card-hover); transform: translateY(-3px); }
    .feature:hover::before { opacity: 1; }
    .feature-icon { width: 38px; height: 38px; border-radius: 9px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; margin-bottom: 0.9rem; }
    .fi-c { background: rgba(0,212,255,0.1); color: var(--cyan); }
    .fi-p { background: rgba(123,47,255,0.1); color: var(--purple); }
    .fi-k { background: rgba(255,45,135,0.1); color: var(--pink); }
    .fi-g { background: rgba(0,255,136,0.1); color: var(--green); }
    .feature h3 { font-size: 0.9rem; font-weight: 700; margin-bottom: 0.35rem; }
    .feature p { font-size: 0.8rem; color: var(--text-dim); line-height: 1.55; }

    /* ═══════ ARCH CARD ═══════ */
    .arch-card {
      max-width: 680px; margin: 0 auto;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 12px; padding: 1.8rem; font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem; line-height: 1.75; color: var(--text-dim);
    }
    .a-cm { color: var(--text-muted); }
    .a-k  { color: var(--cyan); }
    .a-v  { color: var(--pink); }
    .a-t  { color: var(--purple); }

    /* ═══════ FOOTER ═══════ */
    .footer { position: relative; z-index: 1; text-align: center; padding: 2.5rem 2rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.78rem; }
    .footer-links { display: flex; gap: 1.8rem; justify-content: center; margin-bottom: 0.8rem; }
    .footer-links a { color: var(--text-dim); text-decoration: none; font-size: 0.8rem; transition: color 0.2s; }
    .footer-links a:hover { color: var(--cyan); }
    .footer-heart { color: var(--pink); }

    /* ═══════ RESPONSIVE ═══════ */
    @media (max-width: 768px) {
      .features { grid-template-columns: 1fr; }
      .logo { font-size: 2.8rem; }
      .tagline { font-size: 1.05rem; }
      .cta-group { flex-direction: column; align-items: center; }
      .mascot-hover-panel { width: 190px; font-size: 0.6rem; }
    }
    @media (max-width: 480px) {
      .logo { font-size: 2.2rem; }
      .install-tabs { flex-wrap: wrap; }
    }

    /* ═══════ SCROLL REVEAL ═══════ */
    .reveal { opacity: 0; transform: translateY(18px); transition: all 0.6s ease; }
    .reveal.visible { opacity: 1; transform: translateY(0); }
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  <div class="bg-glow"></div>
  <div class="bg-glow-bot"></div>

  <!-- Dark/Light toggle (top-right) -->
  <button class="theme-toggle" id="themeBtn" aria-label="Toggle theme" title="Toggle dark/light mode">
    <div class="toggle-knob"></div>
  </button>

  <!-- Hero -->
  <section class="hero">

    <!-- ── MASCOT ── -->
    <div class="mascot-wrapper" id="mascot">

      <!-- Engineer code-review hover bubble -->
      <div class="mascot-hover-panel">
        <div class="mhp-inner">
          <div class="mhp-bar">
            <div class="mhp-dot r"></div><div class="mhp-dot y"></div><div class="mhp-dot g"></div>
          </div>
          <div class="mhp-file">hauba/agents/director.py</div>
          <div class="mhp-line"><span class="c-kw">async def</span> <span class="c-fn">deliberate</span>(self):</div>
          <div class="mhp-line">&nbsp;&nbsp;plan = <span class="c-kw">await</span> self.<span class="c-fn">think</span>()</div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-cm"># zero hallucination ✓</span></div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-kw">return</span> <span class="c-fn">verify</span>(plan)<span class="mhp-cursor"></span></div>
          <div class="mhp-status">All 42 tests passed in 0.8s</div>
        </div>
      </div>

      <svg class="mascot-svg" viewBox="0 0 130 158" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bG" x1="30" y1="10" x2="100" y2="148" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#00d4ff"/>
            <stop offset="48%" stop-color="#7b2fff"/>
            <stop offset="100%" stop-color="#ff2d87"/>
          </linearGradient>
          <linearGradient id="blG" x1="45" y1="65" x2="85" y2="120" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(255,255,255,0.18)"/>
            <stop offset="100%" stop-color="rgba(255,255,255,0.02)"/>
          </linearGradient>
          <radialGradient id="aura" cx="65" cy="82" r="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(123,47,255,0.22)"/>
            <stop offset="100%" stop-color="transparent"/>
          </radialGradient>
          <filter id="gF"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <!-- aura -->
        <ellipse cx="65" cy="86" rx="56" ry="62" fill="url(#aura)" opacity="0.6"/>
        <g class="mascot-body-group">
          <!-- arms -->
          <g class="arm-left">
            <path d="M36 72 Q18 62 15 76 Q12 90 26 86 Q32 84 38 78" fill="url(#bG)" opacity="0.9"/>
            <ellipse cx="15" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/>
          </g>
          <g class="arm-right">
            <path d="M94 72 Q112 62 115 76 Q118 90 104 86 Q98 84 92 78" fill="url(#bG)" opacity="0.9"/>
            <ellipse cx="115" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/>
          </g>
          <!-- big belly body -->
          <g class="belly">
            <ellipse cx="65" cy="87" rx="38" ry="48" fill="url(#bG)"/>
            <ellipse cx="65" cy="92" rx="28" ry="34" fill="url(#blG)"/>
            <ellipse cx="65" cy="104" rx="3" ry="3.5" fill="rgba(0,0,0,0.18)"/>
          </g>
          <!-- head -->
          <ellipse cx="65" cy="41" rx="25" ry="24" fill="url(#bG)"/>
          <ellipse cx="60" cy="34" rx="12" ry="9" fill="rgba(255,255,255,0.07)"/>
          <!-- antenna -->
          <g>
            <path d="M65 18 Q62 6 68 2" stroke="url(#bG)" stroke-width="2.2" fill="none" stroke-linecap="round">
              <animateTransform attributeName="transform" type="rotate" values="0 65 18;7 65 18;-7 65 18;0 65 18" dur="2.1s" repeatCount="indefinite"/>
            </path>
            <circle cx="68" cy="2" r="3.5" fill="#00d4ff" filter="url(#gF)">
              <animate attributeName="r" values="3.5;5;3.5" dur="1.6s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.75;1;0.75" dur="1.6s" repeatCount="indefinite"/>
            </circle>
          </g>
          <!-- eyes -->
          <g class="eye-blink">
            <ellipse cx="55" cy="40" rx="8" ry="9" fill="white"/>
            <g class="eye-pupil">
              <circle cx="56.5" cy="41" r="4" fill="#1a1a2e"/>
              <circle cx="57.5" cy="39" r="1.8" fill="white" opacity="0.9"/>
            </g>
          </g>
          <g class="eye-blink-r">
            <ellipse cx="75" cy="40" rx="8" ry="9" fill="white"/>
            <g class="eye-pupil">
              <circle cx="76.5" cy="41" r="4" fill="#1a1a2e"/>
              <circle cx="77.5" cy="39" r="1.8" fill="white" opacity="0.9"/>
            </g>
          </g>
          <!-- mouth WOW -->
          <ellipse cx="65" cy="53" rx="5.5" ry="2.8" fill="#1a0a2e">
            <animate attributeName="ry" values="2.8;8;3.5;9;2.8;8.5;2.8" dur="3.2s" repeatCount="indefinite"/>
            <animate attributeName="rx" values="5.5;7;5;7.5;5.5;7;5.5" dur="3.2s" repeatCount="indefinite"/>
          </ellipse>
          <ellipse cx="65" cy="55" rx="3.5" ry="1.5" fill="#0a0020" opacity="0.55">
            <animate attributeName="ry" values="1.5;5.5;2;6;1.5;5.5;1.5" dur="3.2s" repeatCount="indefinite"/>
          </ellipse>
          <!-- feet -->
          <ellipse cx="52" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
          <ellipse cx="78" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
          <!-- sparkles -->
          <circle cx="28" cy="32" r="1.5" fill="#00d4ff" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2.1s" begin="0s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="32;10" dur="2.1s" begin="0s" repeatCount="indefinite"/>
          </circle>
          <circle cx="102" cy="28" r="1.2" fill="#ff2d87" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2.6s" begin="0.6s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="28;8" dur="2.6s" begin="0.6s" repeatCount="indefinite"/>
          </circle>
          <circle cx="38" cy="22" r="1.2" fill="#7b2fff" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="1.9s" begin="1.1s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="22;5" dur="1.9s" begin="1.1s" repeatCount="indefinite"/>
          </circle>
          <circle cx="92" cy="25" r="1.4" fill="#00ff88" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2.3s" begin="0.3s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="25;6" dur="2.3s" begin="0.3s" repeatCount="indefinite"/>
          </circle>
        </g>
      </svg>
    </div><!-- /mascot-wrapper -->

    <h1 class="logo">HAUBA</h1>
    <div class="version-tag">v0.1.0 &mdash; Public Beta</div>

    <!-- Typewriter tagline -->
    <div class="tagline-wrap">
      <p class="tagline">
        One command. <span class="typed-static">An </span><span class="typed-part" id="typed"></span>
      </p>
    </div>

    <!-- Thrilling power lines -->
    <div class="power-lines" id="powerLines">
      <div class="power-line c1"><span class="pl-icon">&#x26A1;</span><span class="pl-text">Ships production code while you sleep.</span></div>
      <div class="power-line c2"><span class="pl-icon">&#x1F9E0;</span><span class="pl-text">Every output SHA-256 verified. Zero hallucinations.</span></div>
      <div class="power-line c3"><span class="pl-icon">&#x1F680;</span><span class="pl-text">Director &rarr; SubAgent &rarr; Worker. A real engineering org.</span></div>
      <div class="power-line c4"><span class="pl-icon">&#x1F510;</span><span class="pl-text">Runs fully offline. Your code never leaves your machine.</span></div>
      <div class="power-line c5"><span class="pl-icon">&#x2605;</span><span class="pl-text">pip install hauba &mdash; that's literally it.</span></div>
    </div>

    <div class="badges">
      <span class="badge"><span class="bdot g"></span> Python 3.11+</span>
      <span class="badge"><span class="bdot c"></span> Open Source</span>
      <span class="badge"><span class="bdot p"></span> MIT License</span>
      <span class="badge"><span class="bdot k"></span> Offline Capable</span>
    </div>

    <!-- Install tabs -->
    <div class="install-section">
      <div class="install-tabs">
        <button class="install-tab active" onclick="switchTab(0)">pip</button>
        <button class="install-tab" onclick="switchTab(1)">macOS / Linux</button>
        <button class="install-tab" onclick="switchTab(2)">Windows</button>
      </div>
      <div class="install-panel active" id="tab-0">
        <code>pip install hauba</code>
        <button class="copy-btn" onclick="copyCmd(this,'pip install hauba')">Copy</button>
      </div>
      <div class="install-panel" id="tab-1">
        <code>curl -fsSL https://hauba.tech/install.sh | sh</code>
        <button class="copy-btn" onclick="copyCmd(this,'curl -fsSL https://hauba.tech/install.sh | sh')">Copy</button>
      </div>
      <div class="install-panel" id="tab-2">
        <code>irm hauba.tech/install.ps1 | iex</code>
        <button class="copy-btn" onclick="copyCmd(this,'irm hauba.tech/install.ps1 | iex')">Copy</button>
      </div>
    </div>

    <div class="cta-group">
      <a href="https://github.com/NikeGunn/haubaa" class="cta-primary">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        Star on GitHub
      </a>
      <a href="https://github.com/NikeGunn/haubaa#readme" class="cta-secondary">Read the Docs</a>
    </div>
  </section>

  <!-- Features -->
  <section class="section" id="features">
    <h2 class="section-title reveal">Why Hauba?</h2>
    <p class="section-subtitle reveal">Not another chatbot. A full AI engineering company in your terminal.</p>
    <div class="features">
      <div class="feature reveal">
        <div class="feature-icon fi-c">&#x26A1;</div>
        <h3>Multi-Agent Teams</h3>
        <p>Director, SubAgents, Workers &mdash; a real hierarchy that plans, delegates, and executes in parallel.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon fi-p">&#x1F510;</div>
        <h3>Zero Hallucination</h3>
        <p>TaskLedger with SHA-256 hash-chain + bit-vector. Every output verified on disk. No fakes.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon fi-g">&#x1F4BB;</div>
        <h3>Works Offline</h3>
        <p>Full Ollama local model support. Air-gapped deployments. Your code never leaves your machine.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon fi-k">&#x1F9E9;</div>
        <h3>Skills &amp; Strategies</h3>
        <p>Composable .md skills and .yaml cognitive playbooks teach agents domain expertise.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon fi-c">&#x1F9E0;</div>
        <h3>Think-Then-Act</h3>
        <p>Every agent deliberates before executing. Minimum think times enforced. No reckless commits.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon fi-p">&#x2699;</div>
        <h3>Zero Dependencies</h3>
        <p>No Docker, Redis, or Postgres. SQLite for everything. pip install hauba and go.</p>
      </div>
    </div>
  </section>

  <!-- Architecture -->
  <section class="section" id="architecture">
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
      <a href="https://github.com/NikeGunn/haubaa#readme">Documentation</a>
      <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
    </div>
    <p>Built with <span class="footer-heart">&hearts;</span> by the Hauba community &mdash; MIT License.</p>
  </footer>

  <script>
    /* ── THEME TOGGLE ── */
    const html = document.documentElement;
    document.getElementById('themeBtn').addEventListener('click', () => {
      html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('hauba-theme', html.dataset.theme);
    });
    const saved = localStorage.getItem('hauba-theme');
    if (saved) html.dataset.theme = saved;

    /* ── TABS ── */
    function switchTab(idx) {
      document.querySelectorAll('.install-tab').forEach((t,i) => t.classList.toggle('active', i===idx));
      document.querySelectorAll('.install-panel').forEach((p,i) => p.classList.toggle('active', i===idx));
    }

    /* ── COPY ── */
    function copyCmd(btn, text) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!'; btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    }

    /* ── TYPEWRITER ── */
    const phrases = [
      'AI engineering team at your service.',
      'Director Agent planning your sprint.',
      'Workers shipping code in parallel.',
      'Zero-hallucination delivery system.',
      'Senior engineer that never sleeps.',
    ];
    let pi = 0, ci = 0, deleting = false;
    const el = document.getElementById('typed');
    function typewriter() {
      const phrase = phrases[pi];
      if (!deleting) {
        el.textContent = phrase.slice(0, ++ci);
        if (ci === phrase.length) { deleting = true; setTimeout(typewriter, 2200); return; }
      } else {
        el.textContent = phrase.slice(0, --ci);
        if (ci === 0) { deleting = false; pi = (pi + 1) % phrases.length; setTimeout(typewriter, 400); return; }
      }
      setTimeout(typewriter, deleting ? 38 : 62);
    }
    setTimeout(typewriter, 800);

    /* ── POWER LINES cascade reveal ── */
    const lines = document.querySelectorAll('.power-line');
    lines.forEach((l, i) => setTimeout(() => l.classList.add('visible'), 600 + i * 160));

    /* ── SCROLL REVEAL ── */
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal').forEach(el => obs.observe(el));

    /* ── MASCOT CLICK ── */
    document.getElementById('mascot').addEventListener('click', function() {
      this.style.transform = 'scale(1.12) rotate(6deg)';
      setTimeout(() => this.style.transform = '', 350);
    });
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
