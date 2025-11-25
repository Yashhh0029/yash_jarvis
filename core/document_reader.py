# core/document_reader.py
"""
High-tech Document Reader + Summarizer for Jarvis.

Features:
- Reads PDF / DOCX / TXT / MD.
- Splits long documents into chunks (safe chunk-size).
- Optional improved summarization:
    - If OpenAI API key present -> uses OpenAI (chat/completions).
    - Else if local transformers summarization pipeline available -> uses it.
    - Else falls back to an in-process TextRank summarizer.
- Reads aloud using core.speech_engine.speak and can return textual summary.
- Non-blocking API: heavy ops run in background thread if used via `read_async` / `summarize_async`.
"""

import os
import threading
import math
from typing import Optional, List

# file readers
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

# optional advanced libs
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    _TRANSFORMERS_AVAILABLE = True
except Exception:
    _TRANSFORMERS_AVAILABLE = False

# optional OpenAI
try:
    import openai
    _OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))
except Exception:
    _OPENAI_AVAILABLE = False

from core.speech_engine import speak
import core.nlp_engine as nlp
from core.memory_engine import JarvisMemory

memory = JarvisMemory()


# -------------------------
# Utility: chunk text
# -------------------------
def _chunk_text(text: str, max_words: int = 350) -> List[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + max_words]
        chunks.append(" ".join(chunk))
        i += max_words
    return chunks


# -------------------------
# Simple TextRank fallback summarizer
# -------------------------
def _textrank_summarize(text: str, max_sentences: int = 5) -> str:
    # naive frequency-based sentence scorer (safe, no external deps)
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) <= max_sentences:
        return text
    # word freq
    words = re.findall(r"\w+", text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    # score sentences
    sscore = []
    for s in sentences:
        s_words = re.findall(r"\w+", s.lower())
        if not s_words:
            sscore.append((0, s))
            continue
        score = sum(freq.get(w, 0) for w in s_words) / len(s_words)
        sscore.append((score, s))
    sscore.sort(reverse=True, key=lambda x: x[0])
    selected = [s for _, s in sscore[:max_sentences]]
    # keep original order
    selected_sorted = [s for s in sentences if s in selected]
    return " ".join(selected_sorted)


# -------------------------
# Summarizer orchestrator
# -------------------------
def _summarize_text(text: str, max_words_chunk=350, prefer="auto") -> str:
    """
    prefer: "openai", "transformers", "textrank", or "auto"
    """
    # Try OpenAI first if requested / available
    if prefer in ("openai", "auto") and _OPENAI_AVAILABLE:
        try:
            # chunk and prompt
            chunks = _chunk_text(text, max_words=max_words_chunk)
            summaries = []
            for ch in chunks:
                prompt = (
                    "Summarize the following text into 4-6 concise bullet points. "
                    "Be precise and keep technical terms if present:\n\n" + ch
                )
                # Use ChatCompletion if available
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4o-mini" if "gpt-4o-mini" in openai.Model.list() else "gpt-4",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        max_tokens=450
                    )
                    summary = resp.choices[0].message.content.strip()
                except Exception:
                    # fallback to completion
                    resp = openai.Completion.create(
                        engine="text-davinci-003",
                        prompt=prompt,
                        max_tokens=450,
                        temperature=0.0
                    )
                    summary = resp.choices[0].text.strip()
                summaries.append(summary)
            return "\n\n".join(summaries)
        except Exception:
            pass

    # Try transformers summarizer if available
    if prefer in ("transformers", "auto") and _TRANSFORMERS_AVAILABLE:
        try:
            summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
            chunks = _chunk_text(text, max_words=max_words_chunk)
            outs = []
            for ch in chunks:
                out = summarizer(ch, max_length=130, min_length=30, do_sample=False)
                outs.append(out[0]["summary_text"])
            return "\n\n".join(outs)
        except Exception:
            pass

    # Final fallback - textrank
    return _textrank_summarize(text, max_sentences=6)


# -------------------------
# DocumentReader
# -------------------------
class DocumentReader:
    def __init__(self):
        self._thread = None

    def _extract_text_pdf(self, path: str) -> str:
        if not PyPDF2:
            raise RuntimeError("PyPDF2 not installed")
        try:
            reader = PyPDF2.PdfReader(path)
            pages = []
            for p in reader.pages:
                t = p.extract_text() or ""
                pages.append(t)
            return "\n\n".join(pages)
        except Exception:
            return ""

    def _extract_text_docx(self, path: str) -> str:
        if not docx:
            raise RuntimeError("python-docx not installed")
        try:
            doc = docx.Document(path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception:
            return ""

    def _extract_text_plain(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _read_chunks_aloud(self, chunks: List[str]):
        for ch in chunks:
            if ch.strip():
                speak(ch.strip(), mood="neutral")

    def read(self, path: str, summarize_first: bool = False, prefer_summarizer: str = "auto") -> Optional[str]:
        """
        Synchronous read: extracts text, optionally summarizes, then speaks and returns summary text.
        If document is very long, this may block. Use read_async for non-blocking.
        """
        if not path or not os.path.exists(path):
            speak("I couldn't find that file.", mood="alert")
            return None

        ext = os.path.splitext(path)[1].lower()
        text = ""
        try:
            if ext == ".pdf":
                text = self._extract_text_pdf(path)
            elif ext in (".docx", ".doc"):
                text = self._extract_text_docx(path)
            else:
                text = self._extract_text_plain(path)
        except Exception:
            text = ""

        if not text.strip():
            speak("The document is empty or unreadable.", mood="alert")
            return None

        # If summary requested, do summarization first and speak summary then offer to read details
        if summarize_first:
            speak("Creating a concise summary of this document...", mood="neutral")
            summary = _summarize_text(text, prefer=prefer_summarizer)
            # speak summary
            speak("Here is a short summary:", mood="happy")
            speak(summary, mood="neutral")
            # offer to read full text
            return summary

        # Normal read: chunk and speak
        chunks = _chunk_text(text, max_words=300)
        self._read_chunks_aloud(chunks)
        return None

    def read_async(self, path: str, summarize_first: bool = False, prefer_summarizer: str = "auto"):
        t = threading.Thread(target=self.read, args=(path, summarize_first, prefer_summarizer), daemon=True)
        t.start()
        self._thread = t
        return t


# singleton
document_reader = DocumentReader()
