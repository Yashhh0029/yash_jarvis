# core/ai_chat.py — FINAL INTEGRATED VERSION (STABLE)

"""
AI Chat Brain for Jarvis
- Uses Ollama (llama3.1 / any local model)
- Falls back to conversation_core
- Injects memory + mood + last topic
- Responds like a friend + assistant
"""

import json
import time

# -------------------------------------------
# Optional HTTP client for Ollama raw requests
# -------------------------------------------
try:
    import httpx
    _HAS_HTTPX = True
except:
    _HAS_HTTPX = False

# -------------------------------------------
# Optional direct Ollama Python package
# -------------------------------------------
try:
    import ollama
    _HAS_OLLAMA_PKG = True
except:
    ollama = None
    _HAS_OLLAMA_PKG = False

# -------------------------------------------
# Local fallback convo
# -------------------------------------------
try:
    from core.conversation_core import JarvisConversation
    _HAS_CONV = True
except:
    JarvisConversation = None
    _HAS_CONV = False

# -------------------------------------------
# Memory + State
# -------------------------------------------
try:
    from core.memory_engine import JarvisMemory
    memory = JarvisMemory()
except:
    memory = None

import core.state as state


# ============================================================
#   OLLAMA CLIENT (HTTP + PYTHON PACKAGE)
# ============================================================
class OllamaClient:
    def __init__(self, model="llama3.1:8b"):
        self.model = model
        self.http_url = "http://localhost:11434/api/chat"

    def available(self):
        """Check if Ollama is alive."""
        if _HAS_OLLAMA_PKG:
            return True

        if not _HAS_HTTPX:
            return False

        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            return r.status_code == 200
        except:
            return False

    def ask(self, system_prompt, user_prompt):
        """Unified stable call."""

        # ---- Preferred: Python package ----
        if _HAS_OLLAMA_PKG:
            try:
                out = ollama.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return out.get("message", {}).get("content", "").strip()
            except:
                pass

        # ---- Fallback: httpx API ----
        if _HAS_HTTPX:
            try:
                r = httpx.post(
                    self.http_url,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    },
                    timeout=20
                )
                data = r.json()
                return data.get("message", {}).get("content", "").strip()
            except:
                pass

        return None


# ============================================================
#   LOCAL FALLBACK
# ============================================================
class LocalFallback:
    def __init__(self):
        self.conv = JarvisConversation() if _HAS_CONV else None

    def ask(self, prompt):
        if not self.conv:
            return "I’m listening: " + (prompt or "")
        try:
            r = self.conv.respond(prompt)
            return r or "Try saying that again?"
        except:
            return "I couldn’t process that locally."


# ============================================================
#   AI CHAT BRAIN (MAIN CLASS)
# ============================================================
class AIChatBrain:
    def __init__(self, model="llama3.1:8b"):
        self.model = model
        self.ollama = OllamaClient(model=model)
        self.fallback = LocalFallback()

    # ---------------------------------------------------------
    # Build the personality + memory injected prompt
    # ---------------------------------------------------------
    def _build_system_prompt(self):
        mood = ""
        last_topic = ""

        try:
            mood = memory.get_mood() or "neutral"
        except:
            mood = "neutral"

        try:
            last_topic = state.LAST_TOPIC or ""
        except:
            last_topic = ""

        # Fetch all memories
        try:
            mem_list = memory.get_all_facts() or []
        except:
            mem_list = []

        mem_text = "\n".join([f"- {m}" for m in mem_list]) if mem_list else "No saved memory."

        return f"""
You are Jarvis — Yash's personal AI partner.
Tone:
- friendly, caring, witty
- understands Hinglish, typos, short forms
- emotional intelligence like a real friend
- but logical & smart like ChatGPT
- NEVER robotic

Context:
- Yash Mood: {mood}
- Jarvis Mood: {state.JARVIS_MOOD}
- Last Topic: {last_topic}

Long-term Memory:
{mem_text}

Rules:
1. Talk like a human friend + assistant.
2. If Yash is emotional, respond empathetically.
3. If it's a command → reply short & confirm.
4. If chatting → reply naturally & expressive.
5. If unsure → ask Yash, never hallucinate.
"""

    # ---------------------------------------------------------
    # Main ASK
    # ---------------------------------------------------------
    def ask(self, prompt: str):
        if not prompt:
            return "Bolo Yash, I’m listening 😊"

        system_prompt = self._build_system_prompt()

        # Try Ollama
        if self.ollama.available():
            ans = self.ollama.ask(system_prompt, prompt)
            if ans:
                try:
                    state.LAST_TOPIC = prompt
                except:
                    pass
                return ans

        # Fallback local
        return self.fallback.ask(prompt)


# ============================================================
# Export singleton
# ============================================================
ai_chat_brain = AIChatBrain()
