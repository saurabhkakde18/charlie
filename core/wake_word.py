"""
Local wake-word detection for Charlie.

Design goals:
  • ZERO cost when the feature is off — openwakeword is imported ONLY inside
    start()/install helpers, never at module load. If the user never enables
    wake word, none of this touches the app.
  • ZERO latency on the audio path — the microphone callback only ever does a
    cheap, non-blocking queue push (feed()); the actual model inference runs in
    this module's own background thread, so the real-time audio thread and the
    Gemini stream are never slowed.
  • Graceful fallback — if a custom "Hey Charlie" model is not present, falls
    back gracefully to Push-to-Talk (Ctrl+Space) with clear instructions on how
    to train or add custom models. Never fakes wake-word detection.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from memory.config_manager import (
    get_wake_word_model,
    get_wake_word_phrase,
    get_assistant_name,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CUSTOM_MODELS_DIR = BASE_DIR / "models"

# Score in [0,1]; above this counts as a detection. Tunable per environment.
DEFAULT_THRESHOLD = 0.5
# Mic frames arrive at 16 kHz int16; this is just the detector's input rate.
SAMPLE_RATE = 16000


def get_active_model_name() -> str:
    """Return the currently configured model identifier (e.g. 'hey_charlie', 'hey_jarvis')."""
    return get_wake_word_model()


def find_model_path(model_name: Optional[str] = None) -> Optional[Path]:
    """
    Search for a wake word model file in:
      1. Project-local models/ folder (for custom user-trained models like hey_charlie.onnx)
      2. openwakeword package resources directory
    """
    name = (model_name or get_active_model_name()).strip().lower()
    CUSTOM_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Project models/ directory
    for ext in (".onnx", ".tflite"):
        direct = CUSTOM_MODELS_DIR / f"{name}{ext}"
        if direct.exists():
            return direct
        matches = list(CUSTOM_MODELS_DIR.glob(f"{name}*{ext}"))
        if matches:
            return matches[0]

    # 2. openwakeword built-in resources
    try:
        import openwakeword
        pkg_models = Path(openwakeword.__file__).resolve().parent / "resources" / "models"
        if pkg_models.is_dir():
            for ext in (".onnx", ".tflite"):
                direct = pkg_models / f"{name}{ext}"
                if direct.exists():
                    return direct
                matches = list(pkg_models.glob(f"{name}*{ext}"))
                if matches:
                    return matches[0]
    except Exception:
        pass

    return None


def is_installed() -> bool:
    """True if the openwakeword package is importable (no model check)."""
    try:
        import importlib.util
        return importlib.util.find_spec("openwakeword") is not None
    except Exception:
        return False


def is_ready(model_name: Optional[str] = None) -> bool:
    """
    True if openwakeword is installed, embedding/mel models exist, and the
    requested wake word model file exists on disk.
    """
    if not is_installed():
        return False
    name = model_name or get_active_model_name()
    m_path = find_model_path(name)
    if not m_path or not m_path.exists():
        return False
    try:
        import openwakeword
        pkg_models = Path(openwakeword.__file__).resolve().parent / "resources" / "models"
        if not pkg_models.is_dir():
            return False
        has_mel = (any(pkg_models.glob("melspectrogram*.onnx"))
                   or any(pkg_models.glob("melspectrogram*.tflite")))
        has_emb = (any(pkg_models.glob("embedding_model*.onnx"))
                   or any(pkg_models.glob("embedding_model*.tflite")))
        return bool(has_mel and has_emb)
    except Exception:
        return False


def get_training_instructions() -> str:
    """Clear guide on how to train or install a custom 'Hey Charlie' model."""
    lines = [
        "How to train or add a custom 'Hey Charlie' wake word model:",
        "1. OpenWakeWord allows training custom wake words using synthetic audio:",
        "   https://github.com/dscripka/openWakeWord",
        "   Follow their Google Colab notebook for 'Training Custom Models'.",
        "2. Export the trained model as an ONNX file named 'hey_charlie.onnx'.",
        f"3. Place 'hey_charlie.onnx' into the 'models/' directory in this project ({CUSTOM_MODELS_DIR}).",
        "4. Alternatively, you can configure an existing pretrained model (such as 'hey_jarvis')",
        "   in Settings or api_keys.json under 'wake_word_model'.",
        "5. Push-to-Talk (Ctrl+Space) is always available without any models.",
    ]
    return "\n".join(lines)


def install_and_download(logger: Callable[[str], None] = print,
                         notify: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """
    One-click setup for the UI button: pip-install openwakeword if missing, then
    download the base models. Returns (ok, message). Never raises.
    """
    _tell = notify or (lambda _msg: None)
    try:
        if not is_installed():
            logger("Wake word: installing openwakeword (one-time)…")
            _tell("Wake word: installing openwakeword (one-time)…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "openwakeword"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
                return False, f"pip install failed: {tail[0][:160]}"

        # Download base acoustic models
        logger("Wake word: downloading base models…")
        _tell("Wake word: downloading base models…")
        try:
            import openwakeword.utils as _u
            _u.download_models()
        except Exception as e:
            return False, f"base model download failed: {e}"

        target = get_active_model_name()
        if not is_ready(target):
            info = (
                f"Base openWakeWord installed. Pretrained models ready.\n"
                f"Custom model '{target}.onnx' not found in models/ directory.\n"
                f"{get_training_instructions()}"
            )
            logger(info)
            return False, f"Custom model '{target}' not in models/ folder. Falling back to Push-to-Talk."

        logger(f"Wake word: model '{target}' ready.")
        return True, f"Wake word '{target}' ready."
    except Exception as e:
        return False, f"setup error: {e}"


class WakeWordDetector:
    """
    Runs the wake model in a dedicated thread. The mic thread calls feed() with
    raw int16 frames; detections invoke on_detect().
    """

    def __init__(self, on_detect: Callable[[], None],
                 threshold: float = DEFAULT_THRESHOLD,
                 logger: Callable[[str], None] = print,
                 notify: Callable[[str], None] | None = None):
        self._on_detect = on_detect
        self._threshold = threshold
        self._logger    = logger
        self._notify    = notify or (lambda _msg: None)
        self._queue: queue.Queue = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._running = False
        self._model = None
        self._ready = False

    def start(self) -> bool:
        """Load the model and spawn the inference thread. Returns True on success."""
        if self._running:
            return True

        model_name = get_active_model_name()
        model_path = find_model_path(model_name)

        if not model_path:
            phrase = get_wake_word_phrase()
            msg = (
                f"Custom wake word model for '{phrase}' ({model_name}) not found.\n"
                f"Falling back to Push-to-Talk (Ctrl+Space).\n\n"
                f"{get_training_instructions()}"
            )
            self._logger(msg)
            self._notify(f"Wake word model not found. Using Push-to-Talk (Ctrl+Space).")
            self._model = None
            return False

        try:
            from openwakeword.model import Model
            self._model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
        except Exception as e:
            self._logger(f"Wake word: could not load model '{model_path}' — {e}")
            self._notify("Wake word unavailable — using Push-to-Talk (Ctrl+Space).")
            self._model = None
            return False

        self._running = True
        self._ready = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="WakeWordThread")
        self._thread.start()
        self._logger(f"Wake word: listening for '{get_wake_word_phrase()}' via {model_path.name}.")
        return True

    def stop(self) -> None:
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        self._model = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def feed(self, frame_int16) -> None:
        """Called from the mic callback (real-time thread). Non-blocking queue push."""
        if not self._running:
            return
        try:
            data = frame_int16[:, 0].copy() if getattr(frame_int16, "ndim", 1) > 1 else frame_int16.copy()
            self._queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    def _loop(self) -> None:
        import numpy as np
        while self._running:
            try:
                frame = self._queue.get()
                if frame is None or not self._running:
                    break
                scores = self._model.predict(np.asarray(frame, dtype=np.int16))
                score = 0.0
                if isinstance(scores, dict):
                    target = get_active_model_name().lower()
                    for k, v in scores.items():
                        if target in k.lower():
                            score = max(score, float(v))
                    if score == 0.0 and scores:
                        score = max(float(v) for v in scores.values())
                if score >= self._threshold:
                    self._drain()
                    try:
                        self._on_detect()
                    except Exception as e:
                        self._logger(f"Wake word: on_detect error — {e}")
            except Exception as e:
                self._logger(f"Wake word: inference error — {e}")

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass
