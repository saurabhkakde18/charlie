"""
tests/test_model_ladder.py — Unit test for Gemini Model Ladder Cooldowns and Error Fallback.

Simulates 429 (quota exhausted), 503 (unavailable), and 404 (model not found) responses,
verifying that the ladder properly identifies errors, cools rungs, and steps to the next.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from core import gemini


def test_error_classification():
    # 429 / Quota
    assert gemini.is_quota_error("429 RESOURCE_EXHAUSTED: quota exceeded")
    assert gemini.is_quota_error("Resource has been exhausted (e.g. check quota).")
    assert not gemini.is_quota_error("200 OK")

    # 503 / 504 / Unavailable
    assert gemini.is_unavailable_error("503 UNAVAILABLE: backend overloaded")
    assert gemini.is_unavailable_error("504 DEADLINE_EXCEEDED")
    assert gemini.is_unavailable_error("Server temporarily unavailable")
    assert not gemini.is_unavailable_error("404 Not Found")

    # 404 / 403 / Gone
    assert gemini.is_gone_error("404 NOT_FOUND: models/nonexistent is not found")
    assert gemini.is_gone_error("403 PERMISSION_DENIED: caller does not have permission")
    assert gemini.is_gone_error("Model is not supported for generateContent")
    assert not gemini.is_gone_error("429 Quota")


def test_cooldown_mechanism():
    test_model = "test-gemini-model"
    # Initially not cooling
    assert not gemini._cooling(test_model)

    # Put on cooldown for 2 seconds
    gemini._cool(test_model, seconds=2.0)
    assert gemini._cooling(test_model)

    # Clear cooldown
    with gemini._cool_lock:
        gemini._cooldown.pop(test_model, None)
    assert not gemini._cooling(test_model)


def test_ladder_simulation_429_503_404():
    """
    Simulate consecutive failures:
      Rung 1: 429 Quota -> cooldown applied -> steps down
      Rung 2: 503 Unavailable -> cooldown applied -> steps down
      Rung 3: 404 Not Found -> cooldown applied -> steps down
      Rung 4: Success!
    """
    # Clear any active cooldowns
    with gemini._cool_lock:
        gemini._cooldown.clear()

    call_history = []

    def mock_generate_content(**kwargs):
        model = kwargs.get("model", "")
        call_history.append(model)
        if len(call_history) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota limit reached")
        elif len(call_history) == 2:
            raise RuntimeError("503 The model is overloaded. Please try again later.")
        elif len(call_history) == 3:
            raise RuntimeError("404 models/gemini-old is not found for API version v1beta")
        else:
            mock_resp = MagicMock()
            mock_resp.text = "Success from fallback model"
            return mock_resp

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = mock_generate_content

    with patch("core.gemini.client", return_value=mock_client), \
         patch("core.gemini.api_key", return_value="AIzaFakeTestKey"):
        # Make a one-shot text call using SEARCH ladder (REST only, avoids LIVE slot)
        resp = gemini.call("Hello test", tier=gemini.SEARCH)
        assert resp is not None
        assert resp.text == "Success from fallback model"

    # Verify that the ladder stepped through 4 rungs
    assert len(call_history) == 4, f"Expected 4 attempts, got {call_history}"

    # Verify that the 3 failed models are now on cooldown
    m1, m2, m3, m4 = call_history
    assert gemini._cooling(m1), f"Model 1 ({m1}) should be on cooldown after 429"
    assert gemini._cooling(m2), f"Model 2 ({m2}) should be on cooldown after 503"
    assert gemini._cooling(m3), f"Model 3 ({m3}) should be on cooldown after 404"
    assert not gemini._cooling(m4), f"Model 4 ({m4}) succeeded and should not be on cooldown"

    # Clean up
    with gemini._cool_lock:
        gemini._cooldown.clear()

