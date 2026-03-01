"""Cross-platform keyboard input for interactive menus.

Provides arrow-key navigation, Enter to select, and Escape to cancel.
Works on Windows (msvcrt) and Unix (termios/tty) without external deps.
"""

from __future__ import annotations

import sys


def _read_key_windows() -> str:
    """Read a single keypress on Windows using msvcrt."""
    import msvcrt

    ch = msvcrt.getwch()

    # Arrow keys on Windows: first char is '\x00' or '\xe0', second is the key
    if ch in ("\x00", "\xe0"):
        ch2 = msvcrt.getwch()
        win_arrows = {"H": "up", "P": "down", "K": "left", "M": "right"}
        return win_arrows.get(ch2, "unknown")

    if ch == "\r":
        return "enter"
    if ch == "\x1b":
        return "escape"
    if ch == " ":
        return "space"
    if ch == "q":
        return "quit"
    if ch in ("j", "J"):
        return "down"
    if ch in ("k", "K"):
        return "up"

    return ch


def _read_key_unix() -> str:
    """Read a single keypress on Unix using termios."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == "\x1b":
            # Could be an escape sequence (arrow keys)
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                unix_arrows = {"A": "up", "B": "down", "C": "right", "D": "left"}
                return unix_arrows.get(ch3, "escape")
            return "escape"

        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch == "q":
            return "quit"
        if ch in ("j", "J"):
            return "down"
        if ch in ("k", "K"):
            return "up"
        if ch == "\x03":
            # Ctrl+C
            raise KeyboardInterrupt

        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key() -> str:
    """Read a single keypress. Returns: 'up', 'down', 'enter', 'escape', 'quit', or the char."""
    if sys.platform == "win32":
        return _read_key_windows()
    else:
        return _read_key_unix()
