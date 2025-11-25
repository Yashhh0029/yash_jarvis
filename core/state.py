"""
Global runtime state for Jarvis.
Only variables — no logic, no functions.
Shared across all modules.
"""

# -------------------------------------------------------------
# FACE AUTH
# -------------------------------------------------------------
FACE_VERIFIED = False

# -------------------------------------------------------------
# OPERATION MODES
# -------------------------------------------------------------
#  "active"          → fully awake, listening normally
#  "sleep_wait"      → inactivity countdown running
#  "sleep"           → soft-sleep mode, only wake-word allowed
#  "wake_transition" → waking animation + dialog
#  "processing"      → busy executing command
MODE = "active"

# -------------------------------------------------------------
# LISTENING & SPEAKING FLAGS
# -------------------------------------------------------------
# Public flags used across listener, command handler, speech engine
SYSTEM_LISTENING = False        # microphone actively recording speech
SYSTEM_SPEAKING = False         # TTS speaking (listener should pause)

# Backward compatibility for older modules
LISTENING = False               # alias → avoid breaking older imports

# Wake-word availability
WAKE_WORD_ENABLED = True

# -------------------------------------------------------------
# TIMESTAMPS
# -------------------------------------------------------------
LAST_INTERACTION = None

# Duration (in seconds) before entering sleep mode
INACTIVITY_TIMEOUT = 120

# -------------------------------------------------------------
# EMOTION + CONTEXT
# -------------------------------------------------------------
USER_TONE = "neutral"       # user emotional tone detected by audio/text
JARVIS_MOOD = "neutral"     # internal mood used by brain & speech_engine
LAST_TOPIC = None           # used for topic continuation in brain

# Continuous conversation flag (Jarvis stays active)
CONVERSATION_ACTIVE = False
