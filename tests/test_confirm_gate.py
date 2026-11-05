"""
tests/test_confirm_gate.py — Unit tests for UI confirmation token gate.
"""
from __future__ import annotations

import time
from core import confirm


def test_confirm_gate_flow():
    mock_shown = []
    mock_hidden = []
    logs = []

    confirm.bind(
        show=lambda t, d: mock_shown.append((t, d)),
        hide=lambda: mock_hidden.append(True),
        log=lambda m: logs.append(m),
    )

    executed = []

    def dangerous_action():
        executed.append("done")
        return "System shutdown performed"

    # 1. Request confirmation
    token_resp = confirm.request(
        key="shutdown",
        title="Confirm Shutdown",
        detail="Shutdown system?",
        run=dangerous_action,
    )
    assert "[CONFIRMATION_PENDING]" in token_resp
    assert len(mock_shown) == 1
    assert mock_shown[0][0] == "Confirm Shutdown"
    assert executed == []  # Not executed yet!

    # 2. Reject
    confirm.resolve(False)
    assert any("Cancelled" in m for m in logs)
    assert executed == []
    assert len(mock_hidden) == 1

    # 3. Request again and Approve
    mock_shown.clear()
    confirm.request(
        key="shutdown",
        title="Confirm Shutdown",
        detail="Shutdown system?",
        run=dangerous_action,
    )
    confirm.resolve(True)
    time.sleep(0.05)  # Allow worker thread to run callable
    assert executed == ["done"]
    assert any("Confirmed" in m for m in logs)


def test_confirm_gate_timeout():
    executed = []
    logs = []
    confirm.bind(show=lambda t, d: None, hide=lambda: None, log=lambda m: logs.append(m))

    confirm.request(
        key="delete",
        title="Delete",
        detail="Delete file",
        run=lambda: executed.append("deleted"),
    )

    # Force timestamp into past
    with confirm._lock:
        if confirm._pending:
            confirm._pending.at = time.monotonic() - (confirm.TIMEOUT_SECONDS + 5)

    confirm.resolve(True)
    assert any("expired" in m.lower() for m in logs)
    assert executed == []
