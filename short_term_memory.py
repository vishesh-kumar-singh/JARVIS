"""
Persistent Short-Term Memory for J.A.R.V.I.S.
Saves recent conversation context (tool calls, model responses, system events) to a JSON file.
On restart after a crash, this context is loaded and injected into the system prompt
so J.A.R.V.I.S. retains awareness of the recent conversation.
"""
import json
import os
import threading
from datetime import datetime, timedelta

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversation_context.json")
MAX_ENTRIES = 50
MAX_AGE_HOURS = 6


class ShortTermMemory:
    def __init__(self, path: str = DEFAULT_PATH, max_entries: int = MAX_ENTRIES, max_age_hours: int = MAX_AGE_HOURS):
        self.path = path
        self.max_entries = max_entries
        self.max_age_hours = max_age_hours
        self._lock = threading.Lock()
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        """Load existing entries from disk, pruning stale ones."""
        if not os.path.exists(self.path):
            self.entries = []
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.entries = data
            else:
                self.entries = []
        except (json.JSONDecodeError, IOError):
            self.entries = []
        self._prune()

    def _save(self):
        """Persist entries to disk (called under lock)."""
        try:
            with open(self.path, "w") as f:
                json.dump(self.entries, f, indent=2, default=str)
        except IOError as e:
            print(f"[ShortTermMemory] Failed to save: {e}")

    def _prune(self):
        """Remove entries older than max_age_hours and trim to max_entries."""
        cutoff = (datetime.now() - timedelta(hours=self.max_age_hours)).isoformat()
        self.entries = [e for e in self.entries if e.get("timestamp", "") >= cutoff]
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def add(self, role: str, content: str):
        """
        Add a conversation entry.
        
        role: one of "tool", "assistant", "system_event", "user_speech"
        content: the text content of the entry
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content[:500]  # Truncate to avoid bloat
        }
        with self._lock:
            self.entries.append(entry)
            self._prune()
            self._save()

    def get_context(self, max_entries: int = 20) -> str:
        """
        Get a formatted string of recent conversation context 
        suitable for injection into a system prompt.
        Returns empty string if no entries exist.
        """
        with self._lock:
            self._prune()
            recent = self.entries[-max_entries:] if self.entries else []

        if not recent:
            return ""

        lines = []
        for e in recent:
            ts = e.get("timestamp", "")
            # Format: just time portion for readability
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime("%H:%M")
            except (ValueError, TypeError):
                time_str = "??:??"
            
            role = e.get("role", "unknown")
            content = e.get("content", "")

            if role == "tool":
                lines.append(f"  [{time_str}] 🔧 {content}")
            elif role == "assistant":
                lines.append(f"  [{time_str}] 🤖 You said: {content}")
            elif role == "system_event":
                lines.append(f"  [{time_str}] ⚡ System: {content}")
            elif role == "user_speech":
                lines.append(f"  [{time_str}] 🗣️ User: {content}")
            else:
                lines.append(f"  [{time_str}] {content}")

        return "\n".join(lines)

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self.entries = []
            self._save()
