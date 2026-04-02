"""
Local Notepad for J.A.R.V.I.S.
Stores notes, phone numbers, todo items, and quick reminders as a JSON file on disk.
"""
import json
import os
import threading
from datetime import datetime

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_notes.json")


class Notepad:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.notes: list[dict] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            self.notes = []
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self.notes = data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            self.notes = []

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.notes, f, indent=2, default=str)
        except IOError as e:
            print(f"[Notepad] Save failed: {e}")

    def add_note(self, content: str, category: str = "general") -> str:
        """Add a new note. Category can be: general, todo, contact, reminder, etc."""
        note = {
            "id": len(self.notes) + 1,
            "content": content,
            "category": category.lower(),
            "created": datetime.now().isoformat(),
            "done": False
        }
        with self._lock:
            self.notes.append(note)
            self._save()
        return f"Note #{note['id']} saved under '{category}': {content}"

    def list_notes(self, category: str = None) -> str:
        """List all notes, optionally filtered by category."""
        with self._lock:
            self._load()
            filtered = self.notes
            if category:
                filtered = [n for n in self.notes if n.get("category", "").lower() == category.lower()]

        if not filtered:
            label = f" in '{category}'" if category else ""
            return f"No notes found{label}."

        lines = []
        for n in filtered:
            status = "✅" if n.get("done") else "📝"
            cat = n.get("category", "general")
            created = ""
            try:
                dt = datetime.fromisoformat(n["created"])
                created = dt.strftime("%b %d, %H:%M")
            except (ValueError, KeyError):
                pass
            lines.append(f"{status} #{n['id']} [{cat}] ({created}) {n['content']}")
        return "\n".join(lines)

    def search_notes(self, query: str) -> str:
        """Search notes by keyword (case-insensitive)."""
        with self._lock:
            self._load()
            query_lower = query.lower()
            matches = [n for n in self.notes if query_lower in n.get("content", "").lower()
                       or query_lower in n.get("category", "").lower()]

        if not matches:
            return f"No notes matching '{query}'."

        lines = []
        for n in matches:
            status = "✅" if n.get("done") else "📝"
            lines.append(f"{status} #{n['id']} [{n.get('category', 'general')}] {n['content']}")
        return "\n".join(lines)

    def mark_done(self, note_id: int) -> str:
        """Mark a todo/note as done by its ID."""
        with self._lock:
            for n in self.notes:
                if n.get("id") == note_id:
                    n["done"] = True
                    self._save()
                    return f"Note #{note_id} marked as done: {n['content']}"
        return f"Note #{note_id} not found."

    def delete_note(self, note_id: int) -> str:
        """Delete a note by its ID."""
        with self._lock:
            for i, n in enumerate(self.notes):
                if n.get("id") == note_id:
                    removed = self.notes.pop(i)
                    self._save()
                    return f"Deleted note #{note_id}: {removed['content']}"
        return f"Note #{note_id} not found."
