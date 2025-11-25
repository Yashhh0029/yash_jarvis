# core/ai_client.py
"""
AI client adapter for Jarvis — compatibility + robust fallbacks.

Behavior:
- Prefer core.ai_chat.ai_chat_brain (the new Ollama-based module).
- Else try a lightweight Ollama HTTP wrapper (if httpx is installed).
- Else fallback to core.conversation_core.JarvisConversation.
- Provides a small stable API:
    ai_client.available() -> bool
    ai_client.ask(prompt: str, timeout: float|None = None) -> str|None

This file should be drop-in compatible with other modules that call
`ai_chat_brain.ask(...)` or expect an `ai_client` style object.
"""

import time
import threading
import traceback

# Try to use the new consolidated ai_chat if present
try:
    from core.ai_chat import ai_chat_brain as _new_ai_brain  # final stable ai_chat (ollama wrapper)
    _HAS_NEW_AICHAT = True
except Exception:
    _new_ai_brain = None
    _HAS_NEW_AICHAT = False

# Try HTTP client for raw Ollama if needed
try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    httpx = None
    _HAS_HTTPX = False

# Try local fallback conversation
try:
    from core.conversation_core import JarvisConversation
    _HAS_CONV = True
except Exception:
    JarvisConversation = None
    _HAS_CONV = False

# Optional memory (not required but used if available)
try:
    from core.memory_engine import JarvisMemory
    _MEMORY = JarvisMemory()
except Exception:
    _MEMORY = None

# state (for optional context update)
try:
    import core.state as state
except Exception:
    state = None

# Default Ollama HTTP config (used only if ai_chat not available and httpx present)
_DEFAULT_OLLAMA_HOST = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
_DEFAULT_TIMEOUT = 20.0


class _HTTPollama:
    """Small, resilient Ollama HTTP client used as a fallback."""
    def __init__(self, host=_DEFAULT_OLLAMA_HOST, model=_DEFAULT_OLLAMA_MODEL, timeout=_DEFAULT_TIMEOUT):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = float(timeout)

    def available(self) -> bool:
        if not _HAS_HTTPX:
            return False
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def ask(self, user_prompt: str, system_prompt: str = "", timeout: float | None = None) -> str | None:
        if not _HAS_HTTPX:
            return None
        try:
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or ""},
                    {"role": "user", "content": user_prompt or ""}
                ]
            }
            to = timeout or self.timeout
            with httpx.Client(timeout=to) as client:
                resp = client.post(f"{self.host}/api/chat", json=body)
            if resp.status_code != 200:
                return None
            data = resp.json()
            # expected format: {"message":{"role":"assistant","content":"..."}}
            if isinstance(data, dict):
                if "message" in data and isinstance(data["message"], dict):
                    return data["message"].get("content", "").strip() or None
                if "content" in data:
                    return str(data.get("content", "")).strip() or None
            return None
        except Exception:
            # don't crash; return None on failure
            return None


class LocalConvWrapper:
    """Wrap JarvisConversation to provide ask() semantics."""
    def __init__(self):
        self.conv = JarvisConversation() if _HAS_CONV else None

    def available(self):
        return self.conv is not None

    def ask(self, prompt: str, timeout: float | None = None) -> str:
        if not self.conv:
            return f"I heard: {prompt or ''}"
        try:
            return self.conv.respond(prompt or "") or "I couldn't form a reply."
        except Exception:
            return "Local conversation engine failed."


class AIClient:
    """
    Unified AI client adapter used by other modules.

    Usage:
        from core.ai_client import ai_client
        if ai_client.available():
            reply = ai_client.ask("hello jarvis")
    """

    def __init__(self):
        # priority: new ai_chat (preferred), HTTP Ollama, local conv
        self._source = None
        self._http = _HTTPollama()
        self._local = LocalConvWrapper()
        self._lock = threading.Lock()

        # prefer new ai_chat if present
        if _HAS_NEW_AICHAT and _new_ai_brain is not None:
            self._source = ("ai_chat", _new_ai_brain)
        elif self._http.available():
            self._source = ("http_ollama", self._http)
        elif self._local.available():
            self._source = ("local_conv", self._local)
        else:
            self._source = ("none", None)

    def refresh_source(self):
        """Try to detect a better source (non-blocking)."""
        try:
            if _HAS_NEW_AICHAT and _new_ai_brain is not None:
                self._source = ("ai_chat", _new_ai_brain)
                return
            if self._http.available():
                self._source = ("http_ollama", self._http)
                return
            if self._local.available():
                self._source = ("local_conv", self._local)
                return
            self._source = ("none", None)
        except Exception:
            self._source = ("none", None)

    def available(self) -> bool:
        """Is there any usable backend?"""
        s, impl = self._source
        if s == "ai_chat":
            return impl is not None
        if s == "http_ollama":
            return impl is not None and impl.available()
        if s == "local_conv":
            return impl is not None and impl.available()
        # try to refresh quickly
        self.refresh_source()
        s, impl = self._source
        return s in ("ai_chat", "http_ollama", "local_conv") and impl is not None

    def ask(self, prompt: str, timeout: float | None = None) -> str:
        """Ask the best available backend for a reply. Returns a string (never raises)."""
        if not prompt:
            return ""

        # quick opportunistic refresh
        try:
            if self._source[0] == "none":
                self.refresh_source()
        except Exception:
            pass

        s, impl = self._source

        # 1) Preferred new ai_chat module (core.ai_chat.ai_chat_brain)
        if s == "ai_chat" and impl is not None:
            try:
                # its API is ask(prompt) returning a string
                return impl.ask(prompt) or "I couldn't get a response."
            except Exception:
                traceback.print_exc()
                # try to fall through to other backends

        # 2) HTTP Ollama fallback
        if (s == "http_ollama" or (impl is None and self._http.available())) and _HAS_HTTPX:
            try:
                resp = self._http.ask(prompt, system_prompt="", timeout=timeout)
                if resp:
                    # update last topic if state available
                    try:
                        if state is not None:
                            state.LAST_TOPIC = prompt
                    except:
                        pass
                    return resp
            except Exception:
                traceback.print_exc()

        # 3) Local conversation fallback
        try:
            if self._local and self._local.available():
                return self._local.ask(prompt)
        except Exception:
            traceback.print_exc()

        # Final safe fallback: echo politely
        return "Sorry Yash, I'm not connected to a model right now."

    # Async helper (fire-and-forget thread, stores latest reply callback)
    def ask_async(self, prompt: str, callback=None, timeout: float | None = None):
        """
        Ask in a background thread. callback(reply_str) will be called with the reply.
        """
        def _worker(q, cb, to):
            try:
                r = self.ask(q, timeout=to)
            except Exception:
                r = "I couldn't get an answer right now."
            if cb:
                try:
                    cb(r)
                except Exception:
                    pass

        t = threading.Thread(target=_worker, args=(prompt, callback, timeout), daemon=True)
        t.start()
        return t


# Export singleton
ai_client = AIClient()

# Backwards-compat convenience: old code sometimes expected `ai_chat_brain` name
# We attempt to expose a minimal compatible object.
class _CompatWrapper:
    def __init__(self, client):
        self._client = client

    def available(self):
        return self._client.available()

    def ask(self, prompt):
        return self._client.ask(prompt)

# Expose `ai_chat_brain` if not already used by new ai_chat
ai_chat_brain = _new_ai_brain if _HAS_NEW_AICHAT and _new_ai_brain is not None else _CompatWrapper(ai_client)
