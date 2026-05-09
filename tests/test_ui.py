from __future__ import annotations

from io import StringIO

from rich.console import Console

import daylily_ec.ui as ui


def test_fail_escapes_regex_markup(monkeypatch):
    buffer = StringIO()
    monkeypatch.setattr(
        ui,
        "console",
        Console(file=buffer, force_terminal=False, color_system=None, width=120),
    )

    ui.fail("Bad Request: '260509-frz' does not match '^[a-zA-Z][a-zA-Z0-9-]+$'")

    assert "^[a-zA-Z][a-zA-Z0-9-]+$" in buffer.getvalue()
