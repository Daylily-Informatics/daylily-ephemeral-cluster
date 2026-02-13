"""Colorized console output for daylily-ec workflows.

Thin wrapper around :mod:`rich` that degrades gracefully when stdout
is not a TTY (e.g. piped, CI, cron).  All user-facing status messages
should flow through this module; ``logger.*`` calls are kept for
structured file logging.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel

# Shared console — auto-detects TTY; force_terminal=None lets Rich decide.
console = Console(stderr=False, force_terminal=None)

# ── Symbols ────────────────────────────────────────────────────────────────

_PASS = "[bold green]✓[/]"
_FAIL = "[bold red]✗[/]"
_WARN = "[bold yellow]⚠[/]"
_ARROW = "[bold cyan]›[/]"
_DOT = "[dim]·[/]"

# ── Phase headers ──────────────────────────────────────────────────────────


def phase(title: str) -> None:
    """Print a bold phase header (e.g. ``PREFLIGHT``, ``CREATE``)."""
    console.print()
    console.print(f"[bold blue]── {title} ──[/]")


# ── Status lines ───────────────────────────────────────────────────────────


def ok(msg: str) -> None:
    """Green checkmark + message."""
    console.print(f"  {_PASS} {msg}")


def fail(msg: str) -> None:
    """Red cross + message."""
    console.print(f"  {_FAIL} [red]{msg}[/]")


def warn(msg: str) -> None:
    """Yellow warning + message."""
    console.print(f"  {_WARN} [yellow]{msg}[/]")


def step(msg: str) -> None:
    """Cyan arrow + action message (in-progress)."""
    console.print(f"  {_ARROW} {msg}")


def info(msg: str) -> None:
    """Dim dot + informational message."""
    console.print(f"  {_DOT} [dim]{msg}[/]")


def detail(key: str, value: str) -> None:
    """Key-value pair, indented."""
    console.print(f"    [bold]{key}[/]: {value}")


def error_msg(msg: str) -> None:
    """Bold red error message (not indented)."""
    console.print(f"[bold red]ERROR:[/] {msg}")


# ── Banners / panels ──────────────────────────────────────────────────────


def success_panel(title: str, body: str) -> None:
    """Green-bordered success panel."""
    console.print()
    console.print(
        Panel(
            body,
            title=f"[bold green]{title}[/]",
            border_style="green",
            padding=(1, 2),
        )
    )


def error_panel(title: str, body: str) -> None:
    """Red-bordered error panel."""
    console.print()
    console.print(
        Panel(
            body,
            title=f"[bold red]{title}[/]",
            border_style="red",
            padding=(1, 2),
        )
    )


# ── Progress helpers ───────────────────────────────────────────────────────


def elapsed_str(seconds: float) -> str:
    """Format seconds as ``Xm Ys``."""
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def progress_line(msg: str, *, end: str = "\n") -> None:
    """Overwrite-friendly single-line progress (for polling loops).

    When stdout is a TTY, uses ``\\r`` to overwrite the line.
    Otherwise falls back to normal print.
    """
    if sys.stdout.isatty():
        console.print(f"  {_ARROW} {msg}", end="\r", highlight=False)
    else:
        console.print(f"  {_ARROW} {msg}", highlight=False)


def clear_progress() -> None:
    """Clear a progress_line (TTY only)."""
    if sys.stdout.isatty():
        console.print(" " * console.width, end="\r")

