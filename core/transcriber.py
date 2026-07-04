"""Обгортка над faster-whisper: завантаження, розпізнавання, вивантаження з RAM."""

import gc
import threading


class Transcriber:
    """Завантажує модель Whisper, транскрибує numpy-аудіо, вміє вивантажуватись."""

    def __init__(self, model_size="base", language="en", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()

    def load(self):
        """Завантажує модель (тягне ваги з мережі при першому запуску)."""
        from faster_whisper import WhisperModel

        with self._lock:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

    def ensure_loaded(self):
        """Завантажує модель, якщо вона ще/вже не в памʼяті."""
        if self._model is None:
            self.load()

    def unload(self):
        """Звільняє модель з оперативної памʼяті."""
        with self._lock:
            self._model = None
        gc.collect()

    @property
    def is_loaded(self):
        return self._model is not None

    def reconfigure(self, model_size=None, language=None):
        """Змінює модель/мову. Якщо модель змінилась — вивантажує стару."""
        if model_size is not None and model_size != self.model_size:
            self.model_size = model_size
            self.unload()
        if language is not None:
            self.language = language

    def transcribe(self, audio):
        """Повертає розпізнаний текст для float32 numpy-масиву (16 kHz mono)."""
        if audio is None or len(audio) == 0:
            return ""
        self.ensure_loaded()
        language = None if self.language in (None, "auto") else self.language
        with self._lock:
            model = self._model
        segments, _info = model.transcribe(audio, language=language, vad_filter=True)
        text = "".join(segment.text for segment in segments)
        return text.strip()
