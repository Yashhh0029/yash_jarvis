
# core/listener.py — TYPEWRITER + stable listener (final)
import speech_recognition as sr
import threading
import time
import random
import webbrowser
import os
import pyautogui
import pygetwindow as gw
import keyboard

from core.speech_engine import speak
from core.voice_effects import JarvisEffects
from core.command_handler import JarvisCommandHandler
from core.memory_engine import JarvisMemory

import core.state as state

jarvis_fx = JarvisEffects()
memory = JarvisMemory()
handler = JarvisCommandHandler()

def is_face_verified():
    try:
        return bool(state.FACE_VERIFIED)
    except:
        return False

APP_COMMANDS = {
    "notepad": lambda: os.system("start notepad"),
    "calculator": lambda: os.system("start calc"),
    "chrome": lambda: os.system("start chrome"),
    "edge": lambda: os.system("start msedge"),
    "vscode": lambda: os.system("code"),
    "code": lambda: os.system("code"),
    "spotify": lambda: webbrowser.open("https://open.spotify.com"),
}

class JarvisListener:
    def __init__(self):
        print("🎙 Initializing Jarvis Listener (Google STT)...")
        self.recognizer = sr.Recognizer()
        try:
            self.microphone = sr.Microphone()
        except Exception as e:
            print("⚠️ Microphone init failed:", e)
            raise

        self.listening = False
        self.running = True

        with self.microphone as source:
            print("🎧 Calibrating microphone (1s)...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            except:
                pass

        print("✅ Microphone ready — waiting for wake word.")
        threading.Thread(target=self._continuous_listen, daemon=True).start()

    def _continuous_listen(self):
        wake_words = [
            "hey jarvis","ok jarvis","okay jarvis",
            "hi jarvis","hello jarvis","jarvis",
            "jarvis bolo","jarvis haan"
        ]

        while self.running:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=4)

                text = self._recognize_speech(audio)
                if not text:
                    continue

                print(f"🗣 Heard: {text}")

                if any(w in text for w in wake_words):
                    cleaned = text
                    for w in wake_words:
                        cleaned = cleaned.replace(w, "").strip()
                    self._activate_jarvis(initial_command=cleaned)

            except:
                time.sleep(0.4)

    def _recognize_speech(self, audio):
        try:
            return self.recognizer.recognize_google(audio).lower().strip()
        except:
            return None

    def _activate_jarvis(self, initial_command=None):
        if self.listening:
            return

        self.listening = True
        print("\n🎯 Hotword detected — activating Jarvis...\n")

        try:
            jarvis_fx.play_listening()
        except:
            pass

        if not is_face_verified():
            speak("Limited mode active. Your face wasn't verified earlier.", mood="neutral")
        else:
            mood = memory.get_mood()
            responses = {
                "happy": ["Yes Yash, I'm listening!", "Hey Yashu, what's up?", "I'm here — go on."],
                "serious": ["Yes Yash, ready.", "Listening.", "Go ahead."],
                "neutral": ["Listening Yash.", "Yes, I'm here.", "Go ahead."]
            }
            speak(random.choice(responses.get(mood, responses["neutral"])), mood=mood)

        time.sleep(0.4)

        if initial_command and len(initial_command) > 1:
            self._process_command(initial_command)
            self.listening = False
            return

        try:
            with self.microphone as source:
                print("🎤 Listening for your command...")
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=10)
            command = self._recognize_speech(audio)
            self._process_command(command)
        except:
            speak("I didn't hear anything, Yash.", mood="neutral")

        self.listening = False
        print("🎧 Returning to standby...\n")

    def _process_command(self, command):
        if not command:
            speak("Sorry, I didn't catch that.", mood="neutral")
            return

        print(f"📡 Command: {command}")

        if any(k in command for k in ["search","find","look up","dhund","search kar"]):
            self._handle_search(command)
            return

        if any(k in command for k in ["type","type this","type message","type that","type kar"]):
            text = command
            for p in ["type this","type message","type that","type","type kar"]:
                text = text.replace(p, "").strip()
            if not text:
                speak("What should I type?", mood="neutral")
                text = self._listen_for_short_text()
            if text:
                self._auto_type_text(text)
            return

        if any(k in command for k in ["new tab","open tab","close tab","next tab","previous tab","prev tab","switch tab"]):
            self._handle_tab_command(command)
            return

        if command.startswith("open ") or command.startswith("launch "):
            self._handle_open(command)
            return

        if any(k in command for k in ["play","pause","volume up","volume down","mute"]):
            self._handle_media(command)
            return

        try:
            handler.process(command)
            speak(random.choice(["Done.","Got it.","All set, Yash."]), mood="happy")
        except:
            speak("I couldn't do that, Yash.", mood="neutral")

    def _auto_type_text(self, text):
        try:
            speak(f"Typing: {text}", mood="neutral")
            active = gw.getActiveWindow()
            if active:
                try:
                    active.activate()
                except:
                    pass
            else:
                try:
                    pyautogui.click(300, 300)
                except:
                    pass

            for ch in text:
                pyautogui.write(ch)
                try:
                    jarvis_fx.typing_effect()
                except:
                    pass
                time.sleep(0.03)

            speak("Typed.", mood="happy")
        except:
            speak("I couldn't type that.", mood="neutral")

    def _listen_for_short_text(self, timeout=6):
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=8)
            return self._recognize_speech(audio)
        except:
            return None


    # ---------------- context-aware universal search ----------------
    def _handle_search(self, command):
        """Typewriter search that works on EVERY website search bar."""
        try:
            # clean query
            query = command
            for k in ["search","find","look up","dhund","search kar","on youtube","on google"]:
                query = query.replace(k, "")
            query = query.strip()

            if not query:
                speak("What do you want me to search?", mood="neutral")
                query = self._listen_for_short_text()
                if not query:
                    speak("Cancelled.", mood="neutral")
                    return

            print("🔍 Query:", query)

            active = gw.getActiveWindow()
            active_title = active.title.lower() if active else ""
            print("🌐 Active Window:", active_title)

            # ---------------- TYPEWRITER FX ----------------
            def typewrite_fx(text):
                for ch in text:
                    pyautogui.write(ch)
                    try:
                        jarvis_fx.typing_effect()
                    except:
                        pass
                    time.sleep(0.03)

            # ======================================================================
            # 1️⃣ YOUTUBE SEARCH (native / shortcut '/')
            # ======================================================================
            if "youtube" in active_title:
                speak(f"Searching YouTube for {query}.", mood="happy")
                try:
                    pyautogui.press("/")
                    time.sleep(0.15)
                    typewrite_fx(query)
                    pyautogui.press("enter")
                except:
                    webbrowser.open_new_tab(f"https://www.youtube.com/results?search_query={query}")
                return

            # ======================================================================
            # 2️⃣ UNIVERSAL SEARCH BAR CLICK — works on ANY website  
            #     (Facebook, Amazon, Flipkart, Wikipedia, ANYTHING)
            # ======================================================================
            if active:
                try:
                    # get active window box
                    wx = active.left
                    wy = active.top
                    ww = active.width
                    wh = active.height

                    # click approx where search bars usually exist (top-center)
                    cx = int(wx + ww * 0.50)
                    cy = int(wy + wh * 0.08)   # 8% down from top (universal sweet spot)

                    pyautogui.click(cx, cy)
                    time.sleep(0.20)

                    # try typing directly
                    typewrite_fx(query)
                    pyautogui.press("enter")
                    speak("Searching.", mood="happy")
                    return

                except Exception as e:
                    print("⚠️ Universal click failed:", e)

            # ======================================================================
            # 3️⃣ GOOGLE / BROWSER fallback (address bar typing)
            # ======================================================================
            try:
                speak(f"Searching Google for {query}.", mood="happy")
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
                pyautogui.press("backspace")
                time.sleep(0.08)
                typewrite_fx(query)
                pyautogui.press("enter")
                return

            except Exception as e:
                print("⚠️ Google fallback failed:", e)

            # ======================================================================
            # 4️⃣ FINAL fallback: open new results page
            # ======================================================================
            webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")
            speak("Opened search results.", mood="happy")

        except Exception as e:
            print("⚠️ Search error:", e)
            speak("Couldn't search that, Yash.", mood="neutral")

    # ---------------- tab commands ----------------
    def _handle_tab_command(self, command):
        try:
            c = command.lower()
            if "new tab" in c or "open tab" in c:
                speak("Opening new tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "t")
                return

            if "close tab" in c:
                speak("Closing tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "w")
                return

            if "next tab" in c or "switch tab" in c:
                speak("Switching tab.", mood="neutral")
                pyautogui.hotkey("ctrl", "tab")
                return

            if "previous" in c or "prev" in c:
                speak("Going back.", mood="neutral")
                pyautogui.hotkey("ctrl", "shift", "tab")
                return

        except:
            speak("Couldn't change tabs.", mood="neutral")

    # ---------------- app / browser open ----------------
    def _handle_open(self, command):
        try:
            words = command.lower().replace("open ","").replace("launch ","").strip()

            if "youtube" in words:
                speak("Opening YouTube.", mood="happy")
                webbrowser.open_new_tab("https://www.youtube.com")
                return

            if "google" in words:
                speak("Opening Google.", mood="happy")
                webbrowser.open_new_tab("https://www.google.com")
                return

            for name, fn in APP_COMMANDS.items():
                if name in words:
                    speak(f"Opening {name}.", mood="neutral")
                    fn()
                    return

            if "." in words:
                speak(f"Opening {words}.", mood="happy")
                if not words.startswith("http"):
                    words = "https://" + words
                webbrowser.open_new_tab(words)
                return

            speak(f"I couldn't find {words}. Searching it.", mood="neutral")
            webbrowser.open_new_tab(f"https://www.google.com/search?q={words}")

        except Exception as e:
            print("⚠️ Open error:", e)
            speak("Couldn't open that.", mood="neutral")

    # ---------------- media ----------------
    def _handle_media(self, command):
        c = command.lower()
        try:
            if "play pause" in c:
                keyboard.send("play/pause media")
                speak("Toggled play.", mood="neutral")
                return

            if "play" in c:
                keyboard.send("play/pause media")
                speak("Play.", mood="neutral")
                return

            if "pause" in c:
                keyboard.send("play/pause media")
                speak("Pause.", mood="neutral")
                return

            if "volume up" in c:
                keyboard.send("volume up")
                speak("Volume up.", mood="neutral")
                return

            if "volume down" in c:
                keyboard.send("volume down")
                speak("Volume down.", mood="neutral")
                return

            if "mute" in c:
                keyboard.send("volume mute")
                speak("Muted.", mood="neutral")
                return

        except:
            speak("Media control failed.", mood="neutral")

    def stop(self):
        self.running = False
        print("🛑 Listener stopped.")

# Standalone
if __name__ == "__main__":
    L = JarvisListener()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        L.stop()

