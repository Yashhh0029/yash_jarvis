import os
import webbrowser
import datetime
import random
import psutil
import pyautogui
import subprocess
import time
import traceback
import threading
import functools

# Desktop control - instantiate safely
try:
    from core.desktop_control import DesktopControl
    desktop = DesktopControl()
except Exception:
    desktop = None

from core.speech_engine import speak, jarvis_fx
from core.conversation_core import JarvisConversation
from core.memory_engine import JarvisMemory
from core.emotion_reflection import JarvisEmotionReflection

# NEW: Phase-2 skill modules
try:
    from core.document_reader import document_reader
except Exception:
    document_reader = None

try:
    from core.video_reader import video_reader
except Exception:
    video_reader = None

try:
    from core.music_player import music_player
except Exception:
    music_player = None

try:
    from core.music_stream import music_stream
except Exception:
    music_stream = None

# NEW IMPORTS (Brain + State + AI)
import core.brain as brain_module
import core.state as state

# Single shared memory/reflection instances
memory = JarvisMemory()
reflection = JarvisEmotionReflection()

# Attempt to import AI chat backend (ollama wrapper or other). If unavailable we'll fallback.
try:
    from core.ai_chat import ai_chat_brain
    AI_CHAT_AVAILABLE = True
except Exception:
    ai_chat_brain = None
    AI_CHAT_AVAILABLE = False


class JarvisCommandHandler:
    """JARVIS Brain — handles commands, responses, emotions & memory."""

    def __init__(self, ai_think_message="Thinking..."):
        print("🧠 Jarvis Command Handler Ready")
        self.user = "Yash"
        self.conversation = JarvisConversation()
        self._ai_lock = threading.Lock()
        self.ai_think_message = ai_think_message
    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def process(self, command):
        if not command:
            return

        raw_command = command
        command = command.lower().strip()
        print(f"🎤 Processing Command: {command}")

        # helper: enhanced speak
        def speak_enhanced(text, mood=None):
            try:
                out = brain_module.brain.enhance_response(
                    text,
                    mood=mood,
                    last_topic=memory.get_last_topic()
                )
            except:
                out = text
            try:
                speak(out, mood=mood)
            except:
                speak(text)

        # --------------------------------------------------------------
        # QUICK IMMEDIATE ACTIONS
        # --------------------------------------------------------------

        # BRIGHTNESS CONTROL
        if any(x in command for x in ["increase brightness", "brightness up", "bright up"]):
            try:
                if desktop: desktop.increase_brightness()
                speak_enhanced("Increasing brightness, Yash.", mood="happy")
            except:
                speak("Couldn't change brightness right now.", mood="alert")
            return

        if any(x in command for x in ["decrease brightness", "brightness down", "dim"]):
            try:
                if desktop: desktop.decrease_brightness()
                speak_enhanced("Okay Yash, dimming the screen.", mood="serious")
            except:
                speak("Couldn't change brightness right now.", mood="alert")
            return

        # VOLUME
        if any(x in command for x in ["volume up", "increase volume", "sound up"]):
            try:
                if desktop: desktop.volume_up()
                speak_enhanced("Raising the volume.", mood="happy")
            except:
                speak("Couldn't change volume.", mood="alert")
            return

        if any(x in command for x in ["volume down", "sound down", "low volume"]):
            try:
                if desktop: desktop.volume_down()
                speak_enhanced("Lowering the volume.", mood="neutral")
            except:
                speak("Couldn't change volume.", mood="alert")
            return

        # MUTE
        if "mute" in command and "unmute" not in command:
            try:
                if desktop: desktop.mute()
                speak_enhanced("Muted.", mood="neutral")
            except:
                speak("Failed to mute.", mood="alert")
            return

        if "unmute" in command:
            try:
                if desktop: desktop.unmute()
                speak_enhanced("Unmuted.", mood="happy")
            except:
                speak("Failed to unmute.", mood="alert")
            return

        # --------------------------------------------------------------
        # DOCUMENT / VIDEO MODULES
        # --------------------------------------------------------------
        # Document Reading
        try:
            if document_reader and (
                "read" in command or
                ("summarize" in command and any(ext in command for ext in [".pdf", ".docx", ".txt", ".md"]))
            ):
                tokens = command.split()
                path_candidate = None
                for tok in tokens:
                    if any(tok.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".txt", ".md"]):
                        path_candidate = tok
                        break

                if path_candidate:
                    path = os.path.abspath(path_candidate)
                    if os.path.exists(path):
                        if "summarize" in command:
                            speak("Summarizing the document…", mood="neutral")
                            threading.Thread(target=document_reader.read, args=(path, True), daemon=True).start()
                            return
                        else:
                            speak("Reading the document…", mood="neutral")
                            threading.Thread(target=document_reader.read, args=(path, False), daemon=True).start()
                            return

                # fallback: pick latest doc
                docs = [f for f in os.listdir('.') if any(f.lower().endswith(ext) for ext in [".pdf", ".docx", ".txt", ".md"])]
                if docs:
                    chosen = os.path.abspath(docs[-1])
                    speak(f"Reading latest document: {os.path.basename(chosen)}", mood="neutral")
                    threading.Thread(target=document_reader.read, args=(chosen, False), daemon=True).start()
                    return
        except:
            pass

        # Video Summarization
        try:
            if video_reader and ("summarize video" in command or "summarize" in command):
                tokens = command.split()
                path_candidate = None
                for tok in tokens:
                    if any(tok.endswith(ext) for ext in [".mp4", ".mkv", ".mov"]):
                        path_candidate = tok
                        break
                if path_candidate:
                    path = os.path.abspath(path_candidate)
                    if os.path.exists(path):
                        speak("Summarizing the video…", mood="neutral")
                        threading.Thread(target=video_reader.summarize, args=(path,), daemon=True).start()
                        return

                vids = [f for f in os.listdir('.') if any(f.lower().endswith(ext) for ext in [".mp4", ".mkv", ".mov"])]
                if vids:
                    chosen = os.path.abspath(vids[-1])
                    speak(f"Summarizing latest video: {os.path.basename(chosen)}", mood="neutral")
                    threading.Thread(target=video_reader.summarize, args=(chosen,), daemon=True).start()
                    return
        except:
            pass

        # --------------------------------------------------------------
        # LOCAL MUSIC / STREAMING
        # --------------------------------------------------------------
        try:
            # local file
            if music_player and ("play " in command and any(ext in command for ext in [".mp3", ".wav", ".ogg"])):
                tokens = command.split()
                for tok in tokens:
                    if any(tok.endswith(ext) for ext in [".mp3", ".wav", ".ogg"]):
                        path = os.path.abspath(tok)
                        if os.path.exists(path):
                            threading.Thread(target=music_player.play, args=(path,), daemon=True).start()
                            return

            # stream query
            if ("play song" in command or command.startswith("play ")) and music_stream:
                q = command
                for p in ["play song", "play music", "play"]:
                    q = q.replace(p, "", 1).strip()
                if q:
                    threading.Thread(target=music_stream.play, args=(q,), daemon=True).start()
                    return
        except:
            pass
        # --------------------------------------------------------------
        # MUSIC CONTROLS
        # --------------------------------------------------------------
        try:
            if music_player and any(k in command for k in ["pause music", "pause song", "pause"]):
                music_player.pause()
                return

            if music_player and any(k in command for k in ["resume music", "resume song", "resume"]):
                music_player.resume()
                return

            if music_player and any(k in command for k in ["stop music", "stop song", "stop playback"]):
                music_player.stop()
                return

            if music_player and any(k in command for k in ["next song", "next track", "next"]):
                music_player.next()
                return

            if music_player and any(k in command for k in ["previous song", "prev song", "previous", "prev"]):
                music_player.previous()
                return

            # set volume to %
            if music_player and "set volume to" in command:
                try:
                    pct = int(''.join(c for c in command.split("set volume to", 1)[1] if c.isdigit()))
                    v = max(0, min(100, pct)) / 100.0
                    music_player.set_volume(v)
                    return
                except:
                    pass
        except:
            pass

        # --------------------------------------------------------------
        # DESKTOP WINDOWS / SYSTEM CONTROLS
        # --------------------------------------------------------------
        if any(x in command for x in ["show desktop", "minimize all"]):
            try:
                if desktop: desktop.show_desktop()
                speak_enhanced("Taking you to the desktop.", mood="neutral")
            except:
                speak("Couldn't switch to desktop.", mood="alert")
            return

        if "close window" in command:
            try:
                if desktop: desktop.close_window()
                speak_enhanced("Window closed.", mood="neutral")
            except:
                speak("Couldn't close window.", mood="alert")
            return

        if "maximize window" in command:
            try:
                if desktop: desktop.maximize_window()
                speak_enhanced("Maximized.", mood="neutral")
            except:
                speak("Couldn't maximize window.", mood="alert")
            return

        if "minimize window" in command:
            try:
                if desktop: desktop.minimize_window()
                speak_enhanced("Minimized.", mood="neutral")
            except:
                speak("Couldn't minimize window.", mood="alert")
            return

        if any(x in command for x in ["next window", "switch window", "alt tab"]):
            try:
                if desktop: desktop.next_window()
                speak_enhanced("Switching window.", mood="neutral")
            except:
                speak("Couldn't switch window.", mood="alert")
            return

        if any(x in command for x in ["previous window", "alt tab back"]):
            try:
                if desktop: desktop.previous_window()
                speak_enhanced("Going back to previous window.", mood="neutral")
            except:
                speak("Couldn't switch back.", mood="alert")
            return

        # --------------------------------------------------------------
        # SYSTEM COMMANDS
        # --------------------------------------------------------------
        if any(x in command for x in ["lock screen", "lock pc"]):
            try:
                if desktop: desktop.lock_screen()
                speak("Locked. I’ll be waiting, Yash.", mood="neutral")
            except:
                speak("Couldn't lock the screen.", mood="alert")
            return

        if any(x in command for x in ["restart", "reboot"]):
            try:
                speak("Restarting the system… be right back.", mood="neutral")
                if desktop: desktop.restart_system()
                else: os.system("shutdown /r /t 1")
            except:
                speak("Restart failed.", mood="alert")
            return

        if any(x in command for x in ["care mode", "take care of me"]):
            try:
                if desktop:
                    desktop.decrease_brightness()
                    desktop.volume_down()
                speak("Of course Yashu… softer lights, calmer sound. I'm here.", mood="serious")
            except:
                speak("Couldn't switch to care mode.", mood="alert")
            return

        # --------------------------------------------------------------
        # GREETINGS
        # --------------------------------------------------------------
        if any(x in command for x in ["hello", "hi", "hey"]):
            speak(random.choice([
                f"Hello {self.user}, ready when you are.",
                f"Hey {self.user}, I’m here.",
                f"Hi {self.user}, systems active."
            ]), mood="happy")
            return

        # --------------------------------------------------------------
        # TIME / DATE
        # --------------------------------------------------------------
        if command == "time" or "what's the time" in command or "time kya" in command:
            now = datetime.datetime.now().strftime("%I:%M %p")
            speak(f"It’s {now}, {self.user}.")
            return

        if "date" in command:
            today = datetime.date.today().strftime("%A, %B %d, %Y")
            speak(f"Today is {today}.")
            return

        # --------------------------------------------------------------
        # BATTERY
        # --------------------------------------------------------------
        if "battery" in command:
            try:
                battery = psutil.sensors_battery()
                if battery:
                    speak(
                        f"Battery is at {battery.percent}% "
                        f"and {'charging' if battery.power_plugged else 'not charging'}.",
                        mood="neutral"
                    )
                else:
                    speak("I can't read battery info right now.")
            except:
                speak("Battery check failed.", mood="alert")
            return

        # --------------------------------------------------------------
        # OPEN WEBSITES
        # --------------------------------------------------------------
        if "open youtube" in command:
            speak("Opening YouTube.", mood="happy")
            webbrowser.open("https://www.youtube.com")
            return

        if "open google" in command:
            speak("Opening Google.", mood="happy")
            webbrowser.open("https://www.google.com")
            return

        if "open spotify" in command:
            speak("Opening Spotify.", mood="happy")
            webbrowser.open("https://open.spotify.com")
            return

        if "open camera" in command:
            speak("Opening camera.", mood="happy")
            os.system("start microsoft.windows.camera:")
            return

        # --------------------------------------------------------------
        # SCREENSHOT
        # --------------------------------------------------------------
        if "screenshot" in command:
            try:
                filename = f"screenshot_{datetime.datetime.now().strftime('%H%M%S')}.png"
                pyautogui.screenshot(filename)
                speak(f"Screenshot saved as {filename}.")
            except:
                speak("Screenshot failed.", mood="alert")
            return

        # --------------------------------------------------------------
        # APPS
        # --------------------------------------------------------------
        if "notepad" in command:
            speak("Opening Notepad.", mood="happy")
            subprocess.Popen(["notepad.exe"])
            return

        if "whatsapp" in command:
            speak("Opening WhatsApp.", mood="happy")
            webbrowser.open("https://web.whatsapp.com")
            return

        # --------------------------------------------------------------
        # BROWSER TAB CONTROLS
        # --------------------------------------------------------------
        if "scroll down" in command:
            pyautogui.press("pagedown")
            speak("Scrolling down.")
            return

        if "scroll up" in command:
            pyautogui.press("pageup")
            speak("Scrolling up.")
            return

        if "new tab" in command:
            pyautogui.hotkey("ctrl", "t")
            speak("New tab opened.")
            return

        if "close tab" in command:
            pyautogui.hotkey("ctrl", "w")
            speak("Tab closed.")
            return

        if "next tab" in command:
            pyautogui.hotkey("ctrl", "tab")
            speak("Switched tab.")
            return

        if "previous tab" in command or "prev tab" in command:
            pyautogui.hotkey("ctrl", "shift", "tab")
            speak("Going back a tab.")
            return
        # --------------------------------------------------------------
        # PERSONALITY QUICK RESPONSES
        # --------------------------------------------------------------
        if "how are you" in command:
            mood = memory.get_mood()
            speak({
                "happy": "Feeling great today!",
                "neutral": "Calm and steady.",
                "alert": "Focused and ready.",
                "serious": "Here — just thinking deeply."
            }.get(mood, "All systems stable."), mood=mood)
            return

        if "thank you" in command or "thanks" in command:
            speak("Always for you, Yashu ❤️", mood="happy")
            return

        # --------------------------------------------------------------
        # FACTS / JOKES
        # --------------------------------------------------------------
        if "joke" in command:
            speak(random.choice([
                "Why did the computer get cold? Because it forgot to close its Windows.",
                "Parallel lines have so much in common. It’s a shame they’ll never meet."
            ]), mood="happy")
            return

        if "fact" in command:
            speak(random.choice([
                "Your brain generates enough electricity to power a small bulb.",
                "Honey never spoils — archaeologists found 3000-year-old honey still edible."
            ]), mood="happy")
            return

        # --------------------------------------------------------------
        # MEMORY COMMANDS
        # --------------------------------------------------------------
        if "remember" in command:
            try:
                if " that " in command:
                    fact = command.replace("remember that", "").strip()
                    if " is " in fact:
                        key, value = fact.split(" is ", 1)
                        memory.remember_fact(key.strip(), value.strip())
                        speak("Okay, I’ll remember that.", mood="neutral")
                    else:
                        speak("Say it like: remember that my laptop is Lenovo.")
                else:
                    speak("Please say it like: remember that ... is ...")
            except:
                speak("Couldn't save that memory.", mood="alert")
            return

        if command.startswith("what is"):
            key = command.replace("what is", "").strip()
            value = memory.recall_fact(key)
            if value:
                speak(f"You told me {key} is {value}.")
            else:
                speak(f"I don’t remember anything about {key}.")
            return

        if "forget" in command:
            key = command.replace("forget", "").strip()
            try:
                memory.forget_fact(key)
                speak("Okay, I forgot it.", mood="neutral")
            except:
                speak("Couldn't forget that.", mood="alert")
            return

        # --------------------------------------------------------------
        # SHUTDOWN
        # --------------------------------------------------------------
        if any(x in command for x in ["shutdown", "exit", "power off"]):
            speak("Powering down softly…", mood="neutral")
            try:
                jarvis_fx.stop_all()
            except:
                pass
            os._exit(0)

        # --------------------------------------------------------------
        # AI / CONVERSATIONAL FALLBACK PIPELINE
        # --------------------------------------------------------------
        # Heuristic: “open / search / play / launch” should stay non-AI
        if any(command.startswith(pref) for pref in ["open ", "launch ", "search ", "play ", "type "]):
            try:
                query = command
                for p in ["search ", "find ", "open ", "launch "]:
                    if query.startswith(p):
                        query = query.replace(p, "", 1).strip()
                if query:
                    webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
                    speak(f"I've searched for {query}.", mood="happy")
                    return
            except:
                pass

        # Spawn background AI worker
        try:
            t = threading.Thread(
                target=self._ai_pipeline_worker,
                args=(raw_command,),
                daemon=True
            )
            t.start()
        except:
            try:
                self._ai_pipeline_worker(raw_command)
            except:
                print("⚠️ Ultimate AI pipeline failure.")

    # --------------------------------------------------------------
    # AI WORKER (Background Thread)
    # --------------------------------------------------------------
    def _ai_pipeline_worker(self, raw_command):
        try:
            # Think message (throttled)
            try:
                if self._ai_lock.acquire(blocking=False):
                    try:
                        speak(self.ai_think_message, mood="neutral")
                    finally:
                        self._ai_lock.release()
            except:
                pass

            ai_response = None

            # 1) Try Ollama / local LLM first
            if AI_CHAT_AVAILABLE and ai_chat_brain:
                try:
                    ai_response = ai_chat_brain.ask(raw_command)
                except:
                    ai_response = None

            # 2) Fallback to JarvisConversation
            if not ai_response:
                try:
                    ai_response = self.conversation.respond(raw_command)
                except:
                    ai_response = None

            # 3) Final fallback to brain.friend-mode reply
            if not ai_response:
                try:
                    ai_response = brain_module.brain.fallback_reply(raw_command)
                except:
                    ai_response = "I didn’t get that — say it differently?"

            # 4) Mood reflection & store
            try:
                inferred = brain_module.brain.detect_text_emotion(ai_response)
                if inferred:
                    memory.set_mood(inferred)
            except:
                pass

            # 5) Enhance with cinematic Jarvis styling
            try:
                enhanced = brain_module.brain.enhance_response(
                    ai_response,
                    mood=memory.get_mood(),
                    last_topic=memory.get_last_topic()
                )
            except:
                enhanced = ai_response

            # 6) Keep system alive
            try:
                state.LAST_INTERACTION = time.time()
            except:
                pass

            # 7) Speak AI response
            speak(enhanced)

        except Exception as e:
            print("⚠️ AI error:", e)
            fallback = "Sorry, I couldn’t process that right now."
            speak(fallback)
