# core/intent_parser.py
"""
Intent parser for Jarvis — lightweight, robust, and natural-language friendly.

Usage:
    from core.intent_parser import parse_intent
    intent = parse_intent("it's too bright in here")
    # intent -> {"intent": "adjust_brightness", "action": "decrease", "reason": "too bright", "confidence": 0.9}

Design:
- Pattern + keyword based (fast and offline)
- Returns a dict: { intent, confidence, params }
- Defensive: never throws; returns {"intent":"unknown", ...} on edge cases
"""

import re
from typing import Dict, Any, Optional

# small helper synonyms
_BRIGHTNESS_UP = ["increase brightness", "brightness up", "brighten", "more brightness", "it's dark", "i can't see", "not able to see", "low brightness", "too dark", "hard to see"]
_BRIGHTNESS_DOWN = ["decrease brightness", "brightness down", "dim", "dark", "too bright", "it's too bright", "reduce brightness", "bright is too much", "blinding"]
_VOLUME_UP = ["volume up", "increase volume", "louder", "sound up", "turn it up", "too low"]
_VOLUME_DOWN = ["volume down", "decrease volume", "lower volume", "dheere", "turn it down", "too loud"]
_MUTE = ["mute", "silence", "shut up", "quiet"]
_UNMUTE = ["unmute", "turn on sound"]
_SCREENSHOT = ["screenshot", "take screenshot", "save screen", "grab screen", "capture screen"]
_SEARCH = ["search", "find", "look up", "dhund", "search kar", "google", "on youtube"]
_OPEN = ["open", "launch", "start", "take me to"]
_CLOSE = ["close", "exit", "quit", "shutdown window"]
_PLAY = ["play", "pause", "resume", "stop", "play music", "pause music"]
_TYPE = ["type", "type this", "type message", "type that"]
_REMEMBER = ["remember that", "remember"]
_FORGET = ["forget", "forget that"]
_HELP = ["help", "explain", "how to", "what is", "why"]

def _contains_any(text: str, keywords):
    t = text.lower()
    for k in keywords:
        if k in t:
            return True
    return False

def _match_regex(text: str, patterns):
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m
    return None

def parse_intent(text: Optional[str]) -> Dict[str, Any]:
    """Parse user utterance into an intent dict.

    Returns:
      {
        "intent": str,
        "confidence": float (0.0-1.0),
        "params": { ... }  # intent-specific
      }
    """
    if not text or not text.strip():
        return {"intent": "none", "confidence": 0.0, "params": {}}

    t = text.lower().strip()

    # 1) Explicit memory patterns
    try:
        if "remember that" in t or t.startswith("remember "):
            # try "remember that key is value"
            m = re.search(r"remember (?:that )?(?P<k>[\w\s]+?) (?:is|=|to be) (?P<v>.+)", t)
            if m:
                return {
                    "intent": "remember_fact",
                    "confidence": 0.95,
                    "params": {"key": m.group("k").strip(), "value": m.group("v").strip()}
                }
            else:
                # <remember> with free text
                rest = t.replace("remember that", "").replace("remember", "").strip()
                return {"intent": "remember_prompt", "confidence": 0.8, "params": {"text": rest}}
    except Exception:
        pass

    # 2) Forget pattern
    try:
        if t.startswith("forget ") or " forget " in t:
            key = t.replace("forget", "").strip()
            return {"intent": "forget_fact", "confidence": 0.9, "params": {"key": key}}
    except Exception:
        pass

    # 3) Screenshot
    if _contains_any(t, _SCREENSHOT) or re.search(r"\b(screen shot|screen-shot|screen shot to)\b", t):
        # optional folder/file name
        m = re.search(r"(?:as|named|called)\s+([^\s]+(?:\.[a-zA-Z0-9]{2,4})?)", text, flags=re.I)
        filename = m.group(1) if m else None
        return {"intent": "screenshot", "confidence": 0.95, "params": {"filename": filename}}

    # 4) Brightness adjustments — include natural phrasing (user complaints)
    try:
        # direct increase/decrease commands
        if _contains_any(t, _BRIGHTNESS_UP):
            # if user says "i can't see" -> increase
            return {"intent": "adjust_brightness", "confidence": 0.95, "params": {"action": "increase", "reason": t}}
        if _contains_any(t, _BRIGHTNESS_DOWN):
            return {"intent": "adjust_brightness", "confidence": 0.95, "params": {"action": "decrease", "reason": t}}

        # complaint + qualifier mapping (eg: "too bright" => decrease)
        if re.search(r"\btoo bright\b|\bblinding\b|\bso bright\b", t):
            return {"intent": "adjust_brightness", "confidence": 0.98, "params": {"action": "decrease", "reason": "too bright"}}
        if re.search(r"\btoo dark\b|\bcan't see\b|\bnot able to see\b|\blow brightness\b", t):
            return {"intent": "adjust_brightness", "confidence": 0.98, "params": {"action": "increase", "reason": "too dark"}}
    except Exception:
        pass

    # 5) Volume adjustments & mute
    try:
        if _contains_any(t, _VOLUME_UP):
            return {"intent": "adjust_volume", "confidence": 0.95, "params": {"action": "up"}}
        if _contains_any(t, _VOLUME_DOWN):
            return {"intent": "adjust_volume", "confidence": 0.95, "params": {"action": "down"}}
        if "mute" in t and "unmute" not in t:
            return {"intent": "mute", "confidence": 0.98, "params": {}}
        if "unmute" in t:
            return {"intent": "unmute", "confidence": 0.98, "params": {}}
    except Exception:
        pass

    # 6) Open / launch / app-specific
    try:
        if any(k in t for k in _OPEN):
            # capture app/site name
            m = re.search(r"(?:open|launch|start|take me to)\s+(?P<app>[\w\.\-/ ]+)", t)
            app = m.group("app").strip() if m else None
            return {"intent": "open_app", "confidence": 0.9, "params": {"app": app}}
    except Exception:
        pass

    # 7) Search queries (explicit)
    try:
        if any(k in t for k in _SEARCH):
            # extract "search for X" or fallback whole phrase minus the verb
            m = re.search(r"(?:search (?:for|about)?|find|look up)\s+(?P<q>.+)", t)
            q = m.group("q").strip() if m else re.sub(r"\b(search|find|look up|dhund|search kar|on youtube|on google)\b", "", t).strip()
            return {"intent": "search", "confidence": 0.9, "params": {"query": q}}
    except Exception:
        pass

    # 8) Typing commands
    try:
        if any(k in t for k in _TYPE):
            # get content after 'type' keywords
            s = re.sub(r"(type this|type message|type that|type kar|type)\s*", "", t)
            if s:
                return {"intent": "type_text", "confidence": 0.92, "params": {"text": s}}
            else:
                return {"intent": "type_text_prompt", "confidence": 0.7, "params": {}}
    except Exception:
        pass

    # 9) Media controls
    try:
        if any(k in t for k in _PLAY):
            if "pause" in t:
                return {"intent": "media_pause", "confidence": 0.9, "params": {}}
            if "play" in t or "resume" in t:
                return {"intent": "media_play", "confidence": 0.9, "params": {}}
            if "stop" in t:
                return {"intent": "media_stop", "confidence": 0.9, "params": {}}
    except Exception:
        pass

    # 10) Explicit direct questions / help
    try:
        if any(k in t for k in _HELP):
            # return generic help intent + original text
            return {"intent": "ask_question", "confidence": 0.8, "params": {"text": text}}
    except Exception:
        pass

    # 11) Short responses / confirmations / negatives
    try:
        if re.fullmatch(r"\b(yes|yeah|yup|y|sure|ok|okay)\b", t):
            return {"intent": "confirm", "confidence": 0.95, "params": {}}
        if re.fullmatch(r"\b(no|nah|nope|don't|dont|stop)\b", t):
            return {"intent": "deny", "confidence": 0.95, "params": {}}
    except Exception:
        pass

    # 12) Memory recall: "what is my X" -> recall
    try:
        m = re.match(r"(?:what is|what's|tell me) (?:my )?(?P<k>[\w\s]+)\??", t)
        if m and ("what is" in t or "what's" in t):
            return {"intent": "recall_fact", "confidence": 0.8, "params": {"key": m.group("k").strip()}}
    except Exception:
        pass

    # 13) Fallback: try to detect simple "visibility complaint" to map to brightness
    try:
        if re.search(r"\b(i can(')?t see|can't see|not able to see|blur|too dark|can't read)\b", t):
            return {"intent": "adjust_brightness", "confidence": 0.88, "params": {"action": "increase", "reason": t}}
    except Exception:
        pass

    # 14) Unknown intent: return raw text for conversation fallback
    return {"intent": "unknown", "confidence": 0.35, "params": {"text": text}}
