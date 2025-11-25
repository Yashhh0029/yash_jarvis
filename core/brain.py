# core/brain.py — IIT-Level Enhanced Friend Brain (UPGRADED)

import random
import time
import html
from typing import Optional

# Core systems
from core.memory_engine import JarvisMemory
from core.emotion_reflection import JarvisEmotionReflection
import core.nlp_engine as nlp
import core.state as state

# Optional LLM (local/Ollama/OpenAI)
try:
    import openai
except:
    openai = None

memory = JarvisMemory()
reflection = JarvisEmotionReflection()

class Brain:
    def __init__(self):
        self.personality = "friend_balanced"
        self._markov_chance = 0.25
        self._friend_tease_chance = 0.15
        self._max_len = 450
        print("🧠 Brain online — mode:", self.personality)

    # -----------------------------------------
    # EMOTION DETECTION (text-based)
    # -----------------------------------------
    def detect_text_emotion(self, text: Optional[str]) -> str:
        if not text:
            return "neutral"

        t = text.lower()

        groups = {
            "serious": ["sad", "hurt", "empty", "broken", "lonely", "upset", "low"],
            "alert": ["angry", "pissed", "furious", "scared", "fear", "panic", "worried", "stress"],
            "happy": ["happy", "great", "awesome", "nice", "amazing"],
            "neutral": ["bored", "meh", "okay", "fine"]
        }

        for mood, words in groups.items():
            if any(w in t for w in words):
                return mood

        return "neutral"

    # -----------------------------------------
    # EMOTION FUSION
    # -----------------------------------------
    def fuse_emotions(self, face=None, text=None, tone=None):
        votes = []

        # face → strongest
        face_map = {
            "happy": "happy",
            "surprise": "happy",
            "neutral": "neutral",
            "sad": "serious",
            "angry": "alert",
            "fear": "alert",
            "disgust": "serious"
        }
        if face:
            votes.append(face_map.get(face.lower(), "neutral"))

        # text
        if text:
            votes.append(self.detect_text_emotion(text))

        # tone
        if tone:
            votes.append(tone)

        # last memory
        last_mood = None
        try:
            hist = memory.memory.get("emotion_history", [])
            if hist:
                last_mood = hist[-1]["mood"]
                votes.append(last_mood)
        except:
            pass

        if not votes:
            return memory.get_mood() or "neutral"

        weight = {"happy": 3, "serious": 2, "alert": 2, "neutral": 1}
        tally = {}
        for v in votes:
            tally[v] = tally.get(v, 0) + weight.get(v, 1)

        final = max(tally, key=tally.get)

        try:
            memory.set_mood(final)
            reflection.add_emotion(final)
        except:
            pass

        return final
    # -------------------------------------------------------
    # CINEMATIC + FRIEND MODE WAKE-UP LINE
    # -------------------------------------------------------
    def generate_wakeup_line(self, mood=None, last_topic=None):
        mood = (mood or memory.get_mood() or "neutral").lower()

        lines = {
            "happy": [
                "Aye Yashu, I’m online and vibing.",
                "Energy high — what’s our plan, Yash?",
                "Back online — and kinda excited."
            ],
            "serious": [
                "Ready. Focused. Tell me the task.",
                "I’m online — let’s get this done properly.",
                "Fully active. Just say the word."
            ],
            "alert": [
                "I’m here — fully attentive.",
                "Alert mode off, listening now.",
                "You called — I’m focused."
            ],
            "neutral": [
                "I’m awake, Yash. What’s next?",
                "Alright — talk to me.",
                "Online. Listening."
            ]
        }

        base = random.choice(lines.get(mood, lines["neutral"]))

        # Friend tease (rare)
        tease = ""
        if random.random() < self._friend_tease_chance and mood != "serious":
            tease = random.choice([
                "Hope it’s something interesting.",
                "If it’s snacks — I’m all ears.",
                "You woke me up like a pro."
            ])

        # Markov flavor
        extra = ""
        if random.random() < self._markov_chance:
            try:
                extra = nlp._markov_generate() or ""
            except:
                extra = ""

        # Topic continuation
        topic_add = ""
        if last_topic and random.random() < 0.30:
            topic_add = f"We were talking about {last_topic}."

        parts = [base, tease, extra, topic_add]
        return " ".join([p for p in parts if p]).strip()

    # -------------------------------------------------------
    # EMOTIONAL SUPPORT ENGINE (FRIEND MODE)
    # -------------------------------------------------------
    def generate_emotional_support(self, user_feeling, mood=None):
        if not user_feeling:
            return "I’m here, Yash. Tell me what’s going on."

        t = user_feeling.lower()

        templates = {
            "sad": [
                "Come here, Yashu… talk to me. I'm right here.",
                "It’s okay to feel sad — I’m listening."
            ],
            "hurt": [
                "You don’t have to handle that pain alone.",
                "Tell me what hurt you — I’m here."
            ],
            "angry": [
                "Slow breath. Tell me what triggered you.",
                "I’m with you, Yash. Take it one line at a time."
            ],
            "stress": [
                "Let’s breathe in… and out. I’m here with you.",
                "One step at a time — tell me the heaviest part."
            ],
            "empty": [
                "Feeling empty is exhausting… sit with me.",
                "We’ll figure this out together, Yash."
            ],
            "happy": [
                "That’s the energy I love! Keep shining.",
                "You sound bright — I like that!"
            ]
        }

        for key, msgs in templates.items():
            if key in t:
                msg = random.choice(msgs)
                if random.random() < 0.25:
                    msg += " Want me to help with something specific?"
                return msg

        # Generic fallback
        fallback = random.choice([
            "I’m with you, Yash. Tell me a little more.",
            "Whatever it is — you’re not alone.",
        ])
        if random.random() < 0.25:
            fallback += " Should I give a suggestion?"
        return fallback

    # -------------------------------------------------------
    # TOPIC CONTINUATION GENERATOR
    # -------------------------------------------------------
    def generate_continuation(self, topic):
        if not topic:
            topic = "that topic"

        variants = [
            f"Want to go deeper into {topic}?",
            f"{topic} has more layers — want me to break them down?",
            f"We can push {topic} further — detailed or simple?"
        ]

        extra = ""
        if random.random() < self._markov_chance:
            try:
                extra = nlp._markov_generate()
            except:
                extra = ""

        return f"{random.choice(variants)} {extra}".strip()

    # -------------------------------------------------------
    # SHORT KNOWLEDGE ANSWERS (FRIEND MODE)
    # -------------------------------------------------------
    def answer_question(self, query, topic, mood=None):
        topic = (topic or "").lower()

        base_info = {
            "ai": "AI is basically pattern learning — machines understanding data like a human brain does.",
            "ml": "Machine learning allows systems to improve using past data — without explicit programming.",
            "java": "Java runs on the JVM, making it portable, secure, and fast.",
            "python": "Python is simple, powerful, and perfect for AI.",
            "life": "Life isn't solved — it's understood slowly.",
            "love": "Love is timing, effort, and understanding.",
            "daa": "DAA helps measure algorithm efficiency and complexity."
        }

        if topic in base_info:
            resp = base_info[topic]
        else:
            resp = f"{topic} is interesting — want a simple explanation or detailed?"

        # Markov flavor
        extra = ""
        if random.random() < 0.20:
            try:
                extra = nlp._markov_generate()
            except:
                extra = ""

        # Friendly signoff
        tail = ""
        if random.random() < 0.20:
            tail = random.choice([
                "Need an example?",
                "Want a summary?",
                "Shall I go deeper?"
            ])

        out = f"{resp} {extra} {tail}".strip()
        return out[:400]
    # -------------------------------------------------------
    # FALLBACK REPLY (When no command matched)
    # -------------------------------------------------------
    def fallback_reply(self, original_text=None):
        seeds = [
            "I might need a bit more clarity — say it in another way?",
            "Hmm… didn’t fully get that. Want me to search it?",
            "Try rephrasing that for me, Yashu."
        ]

        adds = [
            "I can open apps, search, or explain things — what do you need?",
            "Want me to check online?",
            "Should I give a short summary or a deep explanation?"
        ]

        base = random.choice(seeds)

        if random.random() < 0.35:
            base += " " + random.choice(adds)

        if random.random() < 0.25:
            base += " (I’m right here.)"

        return base

    # -------------------------------------------------------
    # FINAL RESPONSE ENHANCEMENT (Adds prefix/suffix/mood polish)
    # -------------------------------------------------------
    def enhance_response(self, text, mood=None, last_topic=None):
        if not text:
            return ""

        mood = (mood or memory.get_mood() or "neutral").lower()
        clean = text.strip()

        # Mood-based flavor
        prefix = ""
        suffix = ""

        if mood == "happy":
            prefix = random.choice(["Nice!", "Sweet!", "Love it!"]) if random.random() < 0.40 else ""
            suffix = random.choice(["That felt smooth.", "Good call."]) if random.random() < 0.25 else ""
        elif mood == "serious":
            prefix = random.choice(["Understood.", "Affirmative."]) if random.random() < 0.45 else ""
            suffix = random.choice(["Proceeding.", "Handled."]) if random.random() < 0.20 else ""
        elif mood == "alert":
            prefix = random.choice(["On it.", "Right away."]) if random.random() < 0.55 else ""
            suffix = random.choice(["Be careful.", "Done swiftly."]) if random.random() < 0.22 else ""
        else:  # neutral
            prefix = random.choice(["Okay.", "Alright."]) if random.random() < 0.22 else ""

        # Friendly “nudge”
        nudge = ""
        if random.random() < 0.20:
            nudge = random.choice([
                " Need anything else?",
                " Want me to continue?",
                " Shall I look up more?"
            ])

        # Flavor from markov chain
        markov = ""
        try:
            if random.random() < self._markov_chance:
                markov = nlp._markov_generate() or ""
        except:
            markov = ""

        # Combine everything
        parts = [prefix, clean, suffix, markov, nudge]
        out = " ".join([p for p in parts if p]).strip()

        # Slight topic reminder
        if last_topic and random.random() < 0.12:
            out += f" (about {last_topic})"

        # Safety trim
        if len(out) > 400:
            out = out[:370].rsplit(" ", 1)[0] + "..."

        return out

    # -------------------------------------------------------
    # LLM RESPONSE POST-PROCESSOR
    # (Wraps Ollama/ChatGPT responses with mood + personality)
    # -------------------------------------------------------
    def postprocess_reply(self, llm_reply, mood=None, last_topic=None):
        if not llm_reply:
            return self.fallback_reply()

        reply = llm_reply.strip()

        # Shorten long LLM outputs
        if len(reply) > 250:
            idx = reply.find(".", 180)
            if idx != -1:
                reply = reply[:idx+1]
            else:
                reply = reply[:300].rsplit(" ", 1)[0] + "..."

        # Apply personality polishing
        try:
            pretty = self.enhance_response(reply, mood=mood, last_topic=last_topic)
        except:
            pretty = reply

        # Store topic memory
        try:
            if last_topic:
                memory.update_topic(last_topic)
            else:
                # auto-extract short topic
                tokens = reply.split()
                if len(tokens) > 2:
                    memory.update_topic(" ".join(tokens[:3]))
        except:
            pass

        # sync global topic
        try:
            state.LAST_TOPIC = last_topic or state.LAST_TOPIC
        except:
            pass

        return pretty


# -------------------------------------------------------
# SINGLETON INSTANCE
# -------------------------------------------------------
brain = Brain()
print("🧠 Brain fully initialized with FRIEND + CINEMATIC mode.")
