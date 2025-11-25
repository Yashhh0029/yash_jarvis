# core/sleep_manager.py

import threading
import time
import random
import core.state as state
from core.speech_engine import speak
import core.voice_effects as fx
from core.brain import brain

# Optional emotion module
try:
    from core.face_emotion import FaceEmotionAnalyzer
except:
    FaceEmotionAnalyzer = None


# ---------------------------------------------------------
# FRIENDLY SLEEP LINES
# ---------------------------------------------------------
SLEEP_LINES = [
    "I’m feeling a little tired… going to sleep now, Yash. Call me if you need me.",
    "Resting for a bit. Just say ‘Hey Jarvis’ to wake me.",
    "Going into sleep mode. I’ll be right here.",
    "Powering down softly… wake me anytime.",
]

# two-minute timeout
SLEEP_TIMEOUT = 120  
def _do_sleep_procedure(overlay=None):

    if state.MODE == "sleep":
        return
    
    state.MODE = "sleep"
    print("💤 Jarvis entering sleep mode...")

    # Soft friendly line
    try:
        speak(random.choice(SLEEP_LINES), mood="neutral", mute_ambient=True)
    except:
        pass

    # Fade out ambient audio
    try:
        fx.jarvis_fx.fade_out_ambient(800)
    except:
        pass

    # UI dim
    try:
        if overlay:
            overlay.set_status("Sleeping…")
            overlay.set_mood("neutral")
            overlay.setWindowOpacity(0.35)
    except:
        pass

    # Stop SFX
    try:
        fx.jarvis_fx.stop_all()
    except:
        pass
def _do_wake_procedure(overlay=None):
    print("⚡ Jarvis waking up...")
    state.MODE = "wake_transition"

    # wake chime
    try:
        fx.jarvis_fx.play_success()
        fx.jarvis_fx.play_ambient()
    except:
        pass

    time.sleep(0.2)

    # Optional face-emotion
    face_mood = None
    if FaceEmotionAnalyzer is not None:
        try:
            fe = FaceEmotionAnalyzer()
            face_mood = fe.capture_emotion()
        except:
            face_mood = None

    # Fuse emotions
    try:
        mood = brain.fuse_emotions(face=face_mood)
    except:
        mood = "neutral"

    state.JARVIS_MOOD = mood

    # Cinematic wake line
    try:
        line = brain.generate_wakeup_line(
            mood=mood,
            last_topic=state.LAST_TOPIC
        )
        speak(line, mood=mood, mute_ambient=True)
    except:
        speak("I'm awake now, Yash.", mood="neutral")

    # Restore UI brightness
    try:
        if overlay:
            overlay.setWindowOpacity(1.0)
            overlay.set_status("Ready")
            overlay.set_mood(mood)
    except:
        pass

    state.MODE = "active"
    state.LAST_INTERACTION = time.time()
class SleepManager:
    def __init__(self):
        self.running = False
        self.overlay = None     # UI reference

    def attach_overlay(self, overlay):
        self.overlay = overlay

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                last = state.LAST_INTERACTION
                mode = state.MODE

                if last is None:  # no interaction yet
                    time.sleep(1)
                    continue

                if mode == "sleep":
                    time.sleep(1)
                    continue

                idle = time.time() - last

                if idle >= SLEEP_TIMEOUT:
                    _do_sleep_procedure(self.overlay)

                time.sleep(1)

            except:
                time.sleep(1)


manager = SleepManager()


def start_manager(overlay=None):
    try:
        if overlay:
            manager.attach_overlay(overlay)
        manager.start()
    except:
        pass
