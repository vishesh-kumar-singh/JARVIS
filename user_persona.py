import json
import os
import threading
from datetime import datetime
from google import genai

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_persona.json")

REFLECTION_MODEL = "gemini-3.1-flash-lite-preview"

DEFAULT_PERSONA = {
    "last_updated": None,
    "personal": {
        "name": None,
        "nicknames": [],
        "occupation": None,
        "institution": None,
        "location": None,
    },
    "communication_style": {
        "preferred_tone": None,
        "humor_level": None,
        "language_preferences": [],
    },
    "interests": {
        "music": [],
        "movies_shows": [],
        "hobbies": [],
        "academic_topics": [],
        "tech_interests": [],
    },
    "work_study_habits": {
        "typical_schedule": None,
        "current_courses": [],
        "current_projects": [],
        "stress_indicators": [],
    },
    "preferences": {
        "email_style": None,
        "browser": None,
        "food": [],
        "pet_peeves": [],
        "other": [],
    },
    "behavioral_patterns": {
        "morning_routine": None,
        "evening_routine": None,
        "common_requests": [],
        "mood_patterns": [],
    },
    "raw_observations": []
}

REFLECTION_PROMPT = """You are analyzing a conversation log between a user and their AI assistant (J.A.R.V.I.S.).
Your job is to extract NEW insights about the user's personality, preferences, habits, and interests.

Here is the EXISTING user profile (what we already know):
```json
{existing_persona}
```

Here is the RECENT conversation log:
```
{conversation_log}
```

Analyze the conversation and output a JSON object with ONLY the fields that need to be UPDATED or ADDED.
Rules:
1. Do NOT repeat information already in the existing profile unless you are correcting it.
2. For list fields (like interests.music), output the NEW items to ADD, not the full list.
3. For string fields, only include them if you have a NEW or CORRECTED value.
4. If you learn nothing new, output an empty JSON object: {{}}
5. Include a "raw_observations" list with any interesting free-form insights.
6. Be specific and factual. Don't speculate wildly.

Output ONLY valid JSON, no markdown code fences, no explanation."""


class UserPersona:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.persona: dict = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            self.persona = json.loads(json.dumps(DEFAULT_PERSONA))
            return
        try:
            with open(self.path, "r") as f:
                self.persona = json.load(f)
        except (json.JSONDecodeError, IOError):
            self.persona = json.loads(json.dumps(DEFAULT_PERSONA))

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.persona, f, indent=2, default=str)
        except IOError as e:
            print(f"Save failed: {e}")

    def _deep_merge(self, base: dict, patch: dict):
        for key, value in patch.items():
            if key not in base:
                base[key] = value
            elif isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            elif isinstance(base[key], list) and isinstance(value, list):
                for item in value:
                    if item not in base[key]:
                        base[key].append(item)
            elif value is not None:
                base[key] = value

    def reflect(self, conversation_log: str) -> str:
        if not conversation_log or len(conversation_log.strip()) < 50:
            return "Not enough conversation data to reflect on."

        prompt = REFLECTION_PROMPT.format(
            existing_persona=json.dumps(self.persona, indent=2, default=str),
            conversation_log=conversation_log
        )

        try:
            client = genai.Client()
            response = client.models.generate_content(
                model=REFLECTION_MODEL,
                contents=prompt,
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()
            if raw_text.startswith("json"):
                raw_text = raw_text[4:].strip()

            patch = json.loads(raw_text)

            if not patch or not isinstance(patch, dict):
                return "No new insights found."

            with self._lock:
                self._deep_merge(self.persona, patch)
                self.persona["last_updated"] = datetime.now().isoformat()
                self._save()

            learned = []
            for key, value in patch.items():
                if key == "raw_observations" and isinstance(value, list):
                    for obs in value:
                        learned.append(f"  • {obs}")
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if v:
                            learned.append(f"  • {key}.{k}: {v}")
                elif value:
                    learned.append(f"  • {key}: {value}")

            if learned:
                summary = "Learned:\n" + "\n".join(learned)
            else:
                summary = "No new insights."

            print(f"[Persona Reflection] {summary}", file=__import__('sys').stderr)
            return summary

        except json.JSONDecodeError as e:
            print(f"[Persona Reflection] JSON parse error: {e}", file=__import__('sys').stderr)
            return f"Reflection failed (bad JSON): {e}"
        except Exception as e:
            print(f"[Persona Reflection] Error: {e}", file=__import__('sys').stderr)
            return f"Reflection failed: {e}"

    def get_prompt_block(self) -> str:
        with self._lock:
            self._load()

        has_data = False
        for section_key, section_val in self.persona.items():
            if section_key in ("last_updated",):
                continue
            if isinstance(section_val, dict):
                for v in section_val.values():
                    if v and v != [] and v is not None:
                        has_data = True
                        break
            elif isinstance(section_val, list) and section_val:
                has_data = True
            if has_data:
                break

        if not has_data:
            return ""

        lines = ["\nIMPORTANT - What You Know About The User (Learned Profile):"]
        lines.append("Use this profile to personalize your responses. Anticipate preferences when possible.")

        for section_key, section_val in self.persona.items():
            if section_key in ("last_updated", "raw_observations"):
                continue
            if isinstance(section_val, dict):
                section_lines = []
                for k, v in section_val.items():
                    if v and v != [] and v is not None:
                        if isinstance(v, list):
                            section_lines.append(f"  - {k.replace('_', ' ').title()}: {', '.join(str(i) for i in v)}")
                        else:
                            section_lines.append(f"  - {k.replace('_', ' ').title()}: {v}")
                if section_lines:
                    lines.append(f"\n{section_key.replace('_', ' ').title()}:")
                    lines.extend(section_lines)

        observations = self.persona.get("raw_observations", [])
        if observations:
            lines.append("\nOther Observations:")
            for obs in observations[-10:]:
                lines.append(f"  - {obs}")

        return "\n".join(lines)
