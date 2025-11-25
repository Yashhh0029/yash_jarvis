# core/nlp_engine.py — Upgraded Hybrid NLP Engine (SAFE & Compatible)
"""
This version is fully backward-compatible with all your existing files.
✓ Zero breaking changes
✓ Faster learning
✓ Safer Markov chain
✓ Cleaner history handling
✓ Higher-quality wake/ack lines
"""

import os
import random
import threading

# ------------------------------------------------------------
# HISTORY LOAD
# ------------------------------------------------------------
HISTORY_PATH = os.path.join("config", "nlp_history.txt")
os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)

try:
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        _HISTORY = [line.strip() for line in f.readlines() if line.strip()]
except:
    _HISTORY = []

# ------------------------------------------------------------
# BUILD MARKOV (safer version)
# ------------------------------------------------------------
def _build_markov(history):
    M = {}
    for line in history:
        words = line.split()
        if len(words) < 2:
            continue
        for i in range(len(words) - 1):
            a = words[i].lower()
            b = words[i + 1].lower()
            if a.isalpha() and b.isalpha():
                M.setdefault(a, []).append(b)
    return M

_MARKOV = _build_markov(_HISTORY)
_LOCK = threading.Lock()

# ------------------------------------------------------------
# LEARN (safe, fast)
# ------------------------------------------------------------
def learn(phrase: str):
    """Safely append phrase & update Markov chain."""
    if not phrase or not phrase.strip():
        return

    phrase = phrase.strip()

    with _LOCK:
        try:
            # Write safely to history file
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(phrase + "\n")

            _HISTORY.append(phrase)

            # Update Markov quickly
            words = phrase.split()
            if len(words) > 1:
                for i in range(len(words) - 1):
                    a = words[i].lower()
                    b = words[i + 1].lower()
                    if a.isalpha() and b.isalpha():
                        _MARKOV.setdefault(a, []).append(b)

        except Exception:
            pass

# async wrapper
def learn_async(phrase):
    threading.Thread(target=learn, args=(phrase,), daemon=True).start()


# ------------------------------------------------------------
# MARKOV GENERATOR (cleaned & safer)
# ------------------------------------------------------------
def _markov_generate(seed_word=None, length=8):
    """Generate short natural text — guaranteed no crashes."""
    if not _MARKOV:
        return None

    # Seed selection
    seed = seed_word.lower() if seed_word else random.choice(list(_MARKOV.keys()))
    if seed not in _MARKOV:
        seed = random.choice(list(_MARKOV.keys()))

    out = [seed.capitalize()]
    cur = seed

    for _ in range(length - 1):
        options = _MARKOV.get(cur)
        if not options:
            break
        nxt = random.choice(options)
        out.append(nxt)
        cur = nxt

    sentence = " ".join(out)
    # Make it cleaner (avoid trailing bad tokens)
    return sentence.strip().rstrip(",. ")


# ------------------------------------------------------------
# TEMPLATES (improved naturalness)
# ------------------------------------------------------------
_WAKE_TEMPLATES = [
    "Good {time_of_day}, Yash. I'm active and listening.",
    "Systems up — what’s our first task today?",
    "Fully online. How can I assist you?"
]

_LIMITED_TEMPLATES = [
    "Face not verified — limited mode enabled. You can still give searches and local commands.",
    "Limited mode active, but I'm still here for essential tasks."
]

_ACK_TEMPLATES = [
    "Done. What next?",
    "Finished — anything else?",
    "All set, Yash."
]

# ------------------------------------------------------------
# PUBLIC GENERATORS
# ------------------------------------------------------------
def generate_greeting(mood="neutral"):
    base = random.choice(_WAKE_TEMPLATES)
    extra = _markov_generate(length=6) or ""
    return f"{base} {extra}".strip()

def generate_wakeup(mood="neutral"):
    variants = [
        "Aye aye, I'm awake.",
        "Yes Yash, I'm right here.",
        "Boot complete — listening."
    ]
    extra = _markov_generate(length=6) or ""
    return random.choice(variants) + (" " + extra if extra else "")

def generate_limited_mode_line(mood="neutral"):
    return random.choice(_LIMITED_TEMPLATES)

def generate_ack(mood="neutral"):
    return random.choice(_ACK_TEMPLATES)

# ------------------------------------------------------------
# Backward compatibility (do NOT remove)
# ------------------------------------------------------------
learn = learn
