# PART 1/4 — core/listener.py
# Single-mic background listener (stable, debounced wake-word, continuous active mode)
# Paste Part 1, then request Part 2.

import speech_recognition as sr
import threading
import time
import random
import webbrowser
import os
import pyautogui
import pygetwindow as gw
import keyboard
import traceback
from queue import Queue, Empty
from typing import Optional

# Local kit
from core.speech_engine import speak
from core.voice_effects import JarvisEffects
from core.command_handler import JarvisCommandHandler
from core.memory_engine import JarvisMemory

# Brain/sleep/state hooks (best-effort imports; code should tolerate missing modules)
try:
    import core.brain as brain_module
except Exception:
    brain_module = None

try:
    import core.sleep_manager as sleep_manager
except Exception:
    sleep_manager = None

try:
    import core.state as state
except Exception:
    state = type("S", (), {})()  # dummy object to avoid crashes

try:
    import core.voice_effects as voice_effects
except Exception:
    voice_effects = None

# singletons used by listener
jarvis_fx = JarvisEffects() if 'JarvisEffects' in globals() else None
memory = JarvisMemory()
handler = JarvisCommandHandler()

# If jarvis_fx creation failed above (because JarvisEffects import failed), ensure we have a no-op
if jarvis_fx is None:
    class _NoFx:
        def play_listening(self): pass
        def play_success(self): pass
        def play_ambient(self): pass
        def typing_effect(self): pass
    jarvis_fx = _NoFx()

# Helper: face verification check (best-effort)
def is_face_verified() -> bool:
    try:
        return bool(getattr(state, "FACE_VERIFIED", False))
    except Exception:
        return False

# App quick-launch table (Windows-style commands; adjust if using different OS)
APP_COMMANDS = {
    "notepad": lambda: os.system("start notepad"),
    "calculator": lambda: os.system("start calc"),
    "chrome": lambda: os.system("start chrome"),
    "edge": lambda: os.system("start msedge"),
    "vscode": lambda: os.system("code"),
    "code": lambda: os.system("code"),
    "spotify": lambda: webbrowser.open("https://open.spotify.com"),
}

PLATFORM_SEARCH_URLS = {
    "flipkart": "https://www.flipkart.com/search?q={q}",
    "amazon": "https://www.amazon.in/s?k={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}"
}

# Tuning
_WAKE_WORDS = [
    "hey jarvis", "ok jarvis", "okay jarvis",
    "hi jarvis", "hello jarvis", "jarvis",
    "jarvis bolo", "jarvis haan"
]

_WAKE_TIMEOUT = 5
_WAKE_PHRASE_TIME_LIMIT = 3

_ACTIVE_TIMEOUT = 8
_ACTIVE_PHRASE_TIME_LIMIT = 10

_DEFAULTS = {
    "energy_threshold": 300,
    "dynamic_energy_threshold": True,
    "pause_threshold": 0.6,
    "non_speaking_duration": 0.3,
}

# Active-mode inactivity (seconds) before listener returns to wake-word only
ACTIVE_INACTIVITY_DEFAULT = 20

class JarvisListener:
    """
    Single-microphone background listener using recognizer.listen_in_background.
    - Keeps a single microphone context open (avoids context-manager assertion)
    - Pushes audio chunks to a queue handled by a single consumer thread
    - Debounces repeated wake fragments ("jar jar jar")
    - Provides continuous active mode until inactivity timeout
    """
    def __init__(self, active_inactivity_timeout: int = ACTIVE_INACTIVITY_DEFAULT):
        print("🎙 Initializing Jarvis Listener (Google STT — single-mic)...")
        self.recognizer = sr.Recognizer()
        self._init_recognizer_defaults()

        # single Microphone object used for listen_in_background
        try:
            self.microphone = sr.Microphone()
        except Exception as e:
            print("⚠️ Microphone init failed:", e)
            raise

        # synchronization & state
        self._lock = threading.RLock()
        self._active_mode_lock = threading.RLock()
        self.running = True

        # active-mode control
        self.active_mode = False
        self.listening = False
        self.active_inactivity_timeout = int(active_inactivity_timeout)
        self._last_active_command_ts = 0.0

        # speaking flag to avoid TTS self-pickup
        self._is_speaking = False
        self._speak_lock = threading.Lock()

        # debounce wake
        self._last_wake_ts = 0.0
        self._wake_debounce_seconds = 1.0

        # audio queue from background callback
        self._audio_queue: "Queue[Optional[sr.AudioData]]" = Queue(maxsize=30)

        # background listener handle
        self._bg_stop_fn = None

        # consumer thread for processing queued audio
        self._consumer_thread = threading.Thread(target=self._audio_consumer_loop, daemon=True, name="JarvisAudioConsumer")
        self._consumer_thread.start()

        # ensure state.SYSTEM_SPEAKING exists
        try:
            setattr(state, "SYSTEM_SPEAKING", bool(getattr(state, "SYSTEM_SPEAKING", False)))
        except Exception:
            pass

        print("✅ Microphone ready — starting background listener and waiting for wake word.")

        # best-effort start of sleep manager
        try:
            if sleep_manager and hasattr(sleep_manager, "start_manager"):
                sleep_manager.start_manager()
        except Exception:
            print("⚠️ sleep_manager.start_manager() failed (ignored).")

        # start background listening (keeps mic context open)
        try:
            self._bg_stop_fn = self.recognizer.listen_in_background(
                self.microphone,
                self._background_callback,
                phrase_time_limit=_WAKE_PHRASE_TIME_LIMIT
            )
        except Exception as e:
            print("⚠️ listen_in_background failed:", e)
            traceback.print_exc()
            self._bg_stop_fn = None

# End of PART 1/4
# PART 2/4 — core/listener.py (continue below Part 1)

    # ---------------- recognizer init & safety ----------------
    def _init_recognizer_defaults(self):
        """Safe microphone/recognizer defaults to avoid SR assertion errors."""
        try:
            self.recognizer.energy_threshold = int(_DEFAULTS["energy_threshold"])
            self.recognizer.dynamic_energy_threshold = bool(_DEFAULTS["dynamic_energy_threshold"])

            pause = float(_DEFAULTS["pause_threshold"])
            non_speaking = float(_DEFAULTS["non_speaking_duration"])
            if pause < non_speaking:
                pause = non_speaking + 0.2

            try:
                self.recognizer.pause_threshold = pause
            except Exception:
                pass

            try:
                setattr(self.recognizer, "non_speaking_duration", non_speaking)
            except Exception:
                pass

            # one-time ambient calibration
            try:
                with sr.Microphone() as src:
                    self.recognizer.adjust_for_ambient_noise(src, duration=1)
            except Exception:
                pass

        except Exception as e:
            print("⚠️ _init_recognizer_defaults failed:", e)
            traceback.print_exc()

    # ---------------- background callback (single mic) ----------------
    def _background_callback(self, recognizer, audio):
        """Called by listen_in_background — push audio to queue."""
        try:
            self._audio_queue.put_nowait(audio)
        except Exception:
            pass  # queue full — drop audio safely

    # ---------------- audio consumer loop ----------------
    def _audio_consumer_loop(self):
        """
        Single consumer thread:
        - Reads audio chunks from queue
        - Converts to text
        - Routes text to wake or active mode
        """
        while self.running:
            try:
                audio = self._audio_queue.get(timeout=0.4)
            except Empty:
                # check inactivity → exit active mode
                if (
                    self.active_mode
                    and time.time() - self._last_active_command_ts > self.active_inactivity_timeout
                ):
                    self._exit_active_mode()
                continue

            # Avoid pickup of TTS output
            if getattr(state, "SYSTEM_SPEAKING", False) or self._is_speaking:
                continue

            text = None
            try:
                text = self._recognize_from_audio(audio)
            except Exception:
                continue

            if not text:
                continue

            normalized = text.lower().strip()
            print(f"🗣 Heard: {normalized}")

            # ACTIVE MODE = directly process commands
            if self.active_mode:
                self._last_active_command_ts = time.time()
                try:
                    self._process_command(normalized)
                except Exception as e:
                    print("⚠️ active command error:", e)
                continue

            # WAKE MODE
            if any(w in normalized for w in _WAKE_WORDS):
                now = time.time()
                if now - self._last_wake_ts < self._wake_debounce_seconds:
                    continue
                self._last_wake_ts = now

                cleaned = normalized
                for w in _WAKE_WORDS:
                    cleaned = cleaned.replace(w, "").strip()

                # if system sleeping → wake
                if getattr(state, "MODE", "active") == "sleep":
                    try:
                        self._wake_from_sleep()
                    except Exception:
                        pass
                    time.sleep(0.12)

                # start active-mode in thread
                threading.Thread(
                    target=self._enter_active_command_mode,
                    args=(cleaned,),
                    daemon=True,
                ).start()

    # ---------------- recognition wrapper ----------------
    def _recognize_from_audio(self, audio, retries=1):
        if not audio:
            return None
        try:
            return self.recognizer.recognize_google(audio).lower().strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print("⚠️ STT RequestError:", e)
            return None
        except Exception:
            if retries > 0:
                time.sleep(0.1)
                return self._recognize_from_audio(audio, retries - 1)
            return None

    # ---------------- active mode entry ----------------
    def _enter_active_command_mode(self, initial_command=None):
        # ensure only one active-mode thread
        with self._active_mode_lock:
            if self.active_mode:
                if initial_command:
                    try:
                        self._process_command(initial_command)
                    except Exception:
                        pass
                return
            self.active_mode = True
            self.listening = True
            self._last_active_command_ts = time.time()

        # prevent sleep reset
        try:
            state.LAST_INTERACTION = time.time()
        except Exception:
            pass

        # sound fx
        try:
            jarvis_fx.play_listening()
        except Exception:
            pass

        # wake-up line
        try:
            mood = memory.get_mood()
            last_topic = getattr(state, "LAST_TOPIC", None)
            if is_face_verified():
                if brain_module and hasattr(brain_module.brain, "generate_wakeup_line"):
                    speak(brain_module.brain.generate_wakeup_line(mood, last_topic), mood)
                else:
                    speak("Yes Yash, I’m listening.", mood)
            else:
                speak("Limited mode active. Your face wasn’t verified earlier.", "neutral")
        except Exception:
            speak("Yes Yash, I’m here.", "neutral")

        # Initial embedded command after wake phrase
        if initial_command:
            try:
                self._process_command(initial_command)
            except Exception:
                pass

        # Loop until inactivity triggers exit (handled by consumer thread)
        while self.active_mode and self.running:
            time.sleep(0.3)

        # exiting active mode
        with self._active_mode_lock:
            self.listening = False
            self.active_mode = False
            try:
                state.LAST_INTERACTION = time.time()
            except:
                pass

    # ---------------- active exit ----------------
    def _exit_active_mode(self):
        with self._active_mode_lock:
            if not self.active_mode:
                return
            self.listening = False
            self.active_mode = False
            try:
                state.LAST_INTERACTION = time.time()
            except:
                pass

# END OF PART 2/4
# PART 3/4 — core/listener.py (continue below Part 2)

    # -------------------------------------------------------
    # PROCESS COMMAND (core unified handler)
    def _process_command(self, command):
        if not command:
            speak("Sorry, I didn’t catch that.", mood="neutral")
            return

        if getattr(state, "MODE", "active") == "sleep":
            speak("Say ‘Hey Jarvis’ to wake me completely.", mood="neutral")
            return

        print(f"📡 Command: {command}")
        cmd_lower = command.lower().strip()

        # ------------------- SEARCH -------------------
        if any(k in cmd_lower for k in ["search", "find", "look up", "dhund", "search kar"]):
            try:
                self._handle_search(cmd_lower)
            except Exception as e:
                print("⚠️ search error:", e)
                speak("I couldn't search that, Yash.", mood="neutral")
            return

        # ------------------- TYPING -------------------
        if any(k in cmd_lower for k in ["type", "type this", "type that", "type message", "type kar"]):
            text = cmd_lower
            for kw in ["type this", "type that", "type message", "type", "type kar"]:
                text = text.replace(kw, "").strip()
            if not text:
                speak("What should I type?", mood="neutral")
                text = self._listen_for_short_text()
            if text:
                self._auto_type_text(text)
            return

        # ------------------- TABS -------------------
        if any(k in cmd_lower for k in ["new tab", "open tab", "close tab",
                                        "next tab", "previous tab", "prev tab", "switch tab"]):
            self._handle_tab_command(cmd_lower)
            return

        # ------------------- APP OPEN -------------------
        if cmd_lower.startswith("open ") or cmd_lower.startswith("launch "):
            self._handle_open(cmd_lower)
            return

        # ------------------- MEDIA -------------------
        if any(k in cmd_lower for k in ["play", "pause", "volume up", "volume down", "mute"]):
            self._handle_media(cmd_lower)
            return

        # ------------------- AI HANDLER -------------------
        try:
            handler.process(command)
        except Exception as e:
            print("⚠️ handler error:", e)
            speak("I couldn't do that, Yash.", mood="neutral")

    # -------------------------------------------------------
    # AUTO TYPE
    def _auto_type_text(self, text):
        try:
            speak(f"Typing: {text}", mood="neutral")
            active = gw.getActiveWindow()

            if not active:
                pyautogui.click(300, 300)
            else:
                try: active.activate()
                except: pass

            for ch in text:
                pyautogui.write(ch)
                try: jarvis_fx.typing_effect()
                except: pass
                time.sleep(0.03)

            speak("Typed.", mood="happy")

        except Exception as e:
            print("⚠️ typing error:", e)
            speak("I couldn’t type that.", mood="neutral")

    # -------------------------------------------------------
    # SMALL TEXT LISTENER (use queue)
    def _listen_for_short_text(self, timeout=6):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                audio = self._audio_queue.get(timeout=0.5)
            except Empty:
                continue

            text = self._recognize_from_audio(audio)
            if text:
                return text
        return None

    # -------------------------------------------------------
    # SEARCH HANDLER
    def _handle_search(self, command):
        try:
            original = command
            query = command

            # strip keywords
            for k in ["search", "find", "look up", "dhund", "search kar",
                      "on youtube", "on google", "on flipkart", "on amazon", "on bing"]:
                query = query.replace(k, "")
            query = query.strip()

            platform = None
            for p in PLATFORM_SEARCH_URLS.keys():
                if p in original:
                    platform = p
                    break

            if not query:
                speak("What should I search?", mood="neutral")
                query = self._listen_for_short_text()
                if not query:
                    speak("Search cancelled.", mood="neutral")
                    return

            # cool typing effect
            def type_fx(t):
                for ch in t:
                    pyautogui.write(ch)
                    try: jarvis_fx.typing_effect()
                    except: pass
                    time.sleep(0.03)

            # DIRECT PLATFORM SEARCH
            if platform:
                win = self._find_and_activate_window(platform)
                if win:
                    try:
                        wx, wy, ww, wh = win.left, win.top, win.width, win.height
                        pyautogui.click(int(wx + ww * 0.5), int(wy + wh * 0.12))
                        time.sleep(0.18)
                        type_fx(query)
                        pyautogui.press("enter")
                        speak(f"Searching {platform} for {query}", mood="happy")
                        return
                    except Exception:
                        pass

                url = PLATFORM_SEARCH_URLS[platform].format(q=query.replace(" ", "+"))
                speak(f"Opening {platform} results for {query}.", mood="happy")
                webbrowser.open_new_tab(url)
                return

            # BROWSER ACTIVE SEARCH
            active = gw.getActiveWindow()
            title = (active.title or "").lower() if active else ""

            # YouTube direct-search
            if "youtube" in title:
                try:
                    pyautogui.press("/")
                    time.sleep(0.12)
                    type_fx(query)
                    pyautogui.press("enter")
                    speak(f"Searching YouTube for {query}", mood="happy")
                    return
                except Exception:
                    pass

            # Google search in browser
            if any(b in title for b in ["chrome", "edge", "firefox", "brave", "msedge"]):
                try:
                    speak(f"Searching Google for {query}", mood="happy")
                    pyautogui.hotkey("ctrl", "l")
                    time.sleep(0.08)
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.press("backspace")
                    type_fx(query)
                    pyautogui.press("enter")
                    return
                except Exception:
                    pass

            # fallback universal click search
            if active:
                try:
                    wx, wy, ww, wh = active.left, active.top, active.width, active.height
                    pyautogui.click(int(wx + ww * 0.5), int(wy + wh * 0.12))
                    time.sleep(0.12)
                    type_fx(query)
                    pyautogui.press("enter")
                    speak("Searching.", mood="happy")
                    return
                except Exception:
                    pass

            # Final fallback — web search
            speak(f"Searching Google for {query}.", mood="happy")
            webbrowser.open_new_tab(PLATFORM_SEARCH_URLS["google"].format(q=query.replace(" ", "+")))

        except Exception as e:
            print("⚠️ Search Error:", e)
            speak("Couldn't search that, Yash.", mood="neutral")
# PART 4/4 — FINAL SECTION OF core/listener.py

    # -------------------------------------------------------
    # FIND WINDOW BY KEYWORD
    def _find_and_activate_window(self, keyword):
        try:
            keyword = keyword.lower()
            for w in gw.getAllWindows():
                title = (w.title or "").lower()
                if keyword in title:
                    try:
                        w.activate()
                        time.sleep(0.18)
                        return w
                    except:
                        continue
        except Exception as e:
            print("⚠️ Window activation error:", e)
        return None

    # -------------------------------------------------------
    # TAB CONTROL
    def _handle_tab_command(self, cmd):
        try:
            cmd = cmd.lower()

            if "new" in cmd or "open" in cmd:
                speak("Opening new tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "t")
                return

            if "close" in cmd:
                speak("Closing tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "w")
                return

            if "next" in cmd:
                speak("Next tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "tab")
                return

            if "previous" in cmd or "prev" in cmd:
                speak("Previous tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "shift", "tab")
                return

        except Exception as e:
            print("⚠️ Tab error:", e)
            speak("Couldn't change tabs.", mood="neutral")

    # -------------------------------------------------------
    # OPEN APPLICATIONS
    def _handle_open(self, command):
        try:
            words = command.lower().replace("open ", "").replace("launch ", "").strip()

            # Direct platforms
            if "youtube" in words:
                speak("Opening YouTube.", mood="happy")
                webbrowser.open_new_tab("https://www.youtube.com")
                return

            if "google" in words:
                speak("Opening Google.", mood="happy")
                webbrowser.open_new_tab("https://www.google.com")
                return

            # Local apps
            for app, fn in APP_COMMANDS.items():
                if app in words:
                    speak(f"Opening {app}.", mood="neutral")
                    fn()
                    return

            # URLs
            if "." in words:
                if not words.startswith("http"):
                    words = "https://" + words
                speak(f"Opening {words}.", mood="happy")
                webbrowser.open_new_tab(words)
                return

            # fallback: Google search
            speak(f"Searching {words}.", mood="neutral")
            webbrowser.open_new_tab(f"https://www.google.com/search?q={words}")

        except Exception as e:
            print("⚠️ Open error:", e)
            speak("Couldn't open that.", mood="neutral")

    # -------------------------------------------------------
    # MEDIA CONTROLS
    def _handle_media(self, command):
        try:
            cmd = command.lower()

            if "play" in cmd or "pause" in cmd:
                keyboard.send("play/pause media")
                speak("Done.", mood="neutral")
                return

            if "volume up" in cmd:
                keyboard.send("volume up")
                speak("Volume up.", mood="neutral")
                return

            if "volume down" in cmd:
                keyboard.send("volume down")
                speak("Volume down.", mood="neutral")
                return

            if "mute" in cmd:
                keyboard.send("volume mute")
                speak("Muted.", mood="neutral")
                return

        except Exception as e:
            print("⚠️ Media error:", e)
            speak("Media control failed.", mood="neutral")

    # -------------------------------------------------------
    # WAKE FROM SLEEP (overlay + brain-line)
    def _wake_from_sleep(self):
        try:
            if getattr(state, "MODE", None) != "sleep":
                return

            # Smooth wake effect
            try:
                jarvis_fx.play_success()
            except:
                pass

            mood = memory.get_mood()
            try:
                line = brain_module.brain.generate_wakeup_line(mood=mood, last_topic=state.LAST_TOPIC)
            except:
                line = "I'm awake."

            speak(line, mood=mood)

            # overlay update
            try:
                ov = getattr(voice_effects, "overlay_instance", None)
                if ov:
                    ov.set_status("Listening…")
                    ov.set_mood(mood)
                    ov.setWindowOpacity(1.0)
            except:
                pass

            state.MODE = "active"
            state.LAST_INTERACTION = time.time()

        except Exception as e:
            print("⚠️ Wake error:", e)

    # -------------------------------------------------------
    # RETURN OVERLAY INSTANCE
    def _get_overlay_if_available(self):
        try:
            return getattr(voice_effects, "overlay_instance", None)
        except:
            return None

    # -------------------------------------------------------
    # SET SPEAKING STATE
    def set_speaking(self, speaking: bool):
        try:
            self._is_speaking = speaking
            state.SYSTEM_SPEAKING = speaking

            base = int(_DEFAULTS["energy_threshold"])
            if speaking:
                self.recognizer.energy_threshold = base * 3
            else:
                self.recognizer.energy_threshold = base
        except:
            pass

    # -------------------------------------------------------
    # STOP LISTENER
    def stop(self):
        print("🛑 Listener stopping...")
        self.running = False

        try:
            if self._bg_stop_fn:
                try: self._bg_stop_fn(wait_for_stop=False)
                except: self._bg_stop_fn()
        except:
            pass

        try:
            self._consumer_thread.join(timeout=1)
        except:
            pass

        print("🛑 Listener stopped.")

# -------------------------------------------------------
# MAIN RUNNER
if __name__ == "__main__":
    L = JarvisListener()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        L.stop()
