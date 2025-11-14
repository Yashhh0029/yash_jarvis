# ============================================================
#   JARVIS CINEMATIC SOUND ENGINE — STABLE & ENHANCED EDITION
# ============================================================
import os
import pygame
import threading
import time
import random

os.environ.setdefault("SDL_AUDIODRIVER", "directsound")

# Overlay reference
overlay_instance = None


def attach_overlay(overlay):
    """Attach the InterfaceOverlay instance safely."""
    global overlay_instance
    overlay_instance = overlay
    print("🌀 Overlay successfully linked with Jarvis voice system.")


class JarvisEffects:
    """Cinematic Jarvis sound system (serious tone removed, smoother typewriter)."""

    CHANNEL_SFX = 1
    CHANNEL_AMBIENT = 2
    CHANNEL_UI = 3  # typing / UI pings

    def __init__(self):
        self.sounds_path = os.path.join(os.path.dirname(__file__), "sounds")
        self._safe_init_mixer()
        self._ambient_sound = None
        self._ambient_lock = threading.Lock()
        print("🎵 Jarvis Cinematic Sound Engine Ready")

    # --------------------------------------------------------
    # MIXER INITIALIZATION
    # --------------------------------------------------------
    def _safe_init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                pygame.mixer.set_num_channels(12)
            else:
                pygame.mixer.set_num_channels(max(12, pygame.mixer.get_num_channels()))
        except Exception as e:
            print(f"⚠️ Mixer init failed: {e}")
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
                pygame.mixer.set_num_channels(12)
            except Exception as e2:
                print(f"❌ Mixer recovery failed: {e2}")

    # --------------------------------------------------------
    # FILE LOADER
    # --------------------------------------------------------
    def _load_sound(self, filename):
        path = os.path.join(self.sounds_path, filename)
        if not os.path.exists(path):
            print(f"⚠️ Missing sound file: {path}")
            return None
        try:
            return pygame.mixer.Sound(path)
        except Exception as e:
            print(f"⚠️ Failed to load sound {path}: {e}")
            return None

    def _get_channel(self, idx):
        self._safe_init_mixer()
        if idx >= pygame.mixer.get_num_channels():
            pygame.mixer.set_num_channels(idx + 4)
        return pygame.mixer.Channel(idx)

    # --------------------------------------------------------
    # INTERNAL PLAYBACK
    # --------------------------------------------------------
    def _play_on_channel(self, channel_idx, sound_obj, loop=False, limit=None, volume=1.0):
        if sound_obj is None:
            return

        def runner():
            try:
                ch = self._get_channel(channel_idx)
                if not ch:
                    return

                ch.set_volume(volume)
                ch.play(sound_obj, loops=(-1 if loop else 0))

                if overlay_instance:
                    try:
                        overlay_instance.react_to_audio(volume)
                    except:
                        pass

                if limit:
                    time.sleep(limit)
                    ch.fadeout(600)

            except Exception as e:
                print(f"⚠️ Playback error: {e}")

        threading.Thread(target=runner, daemon=True).start()

    # --------------------------------------------------------
    # PUBLIC SOUND FUNCTIONS
    # --------------------------------------------------------
    def _play_sound(self, name, channel=None, loop=False, limit=None, volume=1.0):
        snd = self._load_sound(name)
        if snd:
            self._play_on_channel(channel, snd, loop=loop, limit=limit, volume=volume)

    def play_ack(self):
        self._play_sound("ack.mp3", channel=self.CHANNEL_UI, limit=0.8, volume=0.9)

    def play_startup(self, short=False):
        dur = 2 if short else 5
        self._play_sound("startup_sequence.mp3", channel=self.CHANNEL_SFX, limit=dur)
        # Optional overlay animation during boot
        if overlay_instance:
            try:
                for i in range(5):
                    overlay_instance.react_to_audio(1.0)
                    time.sleep(0.4)
                    overlay_instance.react_to_audio(0.2)
                    time.sleep(0.25)
            except:
                pass

    def play_alert(self):
        self._play_sound("alert_warning.mp3", channel=self.CHANNEL_SFX)

    def play_success(self):
        self._play_sound("task_complete.mp3", channel=self.CHANNEL_SFX)

    def play_listening(self):
        self._play_sound("listening_mode.mp3", channel=self.CHANNEL_UI)

    # --------------------------------------------------------
    # AMBIENT BACKGROUND
    # --------------------------------------------------------
    def play_ambient(self):
        with self._ambient_lock:
            if not self._ambient_sound:
                self._ambient_sound = self._load_sound("ambient_background.mp3")
            if not self._ambient_sound:
                return

            ch = self._get_channel(self.CHANNEL_AMBIENT)
            if not ch.get_busy():
                ch.play(self._ambient_sound, loops=-1)
                ch.set_volume(0.4)

    def fade_out_ambient(self, ms=1000):
        try:
            ch = self._get_channel(self.CHANNEL_AMBIENT)
            ch.fadeout(ms)
        except:
            pass

    # --------------------------------------------------------
    # TYPEWRITER EFFECT (Enhanced realism)
    # --------------------------------------------------------
    def typing_effect(self, duration=0.12):
        """Play a random-soft click per keystroke."""
        try:
            vol = random.uniform(0.35, 0.45)
            self._play_sound("type_click.mp3", channel=self.CHANNEL_UI, limit=duration, volume=vol)
        except Exception as e:
            print(f"⚠️ Typing effect failed: {e}")

    # --------------------------------------------------------
    # MOOD TONES (NO SERIOUS TONE)
    # --------------------------------------------------------
    def mood_tone(self, mood):
        mood = (mood or "").lower()

        if mood == "alert":
            self.play_alert()
        elif mood == "happy":
            self.play_success()
        elif mood == "listening":
            self.play_listening()
        # serious tone removed intentionally

    # --------------------------------------------------------
    # STOP ALL SOUNDS
    # --------------------------------------------------------
    def stop_all(self):
        try:
            for i in range(12):
                ch = self._get_channel(i)
                if ch:
                    ch.stop()
        except:
            pass
