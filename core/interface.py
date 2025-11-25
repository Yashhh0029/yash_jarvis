# core/interface.py — UPGRADED PART 1
import sys
import math
import time
import threading
import numpy as np
import sounddevice as sd
from PyQt5 import QtCore, QtGui, QtWidgets

# Keep the same class name and public API (run, stop, set_status, set_mood, react_to_audio)

class InterfaceOverlay(QtWidgets.QWidget):
    """Floating Siri-style circular overlay — mic-reactive + Jarvis mood reactive."""
    # Signals for thread-safe updates from non-Qt threads (sounddevice callback, listener threads)
    sig_set_status = QtCore.pyqtSignal(str)
    sig_set_mood = QtCore.pyqtSignal(str)
    sig_react_audio = QtCore.pyqtSignal(float)

    def __init__(self):
        super().__init__()

        # Frameless, always-on-top, translucent
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.resize(220, 220)

        # Visual state (only mutated on the Qt thread)
        self._pulse_angle = 0.0
        self._reactive_boost = 0.0
        self._mic_intensity = 0.0
        self._status_text = "Booting..."
        self._mood = "neutral"
        self.running = True

        # Mic stream control
        self._mic_stream = None
        self._mic_thread = None
        self._mic_enabled = True  # try to keep same feature; turns False if device busy

        # Timers (Qt timers run on the Qt main loop and won't block paintEvent)
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(16)   # ~60 FPS
        self._anim_timer.timeout.connect(self._on_anim_tick)

        # Fade animation (Qt property animation avoids time.sleep)
        self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)

        # Mood color sets (used in paint)
        self.mood_colors = {
            "happy": [QtGui.QColor(60, 220, 200), QtGui.QColor(0, 160, 255)],
            "serious": [QtGui.QColor(255, 140, 0), QtGui.QColor(255, 80, 0)],
            "alert": [QtGui.QColor(255, 60, 90), QtGui.QColor(255, 0, 0)],
            "neutral": [QtGui.QColor(0, 200, 255), QtGui.QColor(120, 80, 255)]
        }

        # Connect signals to slots (thread-safe)
        self.sig_set_status.connect(self._slot_set_status)
        self.sig_set_mood.connect(self._slot_set_mood)
        self.sig_react_audio.connect(self._slot_react_audio)

        # Precompute common painter objects used every frame to reduce allocations
        self._cached_font = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        self._cached_pen = QtGui.QPen(QtCore.Qt.NoPen)

        # Ensure a clean initial opacity
        self.setWindowOpacity(0.0)

    # ---------------- Public Controls ----------------
    def react_to_audio(self, intensity=1.0):
        """Public method (thread-safe) to indicate audio activity."""
        # If called from non-Qt thread, forward via signal
        if QtCore.QThread.currentThread() != QtWidgets.QApplication.instance().thread():
            self.sig_react_audio.emit(float(intensity))
        else:
            self._slot_react_audio(float(intensity))

    def set_status(self, text):
        """Thread-safe setter for status text."""
        if QtCore.QThread.currentThread() != QtWidgets.QApplication.instance().thread():
            self.sig_set_status.emit(str(text))
        else:
            self._slot_set_status(str(text))

    def set_mood(self, mood):
        """Thread-safe setter for mood."""
        if QtCore.QThread.currentThread() != QtWidgets.QApplication.instance().thread():
            self.sig_set_mood.emit(str(mood))
        else:
            self._slot_set_mood(str(mood))

    # ---------------- Slots (Qt thread) ----------------
    @QtCore.pyqtSlot(str)
    def _slot_set_status(self, text):
        self._status_text = text or ""
        # minimal repaint (only bottom area) would be better, but call update() for simplicity
        self.update()

    @QtCore.pyqtSlot(str)
    def _slot_set_mood(self, mood):
        if mood in self.mood_colors:
            self._mood = mood
        else:
            self._mood = "neutral"
        self.update()

    @QtCore.pyqtSlot(float)
    def _slot_react_audio(self, intensity):
        # clamp and smooth reactive boost
        intensity = float(intensity or 0.0)
        target = max(0.3, min(1.5, intensity))
        # immediate uplift (keeps natural feel) but avoid sudden huge jumps
        self._reactive_boost = max(self._reactive_boost, target)
        # store mic intensity separately for possible visual mapping
        self._mic_intensity = min(max(intensity, 0.0), 1.0)
        self.update()

    # ---------------- Mic Listener (background) ----------------
    def _mic_audio_callback(self, indata, frames, time_info, status):
        """
        This callback runs in the sounddevice thread. Keep it minimal:
        - Compute a small energy value and emit a Qt signal to update UI.
        """
        try:
            # compute RMS-ish energy scaled to small range
            vol = np.linalg.norm(indata) / (frames**0.5 + 1e-9)
            # scale appropriately; keep within 0..1
            scaled = min(max(vol * 10.0, 0.0), 1.0)
            # Emit to Qt thread for safe UI update
            self.sig_react_audio.emit(float(scaled))
        except Exception:
            # ignore errors inside callback (must not raise)
            pass

    def _start_mic_stream(self):
        """Start the sounddevice InputStream in a dedicated thread and handle exceptions gracefully."""
        if not self._mic_enabled:
            return

        def _mic_worker():
            try:
                # blocksize set to match earlier code (1024) and rate 16000
                with sd.InputStream(callback=self._mic_audio_callback, channels=1, samplerate=16000, blocksize=1024):
                    # keep the context alive until stopped
                    while self.running and self._mic_enabled:
                        time.sleep(0.1)
            except Exception as e:
                # If device busy or other PortAudio issues happen, disable mic listener to avoid crashes
                print(f"⚠️ Mic listener failed to start or run: {e}")
                self._mic_enabled = False
                # ensure UI knows mic is inactive
                self.sig_react_audio.emit(0.0)

        # spawn background thread for the InputStream to avoid blocking Qt main thread
        self._mic_thread = threading.Thread(target=_mic_worker, daemon=True, name="OverlayMicThread")
        self._mic_thread.start()

    # ---------------- Animation tick (Qt thread) ----------------
    def _on_anim_tick(self):
        # update pulse and decay reactive boost
        self._pulse_angle = (self._pulse_angle + 3.0) % 360.0
        # decay reactive boost smoothly (multiplicative decay)
        self._reactive_boost = max(self._reactive_boost * 0.92, 0.0)
        # trigger repaint
        self.update()
# core/interface.py — UPGRADED PART 2 (continuation)

    # ---------------- Fade-in ----------------
    def _start_fade_in(self, duration_ms=600):
        # Use QPropertyAnimation to animate windowOpacity safely on the Qt thread
        self._fade_anim.stop()
        self._fade_anim.setDuration(int(duration_ms))
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    # ---------------- Paint ----------------
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        center = QtCore.QPointF(w / 2.0, h / 2.0)

        # mood colors (cached locally)
        colors = self.mood_colors.get(self._mood, self.mood_colors["neutral"])
        col_inner, col_outer = colors

        # compute animation parameters
        glow = (math.sin(math.radians(self._pulse_angle)) + 1.0) * 0.5 * (1.0 + self._reactive_boost)
        outer_radius = 70.0 + 25.0 * self._reactive_boost

        # radial gradient
        gradient = QtGui.QRadialGradient(center, outer_radius)
        inner_alpha = int(200 * (0.6 + glow * 0.4))
        mid_alpha = int(120 * (0.6 + glow * 0.4))
        gradient.setColorAt(0.0, QtGui.QColor(col_inner.red(), col_inner.green(), col_inner.blue(), max(0, min(255, inner_alpha))))
        gradient.setColorAt(0.6, QtGui.QColor(col_outer.red(), col_outer.green(), col_outer.blue(), max(0, min(255, mid_alpha))))
        gradient.setColorAt(1.0, QtCore.Qt.transparent)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(gradient))
        painter.drawEllipse(center, outer_radius, outer_radius)

        # concentric rings
        for i, scale in enumerate([0.85, 0.65, 0.45, 0.25]):
            alpha = int(80 * (1 + 0.5 * self._reactive_boost) * (1 - i * 0.15))
            pen = QtGui.QPen(QtGui.QColor(col_outer.red(), col_outer.green(), col_outer.blue(), max(0, min(255, alpha))), 2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(center, outer_radius * scale, outer_radius * scale)

        # core circle
        core_radius = 35.0 + 8.0 * self._reactive_boost
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(col_inner)
        painter.drawEllipse(center, core_radius, core_radius)

        # status text
        if self._status_text:
            painter.setPen(QtGui.QColor(255, 255, 255, 220))
            painter.setFont(self._cached_font)
            rect = self.rect()
            painter.drawText(rect, QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter, self._status_text)

    # ---------------- Run ----------------
    def run(self):
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication instance missing. Create it before calling overlay.run().")

        try:
            screen = app.primaryScreen()
            geometry = screen.availableGeometry()

            # FIXED POSITIONING — PERFECT FOR ALL SCALINGS
            screen_center_x = geometry.x() + int((geometry.width() - self.width()) / 2)
            webcam_offset_y = geometry.y() + int(geometry.height() * 0.02)  # 2% from top

            self.move(screen_center_x, webcam_offset_y)

            print(f"📍 Overlay fixed at: X={screen_center_x}, Y={webcam_offset_y} (exact under webcam)")

        except Exception as e:
            print(f"⚠️ Overlay positioning failed: {e}")

        # start animation timer and mic stream (if available)
        self._anim_timer.start()
        # try to start mic stream — if portaudio busy, it will gracefully disable itself
        try:
            if self._mic_enabled:
                self._start_mic_stream()
        except Exception as e:
            print("⚠️ _start_mic_stream error:", e)
            self._mic_enabled = False

        # fade in smoothly
        self._start_fade_in()
        self.show()

    def stop(self):
        # Gracefully stop everything
        print("🛑 Siri-style Overlay stopping...")
        self.running = False

        # stop timers & animations on Qt thread
        try:
            self._anim_timer.stop()
        except Exception:
            pass

        try:
            self._fade_anim.stop()
        except Exception:
            pass

        # stop mic stream worker
        self._mic_enabled = False
        # allow mic thread to exit; join briefly if alive (non-blocking overall)
        try:
            if self._mic_thread and self._mic_thread.is_alive():
                self._mic_thread.join(timeout=0.3)
        except Exception:
            pass

        # close widget
        try:
            self.close()
        except Exception:
            pass

        print("🛑 Siri-style Overlay stopped.")
