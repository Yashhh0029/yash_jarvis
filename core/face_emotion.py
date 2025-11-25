# core/face_emotion.py
"""
Face Emotion Analyzer for Jarvis
SAFE VERSION — No TensorFlow required.
Uses DeepFace only if available; otherwise falls back to OpenCV Haarcascade.

Fully compatible with:
- shared memory engine
- brain mood fusion
- emotion reflection
"""

import cv2
import time

from core.memory_engine import shared_memory
from core.speech_engine import speak
from core.voice_effects import JarvisEffects

jarvis_fx = JarvisEffects()

# Try loading DeepFace (optional)
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DEEPFACE_AVAILABLE = False
    print("⚠️ DeepFace not available — using fallback face analyzer.")

# Load Haarcascade (fallback)
HAAR = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


class FaceEmotionAnalyzer:
    """Detects user emotion from camera with safe fallback."""

    def __init__(self):
        print("📸 Face Emotion Analyzer Ready (Safe Mode)")
    
    # ---------------------------------------------------------
    def capture_emotion(self):
        """Capture one frame and analyze emotion in safe mode."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None

        time.sleep(0.4)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        # ----------------------------------------------------
        # If DeepFace exists → use it (max accuracy)
        # ----------------------------------------------------
        if DEEPFACE_AVAILABLE:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = DeepFace.analyze(rgb, actions=['emotion'], enforce_detection=False)
                detected = result.get("dominant_emotion", "neutral").lower()
                return self._apply_mood(detected)

            except Exception as e:
                print("⚠️ DeepFace failed, switching to fallback:", e)

        # ----------------------------------------------------
        # FALLBACK → Basic haar detection + neutral guess
        # ----------------------------------------------------
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = HAAR.detectMultiScale(gray, 1.3, 5)

        if len(faces) == 0:
            return self._apply_mood("neutral")

        # fallback cannot classify → treat as neutral
        return self._apply_mood("neutral")

    # ---------------------------------------------------------
    # MOOD MAP + CINEMATIC RESPONSE
    # ---------------------------------------------------------
    def _apply_mood(self, emotion):
        """Maps detected emotion to Jarvis mood system."""

        emotion = emotion.lower()

        mood_map = {
            "happy": "happy",
            "surprise": "happy",
            "sad": "serious",
            "fear": "alert",
            "angry": "alert",
            "disgust": "serious",
            "neutral": "neutral"
        }

        jarvis_mood = mood_map.get(emotion, "neutral")

        # update global memory
        shared_memory.set_mood(jarvis_mood)
        jarvis_fx.mood_tone(jarvis_mood)

        # CINEMATIC REPLIES (trigger only occasionally)
        if emotion == "happy":
            speak("You look bright today, Yash.", mood="happy")

        elif emotion in ["sad", "fear"]:
            speak("You look a bit low… I'm here with you.", mood="serious")

        elif emotion == "angry":
            speak("Your expression seems tense — breathe with me.", mood="alert")

        return emotion
