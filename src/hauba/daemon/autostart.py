"""Auto-start daemon — register hauba agent to start automatically on login.

When a user runs `hauba agent --install`, it registers a background service
that starts the daemon automatically when the machine boots/logs in.

Approach:
- Windows: Creates a scheduled task (runs on user logon)
- macOS: Creates a LaunchAgent plist
- Linux: Creates a systemd user service

The daemon runs in the background, polling for tasks from the server.
No need to manually open a terminal and run `hauba agent` every time.

Uninstall with `hauba agent --uninstall`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger()

# Service name
SERVICE_NAME = "hauba-agent"
SERVICE_DESCRIPTION = "Hauba AI Agent — polls server for tasks and builds locally"


def install_autostart(
    server_url: str = "https://hauba.tech",
    workspace: str = "",
    owner_id: str = "",
    poll_interval: float = 10.0,
) -> bool:
    """Install the daemon to start automatically on user login.

    Returns True if installed successfully.
    """
    platform = sys.platform

    # Build the hauba agent command
    hauba_bin = _find_hauba_binary()
    if not hauba_bin:
        logger.error("autostart.hauba_not_found")
        return False

    args = [hauba_bin, "agent", "--server", server_url]
    if workspace:
        args.extend(["--workspace", workspace])
    if owner_id:
        args.extend(["--owner", owner_id])
    if poll_interval != 10.0:
        args.extend(["--interval", str(poll_interval)])

    if platform == "win32":
        return _install_windows(args)
    elif platform == "darwin":
        return _install_macos(args)
    else:
        return _install_linux(args)


def uninstall_autostart() -> bool:
    """Remove the auto-start daemon registration.

    Returns True if uninstalled successfully.
    """
    platform = sys.platform

    if platform == "win32":
        return _uninstall_windows()
    elif platform == "darwin":
        return _uninstall_macos()
    else:
        return _uninstall_linux()


def is_installed() -> bool:
    """Check if the auto-start daemon is registered."""
    platform = sys.platform

    if platform == "win32":
        return _is_installed_windows()
    elif platform == "darwin":
        return _is_installed_macos()
    else:
        return _is_installed_linux()


def _find_hauba_binary() -> str | None:
    """Find the hauba CLI binary path."""
    # Try direct import path
    hauba_path = Path(sys.executable).parent / "hauba"
    if hauba_path.exists():
        return str(hauba_path)

    # Windows .exe
    hauba_exe = hauba_path.with_suffix(".exe")
    if hauba_exe.exists():
        return str(hauba_exe)

    # Try python -m hauba
    return f"{sys.executable} -m hauba"


# --- Windows: Scheduled Task ---


def _install_windows(args: list[str]) -> bool:
    """Create a Windows scheduled task that runs on user logon."""
    cmd_str = " ".join(f'"{a}"' if " " in a else a for a in args)
    log_dir = Path.home() / ".hauba" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use pythonw to avoid console window
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    if pythonw.exists():
        cmd_str = cmd_str.replace(sys.executable, str(pythonw))

    try:
        # Delete existing task first (idempotent)
        subprocess.run(
            ["schtasks", "/delete", "/tn", SERVICE_NAME, "/f"],
            capture_output=True,
            text=True,
        )

        # Create new task
        result = subprocess.run(
            [
                "schtasks",
                "/create",
                "/tn",
                SERVICE_NAME,
                "/tr",
                cmd_str,
                "/sc",
                "onlogon",
                "/rl",
                "limited",
                "/f",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("autostart.installed", platform="windows")
            return True

        logger.error(
            "autostart.install_failed",
            platform="windows",
            stderr=result.stderr[:200],
        )
        return False
    except Exception as exc:
        logger.error("autostart.install_error", platform="windows", error=str(exc))
        return False


def _uninstall_windows() -> bool:
    """Remove the Windows scheduled task."""
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", SERVICE_NAME, "/f"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_installed_windows() -> bool:
    """Check if the Windows scheduled task exists."""
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", SERVICE_NAME],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


# --- macOS: LaunchAgent ---


def _install_macos(args: list[str]) -> bool:
    """Create a macOS LaunchAgent plist."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "tech.hauba.agent.plist"

    log_dir = Path.home() / ".hauba" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    args_xml = "\n".join(f"    <string>{a}</string>" for a in args)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>tech.hauba.agent</string>
  <key>ProgramArguments</key>
  <array>
{args_xml}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_dir / "agent.log"}</string>
  <key>StandardErrorPath</key>
  <string>{log_dir / "agent-error.log"}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}</string>
  </dict>
</dict>
</plist>
"""

    try:
        plist_path.write_text(plist_content, encoding="utf-8")

        # Load the agent
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("autostart.installed", platform="macos")
            return True

        logger.error("autostart.install_failed", platform="macos", stderr=result.stderr[:200])
        return False
    except Exception as exc:
        logger.error("autostart.install_error", platform="macos", error=str(exc))
        return False


def _uninstall_macos() -> bool:
    """Remove the macOS LaunchAgent."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / "tech.hauba.agent.plist"
    try:
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        if plist_path.exists():
            plist_path.unlink()
        return True
    except Exception:
        return False


def _is_installed_macos() -> bool:
    """Check if the macOS LaunchAgent exists."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / "tech.hauba.agent.plist"
    return plist_path.exists()


# --- Linux: systemd user service ---


def _install_linux(args: list[str]) -> bool:
    """Create a systemd user service."""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / f"{SERVICE_NAME}.service"

    exec_start = " ".join(args)

    service_content = f"""[Unit]
Description={SERVICE_DESCRIPTION}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=30
Environment=PATH={os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}

[Install]
WantedBy=default.target
"""

    try:
        service_path.write_text(service_content, encoding="utf-8")

        # Reload systemd and enable the service
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        result = subprocess.run(
            ["systemctl", "--user", "enable", "--now", SERVICE_NAME],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("autostart.installed", platform="linux")
            return True

        logger.error("autostart.install_failed", platform="linux", stderr=result.stderr[:200])
        return False
    except Exception as exc:
        logger.error("autostart.install_error", platform="linux", error=str(exc))
        return False


def _uninstall_linux() -> bool:
    """Remove the systemd user service."""
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", SERVICE_NAME],
            capture_output=True,
        )
        service_path = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
        if service_path.exists():
            service_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        return True
    except Exception:
        return False


def _is_installed_linux() -> bool:
    """Check if the systemd user service exists."""
    service_path = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
    return service_path.exists()
