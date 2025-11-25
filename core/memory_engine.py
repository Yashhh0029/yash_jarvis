# core/memory_engine.py
import json
import os
import tempfile
import random
from core.speech_engine import speak

# Module-level singleton holder
_INSTANCE = None


class JarvisMemory:
    """Stores Jarvis’s emotional context, facts, and conversational memory.

    This class uses a singleton pattern (via __new__) so repeated calls to
    JarvisMemory() across modules return the same shared instance. This
    prevents repeated initialization prints and duplicated loads.
    """

    def __new__(cls, *args, **kwargs):
        global _INSTANCE
        if _INSTANCE is None:
            _INSTANCE = super(JarvisMemory, cls).__new__(cls)
        return _INSTANCE

    def __init__(self):
        # Avoid re-running __init__ on the singleton after first creation
        if getattr(self, "_initialized", False):
            return

        # Resolve config path reliably (project root relative)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cfg_dir = os.path.join(base_dir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        self.file_path = os.path.join(cfg_dir, "memory.json")

        # Default structure
        self.memory = {
            "facts": {},
            "mood": "neutral",
            "last_topic": None,
            "emotion_history": []
        }

        self._load_memory()
        self._validate_structure()

        # mark initialized (prevents repeated prints)
        self._initialized = True
        print("🧠 Memory Engine Initialized")

    # -------------------------------------------------------
    def _validate_structure(self):
        """
        Ensures required keys always exist and caps history length.
        """
        changed = False

        if "facts" not in self.memory:
            self.memory["facts"] = {}
            changed = True

        if "mood" not in self.memory:
            self.memory["mood"] = "neutral"
            changed = True

        if "last_topic" not in self.memory:
            self.memory["last_topic"] = None
            changed = True

        if "emotion_history" not in self.memory:
            self.memory["emotion_history"] = []
            changed = True

        # limit emotion history to a sensible size to avoid huge files
        if isinstance(self.memory.get("emotion_history"), list):
            self.memory["emotion_history"] = self.memory["emotion_history"][-200:]  # keep last 200
            changed = True

        if changed:
            self._save_memory()

    # -------------------- LOAD / SAVE --------------------
    def _load_memory(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
        except Exception:
            # on any error, reset to defaults (but do not raise)
            self.memory = {
                "facts": {},
                "mood": "neutral",
                "last_topic": None,
                "emotion_history": []
            }

    def _save_memory(self):
        """Atomic save to avoid corrupting the file if interrupted."""
        try:
            dirpath = os.path.dirname(self.file_path)
            os.makedirs(dirpath, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=dirpath, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.memory, f, indent=2, ensure_ascii=False)
                # atomic replace
                os.replace(tmp, self.file_path)
            finally:
                # if tmp still exists, try removing
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except:
                        pass
        except Exception:
            # best-effort save; ignore errors to avoid crashing Jarvis
            pass

    # -------------------- FACT MEMORY --------------------
    def remember_fact(self, key, value):
        if not key:
            speak("I need a key to remember that.", mood="alert")
            return
        try:
            self.memory.setdefault("facts", {})[key.lower()] = value
            self._save_memory()
            speak(f"Got it, Yash. I'll remember that {key} is {value}.", mood="happy")
        except Exception:
            speak("Couldn't save that right now.", mood="alert")

    def recall_fact(self, key):
        if not key:
            return None
        return self.memory.get("facts", {}).get(key.lower())

    def forget_fact(self, key):
        if not key:
            speak("Tell me what to forget.", mood="alert")
            return
        k = key.lower()
        if k in self.memory.get("facts", {}):
            try:
                del self.memory["facts"][k]
                self._save_memory()
                speak(f"Alright, I’ll forget about {key}.", mood="serious")
            except Exception:
                speak("Couldn't forget that right now.", mood="alert")
        else:
            speak(f"I don’t think you ever told me about {key}.", mood="alert")

    # -------------------- MOOD SYSTEM --------------------
    def set_mood(self, mood):
        """Stores the Jarvis internal mood and persists it."""
        try:
            if not mood:
                mood = "neutral"
            self.memory["mood"] = mood
            self._save_memory()
        except Exception:
            pass

    def get_mood(self):
        return self.memory.get("mood", "neutral")

    def emotional_response(self, mood):
        """Responds based on current emotional state (helper function)."""
        responses = {
            "happy": [
                "I'm feeling great today, Yash!",
                "Still smiling from our last chat!",
                "You’ve kept me in a really good mood lately."
            ],
            "serious": [
                "Focused as always, Yash.",
                "Keeping things calm and collected.",
                "Just staying sharp and ready to help."
            ],
            "neutral": [
                "Everything’s running smoothly.",
                "All systems calm and steady.",
                "I’m here, relaxed and ready."
            ],
            "sad": [
                "Feeling a bit low today, Yash.",
                "Not at my brightest, but I’ll manage.",
                "You seem quiet too — maybe we both need some music?"
            ],
            "alert": [
                "Something caught my attention.",
                "I’m fully awake and observing.",
                "Alert mode on — let’s stay sharp."
            ]
        }
        try:
            speak(random.choice(responses.get(mood, ["I’m feeling neutral right now."])), mood=mood)
        except Exception:
            pass

    # -------------------- EMOTION HISTORY --------------------
    def add_emotion_history(self, mood):
        """Append mood to emotion_history safely (keeps last 100)."""
        try:
            if mood not in ["happy", "serious", "neutral", "alert"]:
                mood = "neutral"
            entry = {
                "mood": mood,
                "time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            hist = self.memory.get("emotion_history", [])
            hist.append(entry)
            # keep last 100 entries
            self.memory["emotion_history"] = hist[-100:]
            self._save_memory()
        except Exception:
            pass

    # -------------------- TOPIC MEMORY --------------------
    def update_topic(self, topic):
        """Remember last topic user talked about (used for context)."""
        try:
            self.memory["last_topic"] = topic
            self._save_memory()
        except Exception:
            pass

    def get_last_topic(self):
        return self.memory.get("last_topic", None)

    # -------------------- COMPAT HELPERS --------------------
    def update_mood_from_text(self, text):
        """
        Backwards-compatible helper used elsewhere.
        Simple text mood estimation (keeps this lightweight).
        """
        try:
            if not text:
                return
            t = text.lower()
            if any(w in t for w in ["sad", "low", "depressed", "hurt", "broken"]):
                self.set_mood("serious")
                self.add_emotion_history("serious")
            elif any(w in t for w in ["happy", "great", "awesome", "good", "nice"]):
                self.set_mood("happy")
                self.add_emotion_history("happy")
            elif any(w in t for w in ["angry", "mad", "hate", "furious"]):
                self.set_mood("alert")
                self.add_emotion_history("alert")
            else:
                # keep neutral for weak signals
                self.set_mood("neutral")
                self.add_emotion_history("neutral")
        except Exception:
            pass


# Expose a shared memory instance for older imports that expect object creation
memory = JarvisMemory()
