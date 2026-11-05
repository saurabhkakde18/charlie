# SYSTEM AUDIT: Mark-LV to Charlie Transformation

> **Audit Date:** 2026-11-05  
> **Target OS:** Windows 11 (tested on Python 3.12)  
> **Source Project:** Mark-LV / Mark-LVI (by FatihMakes)  
> **Scope:** `main.py`, `ui.py`, `setup.py`, `requirements.txt`, `core/*`, `actions/*`, `memory/*`, `plugins/_template.py`, `core/prompt.txt`, `dashboard/*`.

---

## 1. Architecture Map

```
                             ┌──────────────────────────────────┐
                             │       PyQt6 HUD (ui.py)          │
                             │  - Main Window & Canvas          │
                             │  - Holographic Avatar (3D OBJ)   │
                             │  - Waveform & Metric Monitors    │
                             │  - Content / Review / Quiz Board │
                             │  - Quick Controls & Drawers      │
                             └──────────────┬───────────────────┘
                                            │ Signals / Callbacks
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           JarvisLive Controller (main.py)                         │
│  - Asyncio Run Loop on Dedicated Background Worker Thread                         │
│  - Push-To-Talk Watcher (core/hotkey.py) & Wake Word Thread (core/wake_word.py)   │
│  - Stall Watchdog, Reconnection Manager & Resumption Handler Cache                │
└──────────────┬────────────────────────────┬────────────────────────────┬──────────┘
               │                            │                            │
               ▼                            ▼                            ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌──────────────────────┐
│  Audio In/Out Pipeline    │ │     Gemini Live & LLM     │ │   Tool & Extensibility │
│ - sounddevice InputStream │ │ - google-genai Client     │ │ - core/action_loader.py│
│ - RawOutputStream (24kHz) │ │ - WebSocket Live Session  │ │ - core/plugin_loader.py│
│ - EchoGuard (core/echo.py)│ │ - Model Ladder (gemini.py)│ │ - actions/*.py         │
│ - VisemeStream (viseme.py)│ │ - Prompt Renderer         │ │ - plugins/*.py         │
└───────────────────────────┘ └───────────────────────────┘ └──────────┬───────────┘
                                                                       │
                                            ┌──────────────────────────┴───────────┐
                                            │ Safety Gates & Long-Term Memory      │
                                            │ - UI Confirmation Gate (confirm.py)  │
                                            │ - 10-Depth Undo Stack (undo.py)      │
                                            │ - Memory Manager (memory_manager.py) │
                                            │ - Remote Dashboard (dashboard/server)│
                                            └──────────────────────────────────────┘
```

---

## 2. End-to-End Data Flow

```
[User Speaks into Microphone]
           │
           ▼
[sounddevice.InputStream @ 16 kHz int16]
           │
           ▼
[main.py `_listen_audio` callback]
   ├── 1. Wake-Word Gate: If asleep, feed `WakeWordDetector` thread -> drop frame
   ├── 2. Barge-in / Speaking Lock: If assistant speaking -> drop frame
   ├── 3. EchoGuard (`core/echo.py`): Drop frames matching echo tail from speaker
   ├── 4. Push-To-Talk Gate (`core/hotkey.py`): If PTT active & chord released -> drop frame
   └── 5. Valid speech: `out_queue.put_nowait({"data": pcm, "mime_type": "audio/pcm"})`
           │
           ▼
[main.py `_send_realtime`]
   └── `session.send_realtime_input(audio=types.Blob(data=pcm, mime_type="audio/pcm"))`
           │
           ▼  (WebSocket / Gemini Live Server)
[main.py `_receive_audio`]
   ├── 1. `response.data` (Audio chunks @ 24 kHz) -> Slice into 50 ms -> `audio_in_queue`
   ├── 2. `response.server_content.output_transcription` -> `_visemes.feed_text()` -> UI log
   ├── 3. `response.server_content.turn_complete` -> Flush exchange log, trigger proactive checks
   └── 4. `response.tool_call`
           │
           ▼
[main.py `_execute_tool`]
   ├── Inline tools: `screen_process`, `system_status`, `save_memory`, `recall_memory`, `undo`
   ├── Action Registry (`core/action_loader.py`): e.g., `web_search`, `file_controller`
   └── Plugin Registry (`core/plugin_loader.py`): User plugins in `plugins/*.py`
           │
           ▼
[Safety Checks]
   ├── Irreversible action? -> Intercept with `core/confirm.py` UI banner (park execution)
   └── Reversible action?   -> Execute and push inverse lambda to `core/undo.py`
           │
           ▼
[Tool Result String -> `session.send_tool_response`]
           │
           ▼ (Gemini generates spoken response)
[main.py `_play_audio`]
   ├── Dequeue batch from `audio_in_queue` (up to ~200 ms)
   ├── Spectral formant analysis (`_pcm_visemes`) + text visemes -> `ui.push_visemes()`
   ├── Register output with `EchoGuard` for adaptive cancellation
   └── Hand batch to `sounddevice.RawOutputStream.write()` -> [Speakers / Headphones]
```

---

## 3. GitHub Issues & Known Community Flaws

Cross-checked against discussions and open issues on `FatihMakes/Mark-LV` / `Mark-LVI`:
1. **Startup Reconnect & Crash Loops (Issue #160):** Unhandled exceptions in `TaskGroup` child tasks bubble up and crash `asyncio.run()`, killing the background runner.
2. **Audio Stream Device Mismatches:** Headphone/USB microphone unplugging causes immediate unhandled exceptions in `sounddevice.InputStream` callbacks.
3. **Vision WebSocket 1011 Keepalive Timeouts:** Heavy base64 screen/camera frames sent over the WebSocket trigger keepalive ping timeouts on slow connections.
4. **Missing Python Wheel Conflicts:** Pip fails with `ResolutionImpossible` or fails to build C-extensions on fresh Python 3.12+ installations without pinned wheels.
5. **Rate-Limit Lockouts (429):** One-shot sidecar calls exhaust free Gemini text quotas, leaving the assistant unresponsive because the fallback ladder targets non-existent models.

---

## 4. Ranked Findings

### P0 — Crash / Data Loss / Security Flaws

| ID | Category | Component | Description & Root Cause | Impact |
|---|---|---|---|---|
| **P0-1** | **Security / Crash** | `main.py` (L328), `ui.py` (L7161), `core/gemini.py` | **Plaintext API Key & Crash on Missing File:** `_get_api_key()` reads `config/api_keys.json` with bare `open()`. If missing, crashes with `FileNotFoundError`. Ignores `GEMINI_API_KEY` environment variable and OS keyring. Plaintext JSON on disk poses credential leak risk. | App crash on launch; credential exposure. |
| **P0-2** | **Security** | `actions/code_helper.py` (L211, L247), `actions/dev_agent.py` (L265, L321) | **Arbitrary Code & Shell Execution Without Confirmation:** `_build()` in `code_helper.py` writes code and executes it via `subprocess.run` up to 3 times automatically. `dev_agent.py` executes shell commands and `pip install` without prompting the user. | Remote/Prompt-injection Code Execution; system compromise. |
| **P0-3** | **Security** | `actions/file_controller.py` (L269), `actions/send_message.py` (L347) | **Destructive Actions Bypass Confirmation Gate:** `delete_file` sends files to Trash without user confirmation through `core/confirm.py`. `send_message` dispatches WhatsApp/Telegram messages on a background thread without a UI-approved token. | Unauthorized message transmission and file loss. |
| **P0-4** | **Bug / Denial of Service** | `actions/file_controller.py` (L97-104) | **Windows Multi-Drive Lockdown:** `_SAFE_ROOTS` is hardcoded to `[Path.home()]`. On Windows, files located on any drive other than `C:\Users\<user>` (such as `D:\`) are rejected with `Access denied`. | Cannot manage or manipulate files outside user home directory. |
| **P0-5** | **Security** | `dashboard/server.py` (L1152) | **Path Traversal in Remote File Download:** `download_file` sanitizes `filename` with `re.sub(r'[/\\]', '', filename)`. If `filename=".."`, it resolves to `self._uploads_dir.parent`, permitting directory traversal. | Unauthorized file reading on the host system. |
| **P0-6** | **Crash Risk** | `main.py` (L1816-1819, L1640-1643) | **Unhandled Exception in TaskGroup:** Any network glitch or audio disconnect in `_receive_audio` or `_listen_audio` raises uncaught inside `asyncio.TaskGroup()`, crashing the entire thread. | Instant session death without recovery. |
| **P0-7** | **Crash Risk** | Global / `main.py` / Windows Console | **UnicodeEncodeError / UnicodeDecodeError in Non-Latin Locales:** Standard Windows console codepages (e.g. cp1252, cp932) crash when printing non-Latin characters or emoji. Subprocess executions in actions omit `encoding='utf-8', errors='replace'`. | Crash when speaking Hindi, Arabic, Turkish, Japanese, etc. |

---

### P1 — Broken Features & Operational Reliability

| ID | Category | Component | Description & Root Cause | Impact |
|---|---|---|---|---|
| **P1-1** | **Broken Feature** | `core/gemini.py` (L157-173) | **Fictitious Models on Gemini Ladder:** `_LADDERS` specifies non-existent models (`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.6-flash`). Calls return 404/400 errors, causing a 6-hour `_GONE_SECONDS` cooldown and blocking sidecar tasks. | Document analysis, web grounding, and code features break under load. |
| **P1-2** | **Broken Feature** | `actions/web_search.py`, `actions/youtube_video.py`, `actions/flight_finder.py` | **Missing HTTP Network Timeouts & Exponential Backoff:** Network calls use `requests.get` without explicit timeouts or retry backoffs, causing threads to hang indefinitely on flaky connections. | Silent freezes and unresponsive assistant turns. |
| **P1-3** | **Broken Feature** | `main.py` (L2588-2598) | **Premature Session Resumption Eviction:** Reconnection logic drops stored `_resume_handle` when receiving transient argument errors, causing the conversation context to reset unnecessarily. | Forgets current conversation on momentary network drops. |
| **P1-4** | **Install Flaw** | `setup.py` (L99) | **Virtualenv pywin32 Path Bug:** Assumes `sys.executable` parent has a `Scripts/` subdirectory (`Path(sys.executable).parent / "Scripts"`). In a virtualenv, this resolves to `<venv>/Scripts/Scripts`, which fails. | Setup fails on fresh virtual environments on Windows. |
| **P1-5** | **Broken Feature** | Entire Codebase | **Hardcoded "JARVIS" Branding & English Strings:** System prompt (`core/prompt.txt`), tool descriptions, acknowledgments, error messages, and notification scripts hardcode "JARVIS" and English phrasing. | Inability to operate naturally in other languages or rebrand. |
| **P1-6** | **Missing Feature** | Startup Flow (`main.py`, `ui.py`) | **No Startup Self-Check:** The application attempts immediate connection without validating prerequisites (API key, microphone, speakers, `yt-dlp`, wake word). | Cryptic error messages or silent failures on missing hardware/keys. |
| **P1-7** | **Broken Feature** | `actions/reminder.py` (L31, L56) | **Missing Dependency (`plyer`) & Hardcoded Paths:** Relies on unpinned `plyer` library, writes to `~/.jarvis/reminders/`, and hardcodes English notification strings. | Reminders fail or display incorrect titles. |

---

### P2 — Performance, Polish & Extensibility

| ID | Category | Component | Description & Root Cause | Impact |
|---|---|---|---|---|
| **P2-1** | **Performance** | `main.py`, `ui.py` | **Slow Cold Startup (> 3 seconds):** Top-level eager imports of `sounddevice`, `google.genai`, `cv2`, `mss`, `playwright`, `numpy`, and 3D OBJ mesh parsing delay HUD appearance. | Poor user experience on launch. |
| **P2-2** | **Performance** | `ui.py` (L4678), `main.py` (L1536) | **Idle CPU Drain:** Timers in `ui.py` poll WMI and system metrics every 1-2 seconds. Mic callback continuously evaluates frames while asleep instead of using lightweight idle gating. | High laptop battery and CPU utilization when idle. |
| **P2-3** | **Performance** | `main.py` (`TOOL_DECLARATIONS`) | **Overly Verbose Tool Declarations:** Inline tool descriptions contain lengthy explanations, bloating system instruction token count and adding latency to the Live connection. | Slower response generation from Gemini Live. |
| **P2-4** | **Observability** | `main.py`, `actions/*` | **Fragmented Console-Only Logging:** Logs are printed to `stdout` with inconsistent tags. No rotating log files in `logs/` directory. | Difficult troubleshooting and lost error diagnostics. |
| **P2-5** | **UX / Wake Word** | `core/wake_word.py` (L28) | **Hardcoded Wake Word Model:** Fixed to `hey_jarvis`. No configuration or clear user guidance on custom models or fallback to push-to-talk. | Wake word unusable for "Charlie" without clear instructions. |

---

## 5. Phase-by-Phase Remediation Roadmap

1. **Phase 1 (Fix Bugs & Hardening):**
   - Implement secure key retrieval (ENV `GEMINI_API_KEY` -> OS `keyring` -> `config/api_keys.json` fallback).
   - Implement rotating file logger in `logs/charlie.log`.
   - Wrap audio threads, tool dispatchers, and websocket receive loops in resilient `try/except` handlers.
   - Force UTF-8 encoding across all file operations and console streams.
   - Add timeouts and exponential backoff retries to network calls.
   - Implement comprehensive startup self-check (validating API key, mic, speaker, `yt-dlp`).
   - Fix `setup.py` and pin dependencies in `requirements.txt`.
   - Fix `_is_safe_path` multi-drive support on Windows and path traversal in `dashboard/server.py`.

2. **Phase 2 (Rebranding to "Charlie"):**
   - Replace user-facing "Jarvis" strings in UI, prompts, logs, and notifications.
   - Make assistant name configurable in `config/api_keys.json` (default: "Charlie").
   - Update `core/prompt.txt` to introduce as Charlie (concise, natural, friendly).
   - Graceful wake-word fallback to push-to-talk (Ctrl+Space) with actionable instructions for training custom "Hey Charlie" models.

3. **Phase 3 (Multilingual & i18n):**
   - Implement lightweight i18n module for system messages, tool errors, and UI strings.
   - Dynamic language detection storing preferred language in memory (`category="identity", key="language"`).
   - Clean viseme degradation for non-Latin scripts (Arabic, Hindi, Chinese, Japanese, Korean, Marathi, Turkish).
   - Validation test suite across English, Hindi, Marathi, Turkish, Arabic, Spanish, Japanese.

4. **Phase 4 (Extensible Skill System):**
   - Build `create_skill` meta-tool with explicit UI approval gate before loading plugins.
   - Integrate `core/confirm.py` UI token confirmation on all destructive/shell/install actions.
   - Implement 9 core skills (Calendar/Notes, Email draft, Translation, Safe shell, Code helper, Media/Volume control, Web search/summary, Screenshot describer, File downloader).
   - Compact tool declarations to preserve Live API speed.

5. **Phase 5 (Reliability & Speed):**
   - Verify Gemini model ladder with real current models (`gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`).
   - Session resumption stability.
   - Defer heavy imports to achieve < 3.0s startup to HUD.
   - Reduce idle CPU usage.

6. **Phase 6 (Tests, Documentation & Attribution):**
   - Comprehensive pytest suite.
   - Rewrite `README.md` for Charlie.
   - Maintain CC BY-NC 4.0 license with attribution to FatihMakes / Mark-LV.

---
*End of Audit Report.*
