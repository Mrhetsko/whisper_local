"""Запис з мікрофона у numpy-буфер + живий рівень гучності (RMS) для анімації."""

import threading

import numpy as np
import sounddevice as sd


class Recorder:
    """Записує аудіо з мікрофона у памʼять і віддає поточний рівень гучності."""

    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream = None
        self._frames = []
        self._lock = threading.Lock()
        self._level = 0.0  # 0..1, останній RMS
        self.recording = False

    def _callback(self, indata, frames, time_info, status):
        # Рівень гучності для анімації оверлею.
        rms = float(np.sqrt(np.mean(np.square(indata)))) if indata.size else 0.0
        # Перцептивна крива + підсилення: звичайна мова (RMS ~0.01..0.05) має
        # давати помітне відхилення, а не лише крик. Невеликий шумовий поріг.
        level = max(0.0, rms - 0.002) ** 0.5 * 4.8
        level = min(1.0, level)
        with self._lock:
            self._frames.append(indata.copy())
            self._level = level

    def start(self):
        if self.recording:
            return
        with self._lock:
            self._frames = []
            self._level = 0.0
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        self.recording = True

    def stop(self):
        """Зупиняє запис і повертає float32 numpy-масив (моно, 16 kHz)."""
        if not self.recording:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self.recording = False
        with self._lock:
            frames = self._frames
            self._frames = []
            self._level = 0.0
        if not frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(frames, axis=0)
        return audio.flatten().astype(np.float32)

    def get_level(self):
        """Поточний рівень гучності 0..1 (для анімації)."""
        with self._lock:
            return self._level

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.recording = False
