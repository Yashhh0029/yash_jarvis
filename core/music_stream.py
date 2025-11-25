# core/music_stream.py
"""
Music streaming helper for Jarvis.

Design:
- Lightweight default: open YouTube search in browser.
- If yt-dlp + ffmpeg available, can stream audio directly (experimental).
- Uses webbrowser for guaranteed cross-platform behavior.
"""

import os
import webbrowser
import threading
from core.speech_engine import speak
from core.voice_effects import overlay_instance

# try yt-dlp streaming (optional)
try:
    import yt_dlp
    _YTDLP = True
except Exception:
    _YTDLP = False

class MusicStream:
    def __init__(self):
        self._thread = None

    def play(self, query: str, open_in_browser: bool = True):
        if not query:
            speak("Which song should I play?", mood="neutral")
            return

        speak(f"Searching YouTube for {query}.", mood="happy")

        if open_in_browser or not _YTDLP:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            webbrowser.open_new_tab(url)
            return

        # else try yt-dlp direct stream (best-effort)
        def _stream_worker(q):
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': '-',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{q}", download=False)['entries'][0]
                    url = info['webpage_url']
                    webbrowser.open_new_tab(url)
            except Exception as e:
                print("yt-dlp stream failed:", e)
                webbrowser.open_new_tab(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")

        t = threading.Thread(target=_stream_worker, args=(query,), daemon=True)
        t.start()
        self._thread = t

    def play_direct(self, url: str):
        if not url:
            speak("Give me a stream URL.", mood="neutral")
            return
        speak("Opening music stream.", mood="happy")
        webbrowser.open_new_tab(url)


# singleton
music_stream = MusicStream()
