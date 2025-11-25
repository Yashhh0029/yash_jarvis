# core/speech_engine.py
import os
import asyncio
import tempfile
import pygame
import pyttsx3
import threading
import time

try:
    import edge_tts
except Exception:
    edge_tts = None

from core.voice_effects import JarvisEffects
import core.voice_effects as fx
import core.state as state     # <-- NEW: mic-mute integration

jarvis_fx = JarvisEffects()


# ---------------- LISTENER HOOK FOR MIC CONTROL ----------------
LISTENER_HOOK = None

def register_listener_hook(fn):
    """
    Listener will call register_listener_hook(self.set_speaking)
    so speech engine can mute/unmute mic properly.
    """
    global LISTENER_HOOK
    LISTENER_HOOK = fn


# ---------------- MIXER ----------------
class StableMixer:
    """Stable mixer with dedicated channels."""

    VOICE = 0
    SFX = 1
    AMBIENT = 2

    @staticmethod
    def init():
        try:
            pygame.mixer.quit()
            time.sleep(0.05)
        except:
            pass

        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(8)

        StableMixer.voice = pygame.mixer.Channel(StableMixer.VOICE)
        StableMixer.sfx = pygame.mixer.Channel(StableMixer.SFX)
        StableMixer.ambient = pygame.mixer.Channel(StableMixer.AMBIENT)

        print("🔊 Stable Mixer initialized (3-channel mode)")


StableMixer.init()


# ---------------- TTS ENGINE ----------------
class JarvisVoice:
    """Handles neural Edge TTS + pyttsx3 fallback + overlay animations."""

    def __init__(self):
        self.offline_engine = pyttsx3.init()
        self.offline_engine.setProperty("rate", 175)
        self.offline_engine.setProperty("volume", 1.0)
        self.offline_engine.setProperty("voice", self._get_voice("male"))

        self.online_enabled = edge_tts is not None
        self.lock = threading.Lock()

        print("🎧 Jarvis Voice Engine Ready")

    # ---------------------- VOICE PICK ----------------------
    def _get_voice(self, gender):
        voices = self.offline_engine.getProperty("voices")
        for v in voices:
            if gender.lower() in v.name.lower():
                return v.id
        return voices[0].id

    # ---------------------- EDGE TTS ------------------------
    async def _play_edge_tts(self, text):
        tmp_path = None
        try:
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            StableMixer.voice.stop()
            StableMixer.voice.play(pygame.mixer.Sound(tmp_path))

            if fx.overlay_instance:
                fx.overlay_instance.react_to_audio(1.1)

            while StableMixer.voice.get_busy():
                time.sleep(0.05)

            if fx.overlay_instance:
                fx.overlay_instance.react_to_audio(0.2)

            os.remove(tmp_path)
            return True

        except Exception as e:
            print(f"⚠️ Edge-TTS playback error: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ---------------------- OFFLINE -------------------------
    def _speak_offline(self, text):
        try:
            if fx.overlay_instance:
                fx.overlay_instance.react_to_audio(1.0)

            self.offline_engine.say(text)
            self.offline_engine.runAndWait()

            if fx.overlay_instance:
                fx.overlay_instance.react_to_audio(0.2)

        except Exception as e:
            print(f"⚠️ Offline TTS error: {e}")

    # ---------------------- MAIN SPEAK ----------------------
    def speak(self, text, allow_fallback=True):
        if not text or not text.strip():
            return

        with self.lock:
            StableMixer.voice.stop()
            StableMixer.sfx.stop()

            # 🔇 Tell listener to stop listening
            state.SYSTEM_SPEAKING = True
            try:
                if LISTENER_HOOK:
                    LISTENER_HOOK(True)
            except:
                pass

            try:
                # Prefer neural TTS
                if self.online_enabled:
                    ok = self._run_async(self._play_edge_tts(text))
                    if ok:
                        return

                # Fallback offline
                self._speak_offline(text)

            finally:
                time.sleep(0.05)

                # 🎤 Re-enable microphone
                state.SYSTEM_SPEAKING = False
                try:
                    if LISTENER_HOOK:
                        LISTENER_HOOK(False)
                except:
                    pass


# GLOBAL INSTANCE
jarvis_voice = JarvisVoice()


# ---------------- PUBLIC SPEAK FUNCTION ----------------
def speak(text, mood="neutral", mute_ambient=True):
    if not text or not text.strip():
        return

    try:
        # Stop ambience during speech
        if mute_ambient:
            StableMixer.ambient.stop()

        # Small mood tone
        try:
            jarvis_fx.mood_tone(mood)
        except:
            pass

        if fx.overlay_instance:
            fx.overlay_instance.react_to_audio(0.8)

        time.sleep(0.20)

        jarvis_voice.speak(text)

        # After-speech calm
        if fx.overlay_instance:
            fx.overlay_instance.react_to_audio(0.15)

    except Exception as e:
        print(f"⚠️ Speak error: {e}")


# ---------------- CINEMATIC STARTUP ----------------
def play_boot_sequence():
    try:
        jarvis_fx.stop_all()
        StableMixer.sfx.stop()

        boot_sound = pygame.mixer.Sound(os.path.join("assets", "audio", "startup_long.wav"))
        StableMixer.sfx.play(boot_sound)

        if fx.overlay_instance:
            for _ in range(6):
                fx.overlay_instance.react_to_audio(1.3)
                time.sleep(0.4)
                fx.overlay_instance.react_to_audio(0.3)
                time.sleep(0.3)

    except Exception as e:
        print(f"⚠️ Boot sequence failed: {e}")
