"""
tests/test_undo_stack.py — Unit tests for the shared undo stack.
"""
from __future__ import annotations

from core import undo


def test_undo_stack_push_and_pop():
    # Clear stack before test
    with undo._lock:
        undo._stack.clear()

    assert not undo.can_undo()
    assert undo.peek() == ""

    reverted = []

    def undo_action_1():
        reverted.append("action_1")
        return "Undid action 1"

    def undo_action_2():
        reverted.append("action_2")
        return "Undid action 2"

    undo.push_undo("Action 1", undo_action_1)
    undo.push_undo("Action 2", undo_action_2)

    assert undo.can_undo()
    assert undo.peek() == "Action 2"

    # Pop most recent (LIFO)
    res2 = undo.undo_last()
    assert "Undid action 2" in res2
    assert reverted == ["action_2"]
    assert undo.peek() == "Action 1"

    # Pop remaining
    res1 = undo.undo_last()
    assert "Undid action 1" in res1
    assert reverted == ["action_2", "action_1"]
    assert not undo.can_undo()


def test_undo_stack_max_depth():
    with undo._lock:
        undo._stack.clear()

    for i in range(15):
        undo.push_undo(f"Action {i}", lambda idx=i: f"Undid {idx}")

    # Stack must be capped at MAX_DEPTH (10)
    with undo._lock:
        assert len(undo._stack) == undo.MAX_DEPTH
        # Oldest dropped, newest kept
        assert undo._stack[-1].label == "Action 14"
        assert undo._stack[0].label == "Action 5"
