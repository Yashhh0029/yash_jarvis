# main.py — FINAL STABLE VERSION (FaceAuth + Ambient + Success Sound + State Sync)
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import sys
import time
import threading
import random
import tempfile
from PyQt5 import QtWidgets

# UI + effects
from core.interface import InterfaceOverlay
from core import voice_effects  # overlay attach

# TRUE shared state
import core.state as state


# ======================================================================
#  FACE AUTHENTICATION MODULE
# ======================================================================
class FaceAuth:
    """
    Stable & cinematic face verification using fallback OpenCV histogram.
    DeepFace is optional and safely handled.
    """

    def __init__(self):
        self.reference_path = os.path.join("config", "face_data", "yash_reference.jpg")
        os.makedirs(os.path.dirname(self.reference_path), exist_ok=True)
        print("📸 FaceAuth loaded")

    # ------------------------------------------------------
    def capture_reference(self):
        import cv2
        from core.speech_engine import speak

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            speak("Camera not accessible, Yash.", mood="alert")
            return

        speak("Look at the camera. Capturing your reference image.", mood="serious")
        time.sleep(1.2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            speak("Failed to capture your face clearly.", mood="alert")
            return

        cv2.imwrite(self.reference_path, frame)
        print("✅ Reference saved:", self.reference_path)
        speak("Reference image captured successfully.", mood="happy")

    # ------------------------------------------------------
    def _fallback_compare(self, ref_path, img2_path):
        """OpenCV histogram fallback."""
        import cv2
        try:
            ref = cv2.imread(ref_path)
            img = cv2.imread(img2_path)
            if ref is None or img is None:
                return False

            ref = cv2.resize(ref, (224, 224))
            img = cv2.resize(img, (224, 224))

            ref_hsv = cv2.cvtColor(ref, cv2.COLOR_BGR2HSV)
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            h1 = cv2.calcHist([ref_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            h2 = cv2.calcHist([img_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            cv2.normalize(h1, h1, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(h2, h2, 0, 1, cv2.NORM_MINMAX)

            score = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
            return score >= 0.55

        except Exception as e:
            print("⚠️ Fallback compare error:", e)
            return False

    # ------------------------------------------------------
    def verify_user(self):
        import cv2
        from core.speech_engine import speak, jarvis_fx

        # Ensure reference exists
        if not os.path.exists(self.reference_path):
            speak("No reference image found. Creating one.", mood="alert")
            self.capture_reference()
            if not os.path.exists(self.reference_path):
                return False

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            speak("Camera not accessible for verification.", mood="alert")
            return False

        speak("Verifying your identity. Keep looking at the camera.", mood="serious")

        # Ambient sound ON
        try:
            threading.Thread(target=jarvis_fx.play_ambient, daemon=True).start()
        except:
            pass

        # Overlay scanning animation
        if voice_effects.overlay_instance:
            try:
                voice_effects.overlay_instance.set_status("🔍 Scanning your face…")
                voice_effects.overlay_instance.set_mood("neutral")
            except:
                pass

        def scan_anim():
            if not voice_effects.overlay_instance:
                return
            for _ in range(8):
                try:
                    voice_effects.overlay_instance.react_to_audio(1.0)
                    time.sleep(0.22)
                    voice_effects.overlay_instance.react_to_audio(0.2)
                    time.sleep(0.22)
                except:
                    break

        threading.Thread(target=scan_anim, daemon=True).start()

        time.sleep(1.4)

        ret, frame = cap.read()
        cap.release()

        if not ret:
            speak("Couldn't capture a clear image.", mood="alert")
            try: jarvis_fx.fade_out_ambient(800)
            except: pass
            return False

        # Save temp scan image
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            scan_path = tmp.name
        import cv2
        cv2.imwrite(scan_path, frame)

        # Try DeepFace first
        verified = False
        try:
            from deepface import DeepFace
            result = DeepFace.verify(
                img1_path=self.reference_path,
                img2_path=scan_path,
                model_name="Facenet",
                detector_backend="opencv",
                enforce_detection=False
            )
            verified = bool(result.get("verified", False))
        except Exception as e:
            print("⚠️ DeepFace unavailable — using fallback:", e)
            verified = self._fallback_compare(self.reference_path, scan_path)

        # Remove temp
        try: os.remove(scan_path)
        except: pass

        # Stop ambient
        try: jarvis_fx.fade_out_ambient(800)
        except: pass

        # Return result
        return verified


# ======================================================================
#   JARVIS STARTUP FLOW
# ======================================================================
def _time_greeting():
    import datetime
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Hello"


def jarvis_startup(overlay):
    print("\n🤖 Booting Yash’s JARVIS…\n")
    import core.state as state
    from core.speech_engine import speak, jarvis_fx
    from core.memory_engine import JarvisMemory
    from core.command_handler import JarvisCommandHandler
    from core.listener import JarvisListener

    memory = JarvisMemory()
    handler = JarvisCommandHandler()

    # Link overlay to effects
    try:
        if hasattr(voice_effects, "attach_overlay"):
            voice_effects.attach_overlay(overlay)
        else:
            voice_effects.overlay_instance = overlay
        print("🌀 Overlay attached.")
    except:
        pass

    try: overlay.set_status("Booting systems…")
    except: pass

    # Boot animation
    for _ in range(3):
        try:
            overlay.react_to_audio(1.2)
            time.sleep(0.28)
            overlay.react_to_audio(0.2)
            time.sleep(0.28)
        except:
            time.sleep(0.5)

    # Startup sound
    try: jarvis_fx.play_startup()
    except Exception as e: print("⚠️ Startup sound:", e)
    time.sleep(5)

    speak("System booting up. Initializing cognition and neural modules.", mute_ambient=True)
    time.sleep(0.6)

    # ----------------------- FACE VERIFICATION ------------------------
    face = FaceAuth()
    verified = face.verify_user()

    # Sync to global state
    state.FACE_VERIFIED = bool(verified)

    # SUCCESS / FAILURE SOUNDS
    from core.speech_engine import speak, jarvis_fx

    if verified:
        try: jarvis_fx.play_success()
        except: pass
        try:
            overlay.set_status("Identity verified ✅")
            overlay.set_mood("happy")
            overlay.react_to_audio(1.3)
        except: pass
        speak("Identity verified. Welcome back, Yash.", mood="happy", mute_ambient=True)
    else:
        try: jarvis_fx.play_alert()
        except: pass
        try:
            overlay.set_status("Identity not recognized ❌")
            overlay.set_mood("alert")
            overlay.react_to_audio(0.6)
        except: pass
        speak("I couldn't recognize you. Limited mode enabled.", mood="alert", mute_ambient=True)

    # ----------------------- GREETING ------------------------
    greet = _time_greeting()
    mood = memory.get_mood()

    speak(f"{greet}, Yash.", mute_ambient=True)
    time.sleep(0.3)
    speak("Say 'Hey Jarvis' when you're ready.", mute_ambient=True)

    # ----------------------- LISTENER ------------------------
    try: overlay.set_status("Listening…")
    except: pass

    print("\n🎤 Listener online — say: Hey Jarvis\n")
    try: JarvisListener()
    except Exception as e:
        print("⚠️ Listener failed:", e)

    while True:
        time.sleep(1)


# ======================================================================
#   ENTRY POINT
# ======================================================================
if __name__ == "__main__":
    print("CURRENT DIR =", os.getcwd())
    print("FILES =", os.listdir())

    app = QtWidgets.QApplication(sys.argv)
    overlay = InterfaceOverlay()

    try:
        overlay.run()
    except:
        overlay.show()

    backend = threading.Thread(target=jarvis_startup, args=(overlay,), daemon=True)
    backend.start()

    sys.exit(app.exec_())
