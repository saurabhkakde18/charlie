# ⚡ Charlie — Real-Time Multilingual Personal AI Voice Assistant

> **Charlie** is an autonomous, cross-platform personal AI voice assistant with a real-time PyQt6 HUD, native audio streaming via Google Gemini Live, an extensible skill system, and strict user confirmation security gates.
> 
> *Built upon the architecture of **Mark-LV / Mark 56** by [FatihMakes](https://www.youtube.com/@FatihMakes) under the [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) license.*

---

## 🌟 Highlights

- 🗣️ **Gemini Live 24kHz Streaming Audio**: Bidirectional, ultra-low latency voice conversation powered by Gemini 2.5 Flash Live.
- 🧑‍🎤 **Holographic 3D Avatar HUD**: Real facial geometry (MediaPipe 468 vertices canonical mesh) rendered in software Qt without GPU overhead.
- 👄 **Formant & Viseme Lip-Sync**: Physics-based mouth shapes (~50/s) with robust, clean degradation on non-Latin scripts (Hindi, Marathi, Arabic, Japanese, Chinese, etc.).
- 🌍 **True Multilingual Intelligence**: Automatically detects the user's language, responds in kind, switches mid-sentence when prompted, and supports explicit overrides ("speak Spanish", "speak Hindi").
- ⏱️ **Sub-3s Fast Startup**: Deferral of heavy dependencies, credential caching, and optimized module imports deliver a usable HUD in < 2.7s.
- 🛡️ **Zero-Trust Confirmation Gate (`core/confirm.py`)**: Destructive or executable actions (shell commands outside whitelist, dangerous file downloads, shutdowns, deletions) require explicit UI button approval; the model cannot confirm for itself.
- 🧩 **"Do Anything" Extensible Skill System**: Drop a `.py` file into `plugins/` to add skills instantly, or ask Charlie to write one for you using the `create_skill` meta-tool (with mandatory code review and UI approval).
- 🔐 **Hardened Security & Privacy**: API keys stored in environment variables (`GEMINI_API_KEY`) or OS Keyring (Windows Credential Manager / macOS Keychain / Linux SecretService); no plaintext keys required.
- 🪜 **Resilient Model Ladder**: Automatic fallback ladder across real Google Gemini models (`gemini-2.5-flash` → `gemini-2.5-pro` → `gemini-2.0-flash` → `gemini-2.5-flash-lite`) with exponential backoff and cooldown tracking on 429/503 errors.

---

## 🛠️ System Requirements

- **Operating Systems**: Windows 10/11, macOS 12+, or modern Linux (Ubuntu 22.04+, Fedora 38+).
- **Python**: 3.11, 3.12, or 3.13.
- **Hardware**: Working microphone and audio output (speakers / headphones).
- **API Key**: A free or paid Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
- **Optional Tools**:
  - `yt-dlp` and `ffmpeg` (for video and audio stream playback).
  - `openwakeword` + ONNX runtime (for hands-free wake word detection).

---

## 🚀 Quick Start & Installation

### 1. Clone & Set Up Virtual Environment

#### Windows (PowerShell):
```powershell
git clone https://github.com/your-username/Charlie.git
cd Charlie

python -m venv .venv
.\.venv\Scripts\activate
```

#### macOS / Linux (Bash/Zsh):
```bash
git clone https://github.com/your-username/Charlie.git
cd Charlie

python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

You can run the interactive setup self-check or install directly with `pip`:

```bash
# Automated install and configuration check:
python setup.py

# Or direct pip install:
pip install -r requirements.txt
```

---

## 🔑 Configuring Your Gemini API Key

Charlie checks for your API key in the following priority order:

1. **Environment Variable (Recommended & Most Secure)**:
   - **Windows (PowerShell)**:
     ```powershell
     [System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'your_api_key_here', 'User')
     # Or for current session:
     $env:GEMINI_API_KEY="your_api_key_here"
     ```
   - **macOS / Linux**:
     ```bash
     export GEMINI_API_KEY="your_api_key_here"
     # Add to ~/.bashrc or ~/.zshrc for persistence
     ```

2. **OS Keyring**:
   Charlie supports native OS credential storage (Windows Credential Manager, macOS Keychain, Linux SecretService):
   ```bash
   python -c "import keyring; keyring.set_password('charlie', 'gemini_api_key', 'your_api_key_here')"
   ```

3. **Fallback Config File**:
   If neither environment variable nor OS keyring is set, Charlie looks for `config/api_keys.json` (gitignored):
   ```json
   {
     "gemini_api_key": "your_api_key_here"
   }
   ```

---

## 🎙️ Wake Word & Push-To-Talk

- **Push-To-Talk (Ctrl+Space)**:
  - Hold **Ctrl+Space** to talk. Charlie opens the microphone immediately and processes your voice upon release.
  - On Windows, this is a global shortcut. On macOS/Linux, it works while the HUD has window focus.
- **Wake Word ("Hey Charlie")**:
  - By default, Charlie uses Push-To-Talk for maximum reliability and zero background CPU streaming.
  - If you have an `openwakeword` model for "hey_jarvis", Charlie will use it.
  - **Adding a custom "Hey Charlie" wake word**:
    1. Train a custom `.onnx` model using the official [openWakeWord Colab Notebook](https://github.com/dscripka/openWakeWord).
    2. Save your trained model file as `hey_charlie.onnx` into `config/wake_words/`.
    3. Update `"wake_word": "hey_charlie"` in `config/api_keys.json`.
    4. Charlie never fakes wake word detection; if the model file is not found, it falls back cleanly to Push-to-Talk.

---

## 🧰 Built-in Skills & Capabilities

Charlie comes pre-equipped with powerful skills in `plugins/` and `actions/`:

| Skill | Module | Description | Undo / Confirm Gate |
|---|---|---|---|
| **Calendar & Reminders** | `plugins/calendar_notes.py` | Local appointments, reminders, notes, and task lists. | Undoable; `clear_all` requires UI confirmation |
| **Email Draft** | `plugins/email_draft.py` | Composes draft in default email client with recipient, subject, and body. | Safe (requires user to hit send in client) |
| **Live Translator** | `plugins/translator.py` | Bidirectional text and spoken translation via Gemini across 50+ languages. | Safe read-only |
| **Safe Shell** | `plugins/safe_shell.py` | Executes safe terminal commands (`dir`, `ping`, `git status`). | Whitelisted; non-whitelisted commands require UI token |
| **Code Project Helper** | `plugins/code_project_helper.py` | Opens projects in VS Code/Cursor/PyCharm, runs `pytest`/`npm test`, parses errors. | Safe read-only test executor |
| **Media Control** | `plugins/media_control.py` | Play, pause, next, previous track, mute, and volume up/down. | Volume changes undoable |
| **Web Summarizer** | `plugins/web_summarizer.py` | Fetches webpage, strips scripts/styles, protects against prompt injection, summarizes content. | Safe read-only |
| **Screen Description** | `plugins/screen_describe.py` | Takes screenshot of primary display and uses Gemini multimodal vision to describe what's on screen. | Safe read-only |
| **File Downloader** | `plugins/file_downloader.py` | Downloads files with progress logging and SHA-256 verification. | Undoable (deletes file); `.exe`/scripts require UI confirmation |
| **Skill Creator** | `actions/create_skill.py` | Meta-tool: drafts new plugin code in `plugins/_pending.py`, shows preview in HUD. | Mandatory UI confirmation button approval |

---

## 🧩 Writing Your Own Plugin

Adding a plugin to Charlie requires just **one Python file** in `plugins/<skill_name>.py`:

```python
"""
plugins/my_skill.py — Example Charlie Plugin
"""
from __future__ import annotations

PLUGIN = {
    "name": "greet_user",
    "description": "Greets the user with a custom message.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Name of the person"}
        },
        "required": ["name"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    name = parameters.get("name", "friend")
    if player:
        player.write_log(f"Greeting {name}")
    return f"Hello {name}, wonderful to assist you today!"
```

### Golden Rules for Plugins:
1. **Never create Qt widgets in plugins**: Always use thread-safe `player` methods (`player.write_log`, `player.show_content`, etc.).
2. **Never raise**: Catch all exceptions and return a descriptive sentence.
3. **Use `core.confirm` for destructive operations**:
   ```python
   from core import confirm
   return confirm.request(
       key="delete_file",
       title="Delete File",
       detail=f"Permanently delete {filepath}?",
       run=lambda: os.remove(filepath) or f"Deleted {filepath}"
   )
   ```
4. **Register undo callbacks where reversible**:
   ```python
   from memory.undo_stack import register_undo
   register_undo("description", lambda: restore_action())
   ```

---

## 🧪 Running Tests

Charlie includes a comprehensive `pytest` test suite covering memory management, the undo stack, confirmation gates, the model fallback ladder, plugin discovery, i18n fallbacks, and action name fuzzy matching:

```bash
pytest tests/ -v
```

All 13 test suites execute in < 0.5s.

---

## ⚠️ Known Limitations

1. **Internet Connection**: Gemini Live API requires an active internet connection to communicate with Google's servers.
2. **Audio Input Device**: Some virtual audio drivers (Voicemeeter, OBS Virtual Audio) may need to be explicitly selected in settings if they do not report 16kHz/24kHz capture capabilities.
3. **Headless Linux**: On Linux headless servers, PyQt6 requires an X11 display or virtual framebuffer (`xvfb-run python main.py`).
4. **Push-To-Talk on Wayland**: Global hotkey capture on Linux Wayland is restricted by OS security policies; use X11 or keep HUD focused for `Ctrl+Space`.

---

## 📄 License & Attribution

- **Charlie Personal Assistant**: Open-source modifications, rebranding, and skill additions by Anthropic & Google DeepMind engineering contributor.
- **Original Project**: Based on **MARK 56 / Mark-LV** by **FatihMakes** ([YouTube @FatihMakes](https://www.youtube.com/@FatihMakes), [Instagram @fatihmakes](https://www.instagram.com/fatihmakes)).
- **License**: Licensed under the **[Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)**.
  - *Personal and non-commercial use only.*
  - *Any redistributions or derivatives must retain attribution to the original author.*

---

## 🚀 Running Charlie

Once installed and configured, launch Charlie with:

```bash
python main.py
```

Enjoy your personal voice assistant!
