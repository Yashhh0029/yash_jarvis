# core/emotion_reflection.py
"""
Emotion Reflection Engine — Cinematic Version
Keeps emotional history and generates natural reflections.
Fully compatible with:
- brain.py (mood fusion)
- memory_engine.py (shared memory)
- conversation_core.py (dynamic mood flow)
"""

import datetime
import random

from core.memory_engine import JarvisMemory
from core.speech_engine import speak

# shared singleton memory instance
shared_memory = JarvisMemory()


class JarvisEmotionReflection:
    """Tracks mood history and provides soft emotional insights."""

    def __init__(self):
        # ensure shared emotional history exists only once
        if "emotion_history" not in shared_memory.memory:
            shared_memory.memory["emotion_history"] = []
            shared_memory._save_memory()
        print("🧠 Emotion Reflection Engine Ready")

    # ----------------------------------------------------------
    def add_emotion(self, mood: str):
        """Record mood safely (store only last 12 moods)."""
        if mood not in ["happy", "serious", "neutral", "alert"]:
            mood = "neutral"

        entry = {
            "mood": mood,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        hist = shared_memory.memory.get("emotion_history", [])
        hist.append(entry)

        # keep only last 12 moods
        shared_memory.memory["emotion_history"] = hist[-12:]
        shared_memory._save_memory()

    # ----------------------------------------------------------
    def reflect(self, last_topic=None):
        """
        Reflect on emotional patterns — called only when asked.
        Does NOT interrupt user naturally.
        """

        hist = shared_memory.memory.get("emotion_history", [])
        if not hist:
            speak("I don't have enough emotional data yet, Yash.", mood="neutral")
            return

        # most recent moods
        last = hist[-1]["mood"]
        prev = hist[-2]["mood"] if len(hist) > 1 else None

        # ------------------------------------------------------
        # Mood transition (cinematic)
        # ------------------------------------------------------
        if prev and last != prev:
            transitions = {
                ("serious", "happy"): [
                    "You seem brighter now, Yash.",
                    "Your voice feels lighter than before."
                ],
                ("happy", "serious"): [
                    "You feel quieter suddenly. Is something on your mind?",
                    "Your tone shifted… I'm here if you want to talk."
                ],
                ("alert", "happy"): [
                    "I can sense relief in your tone.",
                    "You seem calmer compared to earlier."
                ],
                ("happy", "alert"): [
                    "You sounded cheerful earlier… but now something feels tense.",
                    "Your energy changed suddenly. Want to talk?"
                ],
                ("neutral", "happy"): [
                    "You sound a bit more cheerful now.",
                    "A positive shift — I love that energy."
                ],
                ("neutral", "serious"): [
                    "You seem more focused than a moment ago.",
                    "Your tone feels a bit heavier… everything okay?"
                ]
            }

            key = (prev, last)
            if key in transitions:
                speak(random.choice(transitions[key]), mood=last)
                return

        # ------------------------------------------------------
        # Dominant mood analysis (last 6 moods)
        # ------------------------------------------------------
        moods = [m["mood"] for m in hist[-6:]]
        freq = {m: moods.count(m) for m in set(moods)}
        dominant = max(freq, key=freq.get)

        reflections = {
            "happy": [
                "You've sounded positive lately — it’s refreshing.",
                "Love this brightness in your tone, Yash."
            ],
            "serious": [
                "You've been calm and thoughtful recently.",
                "Your tone feels focused — I admire that."
            ],
            "neutral": [
                "Your mood seems steady and balanced.",
                "You've been consistent and composed lately."
            ],
            "alert": [
                "You’ve sounded a bit tense in recent moments.",
                "I sense stress in your tone… I’m right here for you."
            ]
        }

        line = random.choice(reflections.get(dominant, reflections["neutral"]))

        # Add cinematic continuity (optional)
        if last_topic:
            line += f" And earlier we were talking about {last_topic}. Want to continue?"

        speak(line, mood=dominant)
