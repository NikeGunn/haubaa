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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --cyan: #00d4ff;
      --purple: #7b2fff;
      --pink: #ff2d87;
      --green: #00ff88;
      --bg-primary: #050508;
      --bg-secondary: #0c0c14;
      --bg-card: #0f0f1a;
      --bg-card-hover: #141425;
      --border: #1a1a2e;
      --border-hover: #2a2a4e;
      --text-primary: #f0f0f5;
      --text-secondary: #8888aa;
      --text-muted: #555577;
      --glow-cyan: 0 0 30px rgba(0, 212, 255, 0.15);
      --glow-purple: 0 0 30px rgba(123, 47, 255, 0.15);
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* ═══════ BACKGROUND EFFECTS ═══════ */
    .bg-grid {
      position: fixed; inset: 0; z-index: 0;
      background-image:
        linear-gradient(rgba(123, 47, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(123, 47, 255, 0.03) 1px, transparent 1px);
      background-size: 60px 60px;
    }
    .bg-glow {
      position: fixed; top: -200px; left: 50%; transform: translateX(-50%);
      width: 800px; height: 600px; z-index: 0;
      background: radial-gradient(ellipse, rgba(123, 47, 255, 0.08) 0%, rgba(0, 212, 255, 0.04) 40%, transparent 70%);
      pointer-events: none;
    }
    .bg-glow-bottom {
      position: fixed; bottom: -300px; left: 50%; transform: translateX(-50%);
      width: 1000px; height: 500px; z-index: 0;
      background: radial-gradient(ellipse, rgba(255, 45, 135, 0.05) 0%, transparent 60%);
      pointer-events: none;
    }

    /* ═══════ NAVIGATION ═══════ */
    .nav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      background: rgba(5, 5, 8, 0.8);
      border-bottom: 1px solid var(--border);
      padding: 0.8rem 2rem;
      display: flex; align-items: center; justify-content: space-between;
    }
    .nav-brand {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem; font-weight: 700;
      background: linear-gradient(135deg, var(--cyan), var(--purple));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .nav-links { display: flex; gap: 1.5rem; align-items: center; }
    .nav-links a {
      color: var(--text-secondary); text-decoration: none; font-size: 0.85rem;
      font-weight: 500; transition: color 0.2s;
    }
    .nav-links a:hover { color: var(--cyan); }
    .nav-cta {
      background: linear-gradient(135deg, var(--purple), var(--pink)) !important;
      color: white !important; padding: 0.4rem 1rem; border-radius: 6px;
      font-weight: 600 !important; font-size: 0.8rem !important;
      transition: opacity 0.2s !important;
    }
    .nav-cta:hover { opacity: 0.9; }

    /* ═══════ HERO SECTION ═══════ */
    .hero {
      position: relative; z-index: 1;
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 6rem 2rem 4rem;
      text-align: center;
    }

    /* ═══════ MASCOT ═══════ */
    .mascot-wrapper {
      margin-bottom: 2rem;
      position: relative;
      cursor: pointer;
      transition: transform 0.3s;
    }
    .mascot-wrapper:hover { transform: scale(1.05); }
    .mascot-wrapper:hover .wow-text { opacity: 1; transform: translateX(-50%) scale(1); }

    .mascot-svg { width: 200px; height: 240px; filter: drop-shadow(0 0 40px rgba(0, 212, 255, 0.3)); }

    /* Mascot body bounce */
    @keyframes bodyBounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-6px); }
    }
    .mascot-body-group { animation: bodyBounce 2s ease-in-out infinite; }

    /* Eye looking around */
    @keyframes eyeLook {
      0%, 20% { transform: translate(0, 0); }
      25%, 35% { transform: translate(4px, -2px); }
      40%, 55% { transform: translate(-4px, 1px); }
      60%, 70% { transform: translate(2px, 3px); }
      75%, 85% { transform: translate(-3px, -1px); }
      90%, 100% { transform: translate(0, 0); }
    }
    .eye-pupil { animation: eyeLook 4s ease-in-out infinite; }

    /* Blink */
    @keyframes blink {
      0%, 42%, 44%, 100% { transform: scaleY(1); }
      43% { transform: scaleY(0.05); }
    }
    .eye-blink { animation: blink 4s ease-in-out infinite; transform-origin: center; }
    .eye-blink-r { animation: blink 4s ease-in-out infinite 0.5s; transform-origin: center; }

    /* Mouth open/close (saying WOW) */
    @keyframes mouthWow {
      0%, 15% { ry: 4; rx: 8; }
      20%, 30% { ry: 12; rx: 10; }
      35%, 45% { ry: 5; rx: 7; }
      50%, 60% { ry: 14; rx: 11; }
      65%, 75% { ry: 4; rx: 8; }
      80%, 90% { ry: 13; rx: 10; }
      95%, 100% { ry: 4; rx: 8; }
    }
    .mouth-wow {
      animation: mouthWow 3s ease-in-out infinite;
    }

    /* Belly jiggle */
    @keyframes bellyJiggle {
      0%, 100% { transform: scaleX(1) scaleY(1); }
      25% { transform: scaleX(1.02) scaleY(0.98); }
      50% { transform: scaleX(0.98) scaleY(1.02); }
      75% { transform: scaleX(1.01) scaleY(0.99); }
    }
    .belly { animation: bellyJiggle 2s ease-in-out infinite; transform-origin: center 60%; }

    /* Arms wave */
    @keyframes armWaveL {
      0%, 100% { transform: rotate(0deg); }
      25% { transform: rotate(-15deg); }
      50% { transform: rotate(5deg); }
      75% { transform: rotate(-10deg); }
    }
    @keyframes armWaveR {
      0%, 100% { transform: rotate(0deg); }
      25% { transform: rotate(15deg); }
      50% { transform: rotate(-5deg); }
      75% { transform: rotate(10deg); }
    }
    .arm-left { animation: armWaveL 2.5s ease-in-out infinite; transform-origin: 55px 105px; }
    .arm-right { animation: armWaveR 2.5s ease-in-out infinite 0.3s; transform-origin: 145px 105px; }

    /* Floating particles */
    @keyframes particleFloat {
      0% { opacity: 0; transform: translateY(0) scale(0); }
      20% { opacity: 1; transform: translateY(-10px) scale(1); }
      100% { opacity: 0; transform: translateY(-60px) scale(0.3); }
    }

    /* WOW text */
    .wow-text {
      position: absolute; top: -15px; left: 50%; transform: translateX(-50%) scale(0.8);
      font-family: 'Inter', sans-serif; font-size: 1.4rem; font-weight: 900;
      background: linear-gradient(135deg, var(--cyan), var(--purple), var(--pink));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
      opacity: 0; transition: all 0.3s ease; pointer-events: none;
      letter-spacing: 0.15em;
    }
    @keyframes wowPulse {
      0%, 100% { opacity: 0.7; transform: translateX(-50%) scale(0.95); }
      50% { opacity: 1; transform: translateX(-50%) scale(1.05); }
    }
    .mascot-wrapper:hover .wow-text { animation: wowPulse 0.6s ease-in-out infinite; }

    /* ═══════ LOGO ═══════ */
    .logo {
      font-family: 'JetBrains Mono', monospace;
      font-size: 4rem; font-weight: 900;
      background: linear-gradient(135deg, var(--cyan) 0%, var(--purple) 50%, var(--pink) 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text; letter-spacing: 0.15em;
      margin-bottom: 0.3rem;
      text-shadow: none;
      position: relative;
    }
    .logo::after {
      content: 'HAUBA';
      position: absolute; left: 0; top: 0;
      background: linear-gradient(135deg, var(--cyan), var(--purple), var(--pink));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
      filter: blur(30px); opacity: 0.4; z-index: -1;
    }
    .version-tag {
      display: inline-block;
      background: rgba(123, 47, 255, 0.15);
      border: 1px solid rgba(123, 47, 255, 0.3);
      border-radius: 20px; padding: 0.2rem 0.8rem;
      font-size: 0.7rem; font-weight: 600;
      color: var(--purple); margin-bottom: 1.5rem;
      letter-spacing: 0.05em;
    }
    .tagline {
      font-size: 1.3rem; color: var(--text-secondary);
      max-width: 550px; line-height: 1.6; margin-bottom: 1rem;
    }
    .tagline strong {
      color: var(--text-primary); font-weight: 600;
    }
    .sub-tagline {
      font-size: 0.9rem; color: var(--text-muted);
      margin-bottom: 2.5rem;
    }

    /* ═══════ BADGES ═══════ */
    .badges { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; margin-bottom: 3rem; }
    .badge {
      display: flex; align-items: center; gap: 0.4rem;
      background: rgba(15, 15, 26, 0.8);
      border: 1px solid var(--border); border-radius: 20px;
      padding: 0.35rem 0.85rem; font-size: 0.72rem;
      color: var(--text-secondary); font-weight: 500;
      backdrop-filter: blur(10px);
      transition: all 0.2s;
    }
    .badge:hover { border-color: var(--border-hover); color: var(--text-primary); }
    .badge-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--green); display: inline-block;
    }
    .badge-dot.cyan { background: var(--cyan); }
    .badge-dot.purple { background: var(--purple); }
    .badge-dot.pink { background: var(--pink); }

    /* ═══════ INSTALL SECTION ═══════ */
    .install-section {
      width: 100%; max-width: 580px;
      margin-bottom: 3rem;
    }
    .install-tabs {
      display: flex; gap: 0; margin-bottom: 0;
      border-bottom: 1px solid var(--border);
    }
    .install-tab {
      padding: 0.6rem 1.2rem; font-size: 0.78rem;
      color: var(--text-muted); cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s; font-weight: 500;
      background: none; border-top: none; border-left: none; border-right: none;
      font-family: inherit;
    }
    .install-tab:hover { color: var(--text-secondary); }
    .install-tab.active { color: var(--cyan); border-bottom-color: var(--cyan); }
    .install-panel {
      display: none;
      background: var(--bg-card);
      border: 1px solid var(--border); border-top: none;
      border-radius: 0 0 10px 10px;
      padding: 1.2rem 1.5rem;
      position: relative;
    }
    .install-panel.active { display: block; }
    .install-panel code {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem; color: var(--cyan);
      display: block; word-break: break-all;
    }
    .install-panel .copy-btn {
      position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
      background: rgba(123, 47, 255, 0.15); border: 1px solid rgba(123, 47, 255, 0.3);
      color: var(--purple); border-radius: 6px; padding: 0.35rem 0.7rem;
      font-size: 0.7rem; cursor: pointer; font-family: inherit; font-weight: 600;
      transition: all 0.2s;
    }
    .install-panel .copy-btn:hover {
      background: rgba(123, 47, 255, 0.25); color: var(--text-primary);
    }
    .copy-btn.copied { background: rgba(0, 255, 136, 0.15) !important; border-color: var(--green) !important; color: var(--green) !important; }

    /* ═══════ CTA BUTTONS ═══════ */
    .cta-group {
      display: flex; gap: 1rem; justify-content: center; margin-bottom: 4rem;
    }
    .cta-primary {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: linear-gradient(135deg, var(--purple), var(--pink));
      color: white; padding: 0.75rem 1.8rem;
      border-radius: 8px; text-decoration: none;
      font-weight: 600; font-size: 0.9rem;
      transition: all 0.2s; border: none; cursor: pointer;
      box-shadow: 0 4px 20px rgba(123, 47, 255, 0.3);
    }
    .cta-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 30px rgba(123, 47, 255, 0.4); }
    .cta-secondary {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: transparent;
      border: 1px solid var(--border); color: var(--text-secondary);
      padding: 0.75rem 1.8rem; border-radius: 8px;
      text-decoration: none; font-weight: 500; font-size: 0.9rem;
      transition: all 0.2s; cursor: pointer;
    }
    .cta-secondary:hover { border-color: var(--border-hover); color: var(--text-primary); }

    /* ═══════ FEATURES GRID ═══════ */
    .section { position: relative; z-index: 1; padding: 4rem 2rem; }
    .section-title {
      text-align: center; font-size: 2rem; font-weight: 800;
      margin-bottom: 0.5rem;
    }
    .section-subtitle {
      text-align: center; color: var(--text-muted); font-size: 0.95rem;
      margin-bottom: 3rem;
    }
    .features {
      display: grid; grid-template-columns: repeat(3, 1fr);
      gap: 1.2rem; max-width: 900px; margin: 0 auto;
    }
    .feature {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px; padding: 1.5rem;
      transition: all 0.3s;
      position: relative; overflow: hidden;
    }
    .feature::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0;
      height: 2px; background: linear-gradient(90deg, transparent, var(--cyan), transparent);
      opacity: 0; transition: opacity 0.3s;
    }
    .feature:hover { border-color: var(--border-hover); background: var(--bg-card-hover); transform: translateY(-2px); }
    .feature:hover::before { opacity: 1; }
    .feature-icon {
      width: 40px; height: 40px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.2rem; margin-bottom: 1rem;
    }
    .feature-icon.cyan { background: rgba(0, 212, 255, 0.1); color: var(--cyan); }
    .feature-icon.purple { background: rgba(123, 47, 255, 0.1); color: var(--purple); }
    .feature-icon.pink { background: rgba(255, 45, 135, 0.1); color: var(--pink); }
    .feature-icon.green { background: rgba(0, 255, 136, 0.1); color: var(--green); }
    .feature h3 { font-size: 0.95rem; font-weight: 700; margin-bottom: 0.4rem; color: var(--text-primary); }
    .feature p { font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5; }

    /* ═══════ ARCHITECTURE SECTION ═══════ */
    .arch-card {
      max-width: 700px; margin: 0 auto;
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 2rem; font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem; line-height: 1.7; color: var(--text-secondary);
    }
    .arch-card .a-comment { color: var(--text-muted); }
    .arch-card .a-key { color: var(--cyan); }
    .arch-card .a-val { color: var(--pink); }
    .arch-card .a-type { color: var(--purple); }

    /* ═══════ FOOTER ═══════ */
    .footer {
      position: relative; z-index: 1;
      text-align: center; padding: 3rem 2rem;
      border-top: 1px solid var(--border);
      color: var(--text-muted); font-size: 0.8rem;
    }
    .footer-links {
      display: flex; gap: 2rem; justify-content: center; margin-bottom: 1rem;
    }
    .footer-links a {
      color: var(--text-secondary); text-decoration: none;
      font-size: 0.82rem; transition: color 0.2s;
    }
    .footer-links a:hover { color: var(--cyan); }
    .footer-heart { color: var(--pink); }

    /* ═══════ RESPONSIVE ═══════ */
    @media (max-width: 768px) {
      .features { grid-template-columns: 1fr; }
      .logo { font-size: 2.5rem; }
      .tagline { font-size: 1.1rem; }
      .nav-links a:not(.nav-cta) { display: none; }
      .cta-group { flex-direction: column; align-items: center; }
      .mascot-svg { width: 150px; height: 180px; }
    }
    @media (max-width: 480px) {
      .logo { font-size: 2rem; }
      .install-tabs { flex-wrap: wrap; }
    }

    /* ═══════ SMOOTH SCROLL REVEAL ═══════ */
    .reveal { opacity: 0; transform: translateY(20px); transition: all 0.6s ease; }
    .reveal.visible { opacity: 1; transform: translateY(0); }
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  <div class="bg-glow"></div>
  <div class="bg-glow-bottom"></div>

  <!-- Navigation -->
  <nav class="nav">
    <div class="nav-brand">HAUBA</div>
    <div class="nav-links">
      <a href="#features">Features</a>
      <a href="#architecture">Architecture</a>
      <a href="https://github.com/NikeGunn/haubaa#readme">Docs</a>
      <a href="https://github.com/NikeGunn/haubaa" class="nav-cta">Star on GitHub</a>
    </div>
  </nav>

  <!-- Hero -->
  <section class="hero">
    <!-- Animated Mascot -->
    <div class="mascot-wrapper" id="mascot">
      <div class="wow-text">WOW!</div>
      <svg class="mascot-svg" viewBox="0 0 200 240" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bodyGrad" x1="50" y1="20" x2="150" y2="220" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#00d4ff"/>
            <stop offset="50%" stop-color="#7b2fff"/>
            <stop offset="100%" stop-color="#ff2d87"/>
          </linearGradient>
          <linearGradient id="bellyGrad" x1="70" y1="100" x2="130" y2="180" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(255,255,255,0.15)"/>
            <stop offset="100%" stop-color="rgba(255,255,255,0.03)"/>
          </linearGradient>
          <radialGradient id="glowGrad" cx="100" cy="120" r="90" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(123,47,255,0.2)"/>
            <stop offset="100%" stop-color="transparent"/>
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        <!-- Glow aura -->
        <ellipse cx="100" cy="130" rx="85" ry="95" fill="url(#glowGrad)" opacity="0.5"/>

        <g class="mascot-body-group">
          <!-- Arms (behind body) -->
          <g class="arm-left">
            <path d="M55 108 Q30 95 25 115 Q20 135 40 130 Q50 128 58 120" fill="url(#bodyGrad)" opacity="0.9"/>
            <ellipse cx="25" cy="118" rx="8" ry="7" fill="url(#bodyGrad)" opacity="0.9"/>
          </g>
          <g class="arm-right">
            <path d="M145 108 Q170 95 175 115 Q180 135 160 130 Q150 128 142 120" fill="url(#bodyGrad)" opacity="0.9"/>
            <ellipse cx="175" cy="118" rx="8" ry="7" fill="url(#bodyGrad)" opacity="0.9"/>
          </g>

          <!-- Main body (big belly) -->
          <g class="belly">
            <ellipse cx="100" cy="130" rx="58" ry="72" fill="url(#bodyGrad)"/>
            <!-- Belly highlight -->
            <ellipse cx="100" cy="138" rx="42" ry="50" fill="url(#bellyGrad)"/>
            <!-- Belly button -->
            <ellipse cx="100" cy="155" rx="4" ry="5" fill="rgba(0,0,0,0.2)"/>
          </g>

          <!-- Head (on top of body) -->
          <ellipse cx="100" cy="65" rx="38" ry="36" fill="url(#bodyGrad)"/>
          <!-- Head highlight -->
          <ellipse cx="92" cy="55" rx="18" ry="14" fill="rgba(255,255,255,0.07)"/>

          <!-- Antenna/hair -->
          <g>
            <path d="M100 30 Q95 10 105 5" stroke="url(#bodyGrad)" stroke-width="3" fill="none" stroke-linecap="round">
              <animateTransform attributeName="transform" type="rotate" values="0 100 30;8 100 30;-8 100 30;0 100 30" dur="2s" repeatCount="indefinite"/>
            </path>
            <circle cx="105" cy="5" r="5" fill="var(--cyan)" filter="url(#glow)">
              <animate attributeName="r" values="5;7;5" dur="1.5s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.8;1;0.8" dur="1.5s" repeatCount="indefinite"/>
            </circle>
          </g>

          <!-- Eyes -->
          <g class="eye-blink">
            <!-- Left eye white -->
            <ellipse cx="85" cy="62" rx="12" ry="13" fill="white"/>
            <!-- Left eye pupil -->
            <g class="eye-pupil">
              <circle cx="87" cy="63" r="6" fill="#1a1a2e"/>
              <circle cx="89" cy="60" r="2.5" fill="white" opacity="0.9"/>
            </g>
          </g>
          <g class="eye-blink-r">
            <!-- Right eye white -->
            <ellipse cx="115" cy="62" rx="12" ry="13" fill="white"/>
            <!-- Right eye pupil -->
            <g class="eye-pupil">
              <circle cx="117" cy="63" r="6" fill="#1a1a2e"/>
              <circle cx="119" cy="60" r="2.5" fill="white" opacity="0.9"/>
            </g>
          </g>

          <!-- Mouth (O shape for WOW) -->
          <ellipse class="mouth-wow" cx="100" cy="82" rx="8" ry="4" fill="#1a0a2e">
            <animate attributeName="ry" values="4;12;5;14;4;13;4" dur="3s" repeatCount="indefinite"/>
            <animate attributeName="rx" values="8;10;7;11;8;10;8" dur="3s" repeatCount="indefinite"/>
          </ellipse>
          <!-- Inner mouth -->
          <ellipse cx="100" cy="84" rx="5" ry="2" fill="#0a0020" opacity="0.6">
            <animate attributeName="ry" values="2;8;3;9;2;8;2" dur="3s" repeatCount="indefinite"/>
            <animate attributeName="rx" values="5;7;4;7;5;7;5" dur="3s" repeatCount="indefinite"/>
          </ellipse>

          <!-- Feet -->
          <ellipse cx="80" cy="198" rx="16" ry="8" fill="url(#bodyGrad)" opacity="0.9"/>
          <ellipse cx="120" cy="198" rx="16" ry="8" fill="url(#bodyGrad)" opacity="0.9"/>

          <!-- Sparkle particles -->
          <circle cx="45" cy="50" r="2" fill="var(--cyan)" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2s" begin="0s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="50;20" dur="2s" begin="0s" repeatCount="indefinite"/>
          </circle>
          <circle cx="155" cy="45" r="1.5" fill="var(--pink)" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2.5s" begin="0.5s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="45;15" dur="2.5s" begin="0.5s" repeatCount="indefinite"/>
          </circle>
          <circle cx="60" cy="35" r="1.5" fill="var(--purple)" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="1.8s" begin="1s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="35;10" dur="1.8s" begin="1s" repeatCount="indefinite"/>
          </circle>
          <circle cx="140" cy="40" r="2" fill="var(--green)" opacity="0">
            <animate attributeName="opacity" values="0;1;0" dur="2.2s" begin="0.3s" repeatCount="indefinite"/>
            <animate attributeName="cy" values="40;12" dur="2.2s" begin="0.3s" repeatCount="indefinite"/>
          </circle>
        </g>
      </svg>
    </div>

    <h1 class="logo">HAUBA</h1>
    <div class="version-tag">v0.1.0 &mdash; Public Beta</div>
    <p class="tagline">One command. An <strong>AI engineering team</strong> at your service.</p>
    <p class="sub-tagline">Open-source agent framework that orchestrates teams of AI to build real software.</p>

    <div class="badges">
      <span class="badge"><span class="badge-dot"></span> Python 3.11+</span>
      <span class="badge"><span class="badge-dot cyan"></span> Open Source</span>
      <span class="badge"><span class="badge-dot purple"></span> MIT License</span>
      <span class="badge"><span class="badge-dot pink"></span> Offline Capable</span>
    </div>

    <!-- Install Commands with Tabs -->
    <div class="install-section">
      <div class="install-tabs">
        <button class="install-tab active" onclick="switchTab(0)">pip</button>
        <button class="install-tab" onclick="switchTab(1)">macOS / Linux</button>
        <button class="install-tab" onclick="switchTab(2)">Windows</button>
      </div>
      <div class="install-panel active" id="tab-0">
        <code>pip install hauba</code>
        <button class="copy-btn" onclick="copyCmd(this, 'pip install hauba')">Copy</button>
      </div>
      <div class="install-panel" id="tab-1">
        <code>curl -fsSL https://hauba.tech/install.sh | sh</code>
        <button class="copy-btn" onclick="copyCmd(this, 'curl -fsSL https://hauba.tech/install.sh | sh')">Copy</button>
      </div>
      <div class="install-panel" id="tab-2">
        <code>irm hauba.tech/install.ps1 | iex</code>
        <button class="copy-btn" onclick="copyCmd(this, 'irm hauba.tech/install.ps1 | iex')">Copy</button>
      </div>
    </div>

    <div class="cta-group">
      <a href="https://github.com/NikeGunn/haubaa" class="cta-primary">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        Star on GitHub
      </a>
      <a href="https://github.com/NikeGunn/haubaa#readme" class="cta-secondary">
        Read the Docs
      </a>
    </div>
  </section>

  <!-- Features -->
  <section class="section" id="features">
    <h2 class="section-title reveal">Why Hauba?</h2>
    <p class="section-subtitle reveal">Not another chatbot. A full AI engineering company in your terminal.</p>
    <div class="features">
      <div class="feature reveal">
        <div class="feature-icon cyan">&#x2B21;</div>
        <h3>Multi-Agent Teams</h3>
        <p>Director, SubAgents, Workers &mdash; a real engineering hierarchy that plans, delegates, and executes.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon purple">&#x26D3;</div>
        <h3>Zero Hallucination</h3>
        <p>TaskLedger with SHA-256 hash-chain + bit-vector guarantees every output is verified on disk.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon green">&#x26A1;</div>
        <h3>Works Offline</h3>
        <p>Full support for Ollama local models. Your code never leaves your machine.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon pink">&#x2B2A;</div>
        <h3>Skills &amp; Strategies</h3>
        <p>Composable .md skills and .yaml cognitive playbooks teach agents domain expertise.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon cyan">&#x2B22;</div>
        <h3>Think-Then-Act</h3>
        <p>Every agent deliberates before executing. Minimum think times enforced. No reckless code.</p>
      </div>
      <div class="feature reveal">
        <div class="feature-icon purple">&#x2339;</div>
        <h3>Zero Dependencies</h3>
        <p>No Docker, Redis, or Postgres. SQLite for everything. pip install and go.</p>
      </div>
    </div>
  </section>

  <!-- Architecture -->
  <section class="section" id="architecture">
    <h2 class="section-title reveal">Architecture</h2>
    <p class="section-subtitle reveal">Python-first. Single process. Event-driven. Crash-safe.</p>
    <div class="arch-card reveal">
      <span class="a-comment"># Agent Hierarchy</span><br>
      <span class="a-key">Owner</span> <span class="a-type">(Human)</span><br>
      &nbsp;&nbsp;<span class="a-val">&#x2514;&#x2500;&#x2500;</span> <span class="a-key">Director</span> <span class="a-type">(CEO)</span> <span class="a-comment">&mdash; deliberates, plans, delegates</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-val">&#x251C;&#x2500;&#x2500;</span> <span class="a-key">SubAgent</span> <span class="a-type">(Team Lead)</span> <span class="a-comment">&mdash; manages milestone</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-val">&#x251C;&#x2500;&#x2500;</span> <span class="a-key">Worker</span> <span class="a-type">(Specialist)</span> <span class="a-comment">&mdash; executes in sandbox</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2514;&#x2500;&#x2500;</span> <span class="a-key">CoWorker</span> <span class="a-type">(Helper)</span> <span class="a-comment">&mdash; ephemeral, single task</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2502;</span>&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2514;&#x2500;&#x2500;</span> <span class="a-key">Worker</span> ...<br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-val">&#x2514;&#x2500;&#x2500;</span> <span class="a-key">SubAgent</span> ...<br><br>
      <span class="a-comment"># Communication: async events &mdash; full audit trail</span><br>
      <span class="a-comment"># Storage: SQLite &mdash; zero external dependencies</span><br>
      <span class="a-comment"># TaskLedger: every level &mdash; GateCheck before delivery</span>
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
    <p>Built with <span class="footer-heart">&hearts;</span> by the Hauba community. MIT License.</p>
  </footer>

  <script>
    // Tab switcher
    function switchTab(idx) {
      document.querySelectorAll('.install-tab').forEach((t, i) => t.classList.toggle('active', i === idx));
      document.querySelectorAll('.install-panel').forEach((p, i) => p.classList.toggle('active', i === idx));
    }

    // Copy to clipboard
    function copyCmd(btn, text) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    }

    // Scroll reveal
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    // Mascot click interaction
    document.getElementById('mascot').addEventListener('click', function() {
      this.style.transform = 'scale(1.1) rotate(5deg)';
      setTimeout(() => this.style.transform = '', 400);
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
