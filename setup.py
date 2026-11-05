"""
Charlie Voice Assistant — one-time setup.

Installs the Python dependencies for THIS operating system only: the OS-specific
packages in requirements.txt carry `sys_platform` markers, so a macOS or Linux
user never pulls Windows-only libraries (and vice-versa). Then it fetches the
Playwright browsers needed for web automation (current-OS builds only).
"""
import platform
import subprocess
import sys
from pathlib import Path

OS = platform.system()  # "Windows" | "Darwin" | "Linux"
HERE = Path(__file__).resolve().parent

MIN_PY = (3, 11)        # hard floor: below this the syntax used here won't parse
MAX_PY = (3, 13)        # highest tested version


def _run(label: str, args: list[str]) -> None:
    print(f"\n▶ {label}")
    subprocess.run(args, check=True)


def _check_python() -> None:
    """Fail immediately and clearly rather than deep inside a pip resolver."""
    v = sys.version_info[:2]
    if v > MAX_PY:
        print(f"\n⚠️  Python {v[0]}.{v[1]} is newer than the "
              f"{MAX_PY[0]}.{MAX_PY[1]} this is tested on. Continuing — if a "
              f"package has no wheel yet, install Python "
              f"{MAX_PY[0]}.{MAX_PY[1]} and run setup with that.")
        return
    if v < MIN_PY:
        print(f"\n❌ Python {v[0]}.{v[1]} detected — Charlie needs at "
              f"least Python {MIN_PY[0]}.{MIN_PY[1]}.")
        print("   Install a supported version and run setup with it, e.g.:")
        print(f"     py -{MIN_PY[0]}.{MIN_PY[1]} setup.py        (Windows)")
        print(f"     python{MIN_PY[0]}.{MIN_PY[1]} setup.py      (macOS / Linux)")
        sys.exit(1)


def _check_assets() -> None:
    """The avatar's face is a shipped file; a truncated clone should say so."""
    face = HERE / "core" / "face_model.obj"
    if not face.exists() or face.stat().st_size < 4096:
        print(
            "\n⚠️  core/face_model.obj is missing or truncated — the avatar will "
            "fall back to the plain glowing core.\n"
            "    Re-clone the repository, or fetch that one file again."
        )


def main() -> None:
    print(f"⚙  Charlie setup — detected OS: {OS or 'unknown'}, "
          f"Python {sys.version_info[0]}.{sys.version_info[1]}")
    _check_python()

    # requirements.txt filters OS-specific extras by itself via pip markers.
    _run("Installing Python dependencies (OS-specific extras auto-filtered)…",
         [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    try:
        _run("Installing Playwright browsers (chromium + firefox)…",
             [sys.executable, "-m", "playwright", "install", "chromium", "firefox"])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"\n⚠️  Playwright browsers were not installed ({e}).")
        print("    Everything except browser automation works. Retry later with:")
        print(f'    {sys.executable} -m playwright install chromium firefox')

    _check_assets()

    # ── OS-specific post-install notes ────────────────────────────────────────
    if OS == "Windows":
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            candidates = [
                Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py",
                Path(sys.executable).parent / "pywin32_postinstall.py",
                Path(getattr(sys, "base_prefix", sys.prefix)) / "Scripts" / "pywin32_postinstall.py",
            ]
            postinstall = next((p for p in candidates if p.exists()), None)
            cmd = f'    "{sys.executable}" "{postinstall}" -install' if postinstall else '    pip install --force-reinstall pywin32'
            print(
                "\n⚠️  pywin32 did not register correctly — desktop-shortcut "
                "creation will use a slower fallback. To fix it, run:\n"
                f'    "{sys.executable}" -m pip install --force-reinstall pywin32\n'
                f'{cmd}'
            )
    elif OS == "Linux":
        print(
            "\nℹ️  Linux note — a few voice-controlled OS actions shell out to "
            "native tools. Install the ones you'll use via your package manager:\n"
            "    • volume      → pulseaudio-utils   (pactl)\n"
            "    • brightness  → brightnessctl\n"
            "    • reminders   → systemd (systemd-run) or 'at'\n"
            "    • open URLs   → xdg-utils          (xdg-open)"
        )
    elif OS == "Darwin":
        print(
            "\nℹ️  macOS note — volume, brightness and reminders use the built-in "
            "'osascript' / LaunchAgents, so no extra tools are required.\n"
            "    For Safari automation only: python -m playwright install webkit"
        )

    print("\n✅ Setup complete!")
    print("   1) Launch Charlie:  python main.py")
    print("   2) Configure your free Gemini API key in environment or on the setup screen.")
    print("   3) Use Push-To-Talk (Ctrl+Space) to speak anytime.")


if __name__ == "__main__":
    main()
