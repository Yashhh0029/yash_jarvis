# core/conversation_core.py
"""
Hybrid conversational core for Jarvis (Hybrid Mode - natural + consistent).

Goals:
- Preserve Yash's casual Jarvis voice.
- Improve topic continuity, mood detection, and non-repetitive fallbacks.
- Integrate cleanly with brain.py, memory_engine, emotion_reflection and nlp.
- Defensive: won't crash if optional modules fail.
"""

import random
import re
import time
from typing import Optional
from collections import deque

from core.brain import brain
from core.memory_engine import JarvisMemory
from core.emotion_reflection import JarvisEmotionReflection
import core.state as state
import core.nlp_engine as nlp

# Singletons (re-instantiating memory is safe since it's file-backed)
memory = JarvisMemory()
reflection = JarvisEmotionReflection()


def _word_bound_search(word_list, text):
    """Return True if any word from word_list appears as a whole word in text."""
    for w in word_list:
        # word boundary, case-insensitive
        if re.search(rf'\b{re.escape(w)}\b', text, flags=re.IGNORECASE):
            return True
    return False


class JarvisConversation:
    """
    Hybrid conversation core: natural + consistent personality,
    mood-aware, memory-aware, topic-aware.
    """

    def __init__(self):
        print("🧩 Conversational Core Online (Hybrid Mode)")
        self.last_topic = None
        self.last_response = ""
        # fixed-size history to avoid repetitive fallbacks
        self.recent_fallbacks = deque(maxlen=8)
        # small anti-repeat cache for last user queries (for slightly different wording)
        self._recent_user_queries = deque(maxlen=12)

    # -------------------------------------------------------
    # Lightweight sentiment → mood detection (scoring-based)
    # -------------------------------------------------------
    def _estimate_sentiment(self, text: Optional[str]) -> str:
        if not text:
            return "neutral"
        t = text.lower()

        # keyword lists (expanded slightly)
        sad = ["sad", "low", "down", "hurt", "upset", "empty", "broken", "depressed", "lonely", "tear"]
        happy = ["happy", "great", "awesome", "nice", "good", "fantastic", "amazing", "glad", "yay", "excited"]
        angry = ["angry", "mad", "pissed", "furious", "hate", "annoyed"]
        anxious = ["scared", "worried", "anxious", "panic", "stressed", "stress", "overthinking", "nervous"]
        bored = ["bored", "meh", "boring", "idle"]

        score = 0
        # each match adjusts score
        if _word_bound_search(sad, t):
            score -= 2
        if _word_bound_search(angry, t):
            score -= 3
        if _word_bound_search(anxious, t):
            score -= 2
        if _word_bound_search(happy, t):
            score += 3
        if _word_bound_search(bored, t):
            score -= 1

        # negation handling (simple)
        if re.search(r"\b(no|not|n't|never)\b", t):
            # flip some effect if there are strong emotion words
            if _word_bound_search(happy, t):
                score -= 2
            if _word_bound_search(sad, t):
                score += 1

        # map score to mood labels used across project
        if score >= 2:
            return "happy"
        if score <= -2:
            # disambiguate angry vs serious
            if _word_bound_search(angry, t):
                return "alert"
            return "serious"
        return "neutral"

    # -------------------------------------------------------
    # Topic detection (keywords + heuristics)
    # -------------------------------------------------------
    def _detect_topic(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        t = text.lower()

        # domain-specific keywords mapping (multi-word keys allowed)
        topic_map = {
            "ai": ["ai", "artificial intelligence", "machine learning", "deep learning"],
            "java": ["java", "jvm", "spring"],
            "daa": ["daa", "dynamic programming", "algorithms", "graphs"],
            "python": ["python", "py"],
            "graphics": ["graphics", "opengl", "projection", "3d"],
            "dbms": ["dbms", "database", "sql", "mysql", "postgres", "oracle"],
            "blockchain": ["blockchain", "ethereum", "smart contract"],
            "gesture": ["gesture", "hand gesture", "gesture recognition"],
            "emotion": ["emotion", "mood", "feeling"],
            "life": ["life", "future", "career"],
            "love": ["love", "relationship", "gf", "bf", "crush"],
        }

        for key, aliases in topic_map.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", t):
                    return key

        # fallback: try to extract a reasonable noun-like token
        m = re.search(r"\b([a-zA-Z]{3,20})\b", t)
        return m.group(1) if m else None

    # -------------------------------------------------------
    # Continue topic helper
    # -------------------------------------------------------
    def _continue_topic(self) -> str:
        if not self.last_topic:
            base = "Continue what, Yashu? Remind me the topic and I'll follow up."
            return brain.enhance_response(base, mood=memory.get_mood())

        base_templates = {
            "ai": "AI improves when you iterate on datasets and objectives. Want a small example or a project idea?",
            "java": "Java is excellent for large apps — focus on design patterns and testing. Want a sample structure?",
            "life": "Small consistent habits beat sudden bursts. Which habit should we plan first?",
            "love": "Communication and patience are key. Want a gentle script to start a conversation?",
            "daa": "For DAA, practice time/space trade-offs with real problems — want 3 practice problems?",
            "dbms": "Normalization and indexing matter. Want a quick explanation of normalization levels?"
        }

        reply = base_templates.get(self.last_topic, f"Let's explore more about {self.last_topic}. Which part interests you?")
        return brain.enhance_response(reply, mood=memory.get_mood(), last_topic=self.last_topic)

    # -------------------------------------------------------
    # Public API: respond
    # -------------------------------------------------------
    def respond(self, text: Optional[str]) -> str:
        # defensive
        if not text:
            candidate = "Yes Yashu? I'm listening."
            return brain.enhance_response(candidate, mood=memory.get_mood(), last_topic=memory.get_last_topic())

        raw = text.strip()
        t = raw.lower()

        # store recent queries to avoid repeating identical processing
        try:
            if len(self._recent_user_queries) == self._recent_user_queries.maxlen:
                self._recent_user_queries.popleft()
            self._recent_user_queries.append(raw)
        except Exception:
            pass

        # non-blocking learning (best-effort)
        try:
            nlp.learn_async(raw)
        except Exception:
            pass

        # estimate mood, update memory + reflection + global state (safe)
        try:
            mood = self._estimate_sentiment(t)
            memory.set_mood(mood)
            reflection.add_emotion(mood)
            try:
                state.JARVIS_MOOD = mood
            except Exception:
                pass
        except Exception:
            mood = memory.get_mood() or "neutral"

        # WAKEWORD / presence checks (short friendly lines)
        if t in ("jarvis", "hey jarvis", "are you there", "yo jarvis", "jarvis bolo", "jarvis haan"):
            try:
                line = brain.generate_wakeup_line(mood=memory.get_mood(), last_topic=self.last_topic)
                return brain.enhance_response(line, mood=memory.get_mood(), last_topic=self.last_topic)
            except Exception:
                return brain.enhance_response("Yes Yashu, I am here.", mood=memory.get_mood())

        # Emotional triggers (direct "I am ..." lines)
        try:
            # if user says "i am sad" or "i feel low", pick it up
            if re.search(r"\b(i am|i'm|i feel|feeling)\b.*\b(sad|low|hurt|empty|depressed|lonely)\b", t):
                reply = brain.generate_emotional_support("sad", mood)
                return brain.enhance_response(reply, mood=mood, last_topic="mood")
            if re.search(r"\b(i am|i'm|i feel|feeling)\b.*\b(happy|great|good|awesome|excited)\b", t):
                reply = brain.generate_emotional_support("happy", mood)
                return brain.enhance_response(reply, mood=mood, last_topic="mood")
        except Exception:
            pass

        # Continue / expand requests
        if any(w in t for w in ("continue", "more", "keep going", "tell me more")):
            return self._continue_topic()

        # Question / explain requests -> attempt knowledgeful answer
        if re.search(r"\b(what|why|how|explain|help|define)\b", t):
            topic = self._detect_topic(t)
            self.last_topic = topic
            try:
                memory.update_topic(topic)
            except Exception:
                pass
            try:
                reply = brain.answer_question(t, topic, mood)
                return brain.enhance_response(reply, mood=mood, last_topic=topic)
            except Exception:
                fallback = f"I can explain {topic or 'that'} — short summary or a detailed explanation?"
                return brain.enhance_response(fallback, mood=mood, last_topic=topic)

        # Command-like inputs (quick ack, actual execution delegated elsewhere)
        if any(w in t for w in ("open", "launch", "play", "type", "search", "screenshot", "volume", "brightness", "notepad", "whatsapp")):
            topic = self._detect_topic(t)
            self.last_topic = topic
            try:
                memory.update_topic(topic)
            except Exception:
                pass
            ack = random.choice([
                "On it, Yash. Doing that now.",
                "Got the command — executing.",
                "Alright — I'll take care of that."
            ])
            return brain.enhance_response(ack, mood=mood, last_topic=topic)

        # Natural fallback (varied, non-repetitive, context-aware)
        fallback_pool = [
            "Hmm… interesting. Want to explore that?",
            "Tell me more — I’m following you.",
            "You always think differently. What’s the next part?",
            "I can dive deeper into that if you want.",
            "Want a breakdown, a summary, or a story version?"
        ]

        # pick a fallback that isn't the immediate last one
        reply = random.choice(fallback_pool)
        if self.recent_fallbacks and reply == self.recent_fallbacks[-1]:
            # choose alternative if possible
            alt = [r for r in fallback_pool if r != reply]
            if alt:
                reply = random.choice(alt)

        # small heuristics: if user repeated same question several times, give a stronger answer
        try:
            recent_same = sum(1 for q in self._recent_user_queries if q.lower() == raw.lower())
            if recent_same >= 2:
                # escalate: ask if user wants a step-by-step or an example
                reply = "Seems like you want a clear answer. Do you want a short summary or a step-by-step example?"
        except Exception:
            pass

        # update last topic & shared state
        try:
            self.last_topic = self._detect_topic(t)
            state.LAST_TOPIC = self.last_topic
            memory.update_topic(self.last_topic)
        except Exception:
            pass

        # produce final enhanced reply
        enhanced = brain.enhance_response(reply, mood=mood, last_topic=self.last_topic)
        # store in fallbacks history
        try:
            self.recent_fallbacks.append(enhanced)
        except Exception:
            pass

        self.last_response = enhanced
        return enhanced
