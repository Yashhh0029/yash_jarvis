# core/music_player.py
"""
High-tech local music player for Jarvis.

Features:
- Play / pause / resume / stop.
- Playlist support and simple next/prev.
- Crossfade (soft) using pygame mixer fadeout.
- Integrates with overlay_instance for UI react.
- Emits short TTS confirmations.
"""

import os
import time
import threading
import pygame
from typing import Optional, List
from core.speech_engine import speak
from core.voice_effects import overlay_instance

# init mixer safely
try:
    pygame.mixer.init()
except Exception:
    try:
        pygame.mixer.quit()
        pygame.mixer.init()
    except:
        pass

class MusicPlayer:
    def __init__(self):
        self.playlist: List[str] = []
        self.index = 0
        self.lock = threading.Lock()
        self._paused = False

    def load(self, paths: List[str]):
        self.playlist = [p for p in paths if os.path.exists(p)]
        self.index = 0

    def play(self, path: Optional[str] = None):
        with self.lock:
            if path:
                if not os.path.exists(path):
                    speak("I couldn't find that song.", mood="alert")
                    return
                self.playlist = [path]
                self.index = 0
            if not self.playlist:
                speak("Your playlist is empty.", mood="alert")
                return
            current = self.playlist[self.index]
            try:
                pygame.mixer.music.load(current)
                pygame.mixer.music.play()
                self._paused = False
                speak(f"Playing {os.path.basename(current)}", mood="happy")
                if overlay_instance:
                    overlay_instance.react_to_audio(1.0)
            except Exception as e:
                print("Music play error:", e)
                speak("Couldn't play the track.", mood="alert")

    def pause(self):
        try:
            pygame.mixer.music.pause()
            self._paused = True
            speak("Paused.", mood="neutral")
        except Exception:
            pass

    def resume(self):
        try:
            pygame.mixer.music.unpause()
            self._paused = False
            speak("Resuming.", mood="happy")
        except Exception:
            pass

    def stop(self, fade_ms: int = 300):
        try:
            pygame.mixer.music.fadeout(fade_ms)
            time.sleep(fade_ms / 1000.0)
            self._paused = False
            speak("Stopped playback.", mood="neutral")
        except Exception:
            pass

    def next(self):
        with self.lock:
            if not self.playlist:
                return
            self.index = (self.index + 1) % len(self.playlist)
            self.play()

    def previous(self):
        with self.lock:
            if not self.playlist:
                return
            self.index = (self.index - 1) % len(self.playlist)
            self.play()

    def set_volume(self, v: float):
        try:
            v = max(0.0, min(1.0, v))
            pygame.mixer.music.set_volume(v)
            speak(f"Volume set to {int(v*100)} percent.", mood="neutral")
        except Exception:
            pass


# singleton
music_player = MusicPlayer()
