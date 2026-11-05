import pytest
from actions.computer_settings import (
    brightness_set,
    brightness_get,
    brightness_up,
    brightness_down,
    computer_settings,
    _detect_action,
)


def test_brightness_set_and_get():
    # Set to 70%
    ok = brightness_set(70)
    assert ok is True
    cur = brightness_get()
    assert cur is not None
    assert 0 <= cur <= 100

    # Clamp bounds check
    brightness_set(120)
    assert brightness_get() <= 100
    brightness_set(-10)
    assert brightness_get() >= 0


def test_brightness_up_and_down():
    brightness_set(50)
    up = brightness_up(15)
    assert up == 65
    assert brightness_get() == 65

    down = brightness_down(20)
    assert down == 45
    assert brightness_get() == 45


def test_brightness_action_detection():
    # Free-text parsing with percentage
    res1 = _detect_action("set brightness to 80%")
    assert res1["action"] == "brightness_set"
    assert res1["value"] == 80

    res2 = _detect_action("increase brightness by 15%")
    assert res2["action"] == "brightness_up"
    assert res2["value"] == 15

    res3 = _detect_action("dim brightness by 10%")
    assert res3["action"] == "brightness_down"
    assert res3["value"] == 10

    res4 = _detect_action("screen brightness 60")
    assert res4["action"] == "brightness_set"
    assert res4["value"] == 60


def test_computer_settings_brightness_dispatch():
    # Direct action: set_brightness
    out1 = computer_settings({"action": "brightness_set", "value": "75"})
    assert "done" in out1.lower()
    assert "75" in out1

    # Action: brightness_up with custom step
    out2 = computer_settings({"action": "brightness_up", "value": "10"})
    assert "done" in out2.lower()

    # Action: get_brightness
    out3 = computer_settings({"action": "get_brightness"})
    assert "done" in out3.lower()
    assert "brightness" in out3.lower()

    # Restore to 100%
    brightness_set(100)

