"""
plugins/calendar_notes.py — Local Calendar, Reminders, Notes, and To-Dos for Charlie.

Persists locally in memory/calendar_notes.json. Cross-platform.
Registers reversible operations with core/undo.py.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import undo
from core import confirm
from core.logger import get_logger

logger = get_logger("calendar_notes")

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_FILE = BASE_DIR / "memory" / "calendar_notes.json"


def _load_data() -> dict:
    STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORAGE_FILE.exists():
        return {"events": [], "notes": [], "todos": []}
    try:
        return json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"events": [], "notes": [], "todos": []}


def _save_data(data: dict) -> None:
    STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STORAGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


PLUGIN = {
    "name": "calendar_notes",
    "description": (
        "Manage local calendar events, reminders, notes, and to-do lists. "
        "Use this for scheduling events, taking notes, creating to-dos, or checking upcoming items."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: 'add_event', 'list_events', 'add_note', 'list_notes', 'add_todo', 'list_todos', 'complete_todo', 'delete_item', 'clear_all'",
            },
            "title": {"type": "STRING", "description": "Title of event, note, or to-do task"},
            "content": {"type": "STRING", "description": "Body of the note or details of event"},
            "datetime_str": {"type": "STRING", "description": "Date and time for event or due date for to-do"},
            "item_id": {"type": "STRING", "description": "ID of the item to complete or delete"},
            "category": {"type": "STRING", "description": "Category for delete_item: 'events', 'notes', or 'todos'"},
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip().lower()
    title = str(parameters.get("title", "")).strip()
    content = str(parameters.get("content", "")).strip()
    dt_str = str(parameters.get("datetime_str", "")).strip()
    item_id = str(parameters.get("item_id", "")).strip()
    category = str(parameters.get("category", "")).strip().lower()

    data = _load_data()

    if action == "add_event":
        if not title:
            return "Please provide an event title."
        evt_id = str(uuid.uuid4())[:8]
        event = {
            "id": evt_id,
            "title": title,
            "datetime": dt_str or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "details": content,
            "created_at": datetime.now().isoformat(),
        }
        data["events"].append(event)
        _save_data(data)

        # Register undo
        def _undo_add_event():
            d = _load_data()
            d["events"] = [e for e in d["events"] if e.get("id") != evt_id]
            _save_data(d)
            return f"Removed calendar event '{title}'."

        undo.push_undo(f"Add event '{title}'", _undo_add_event)
        msg = f"Scheduled event '{title}' for {event['datetime']}."
        if player:
            player.write_log(f"Charlie: {msg}")
        return msg

    elif action == "list_events":
        events = data.get("events", [])
        if not events:
            return "You have no upcoming scheduled events."
        lines = [f"• {e['title']} ({e['datetime']})" + (f": {e['details']}" if e.get("details") else "") for e in events]
        summary = f"You have {len(events)} event(s):\n" + "\n".join(lines[:10])
        if player:
            player.show_content("Upcoming Events", summary)
        return summary

    elif action == "add_note":
        if not title and not content:
            return "Please provide a note title or content."
        note_id = str(uuid.uuid4())[:8]
        note = {
            "id": note_id,
            "title": title or "Note",
            "content": content,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        data["notes"].append(note)
        _save_data(data)

        def _undo_add_note():
            d = _load_data()
            d["notes"] = [n for n in d["notes"] if n.get("id") != note_id]
            _save_data(d)
            return f"Deleted note '{note['title']}'."

        undo.push_undo(f"Add note '{note['title']}'", _undo_add_note)
        msg = f"Saved note '{note['title']}'."
        if player:
            player.write_log(f"Charlie: {msg}")
        return msg

    elif action == "list_notes":
        notes = data.get("notes", [])
        if not notes:
            return "You have no stored notes."
        lines = [f"[{n.get('id', '')}] {n['title']}: {n['content']}" for n in notes]
        summary = f"Stored Notes ({len(notes)}):\n" + "\n".join(lines)
        if player:
            player.show_content("Notes", summary)
        return summary

    elif action == "add_todo":
        if not title:
            return "Please provide a task description for the to-do."
        todo_id = str(uuid.uuid4())[:8]
        todo_item = {
            "id": todo_id,
            "task": title,
            "due": dt_str or "No due date",
            "done": False,
            "created_at": datetime.now().isoformat(),
        }
        data["todos"].append(todo_item)
        _save_data(data)

        def _undo_add_todo():
            d = _load_data()
            d["todos"] = [t for t in d["todos"] if t.get("id") != todo_id]
            _save_data(d)
            return f"Removed to-do '{title}'."

        undo.push_undo(f"Add to-do '{title}'", _undo_add_todo)
        msg = f"Added to-do: '{title}'."
        if player:
            player.write_log(f"Charlie: {msg}")
        return msg

    elif action == "list_todos":
        todos = data.get("todos", [])
        if not todos:
            return "Your to-do list is empty."
        lines = [f"[{'✓' if t.get('done') else ' '}] [{t.get('id')}] {t['task']} (Due: {t.get('due', 'N/A')})" for t in todos]
        summary = "To-Do List:\n" + "\n".join(lines)
        if player:
            player.show_content("To-Do List", summary)
        return summary

    elif action == "complete_todo":
        todos = data.get("todos", [])
        target = None
        for t in todos:
            if (item_id and t.get("id") == item_id) or (title and title.lower() in t.get("task", "").lower()):
                target = t
                break
        if not target:
            return f"Could not find matching to-do for '{item_id or title}'."
        target["done"] = True
        _save_data(data)

        def _undo_complete():
            d = _load_data()
            for x in d.get("todos", []):
                if x.get("id") == target["id"]:
                    x["done"] = False
            _save_data(d)
            return f"Marked to-do '{target['task']}' as incomplete."

        undo.push_undo(f"Complete to-do '{target['task']}'", _undo_complete)
        msg = f"Completed to-do: '{target['task']}'."
        if player:
            player.write_log(f"Charlie: {msg}")
        return msg

    elif action == "delete_item":
        if not item_id and not title:
            return "Please provide the item_id or title of the item to delete."
        cat = category if category in ("events", "notes", "todos") else "todos"
        items = data.get(cat, [])
        removed = None
        new_items = []
        for x in items:
            ident = x.get("id")
            label = x.get("title") or x.get("task") or ""
            if (item_id and ident == item_id) or (title and title.lower() in label.lower()):
                removed = x
            else:
                new_items.append(x)
        if not removed:
            return f"Could not find item to delete in {cat}."
        data[cat] = new_items
        _save_data(data)

        def _undo_delete():
            d = _load_data()
            d.setdefault(cat, []).append(removed)
            _save_data(d)
            return f"Restored {cat} item."

        undo.push_undo(f"Delete {cat} item", _undo_delete)
        return f"Deleted item from {cat}."

    elif action == "clear_all":
        # Destructive -> gate through confirm
        def _execute_clear():
            _save_data({"events": [], "notes": [], "todos": []})
            return "Cleared all calendar events, notes, and to-dos."

        return confirm.request(
            key="calendar_clear_all",
            title="Clear All Calendar & Notes Data",
            detail="This will permanently delete all stored events, notes, and to-do items.",
            run=_execute_clear,
        )

    return f"Unknown action '{action}' for calendar_notes."
