"""Обгортка над faster-whisper: розпізнавання в окремому фоновому процесі.

Модель живе не в основному процесі застосунку, а в процесі-«воркері». Причина —
ноутбуки з гібридною графікою: поки процес тримає CUDA-контекст, драйвер не дає
NVIDIA заснути, а CTranslate2 не вміє цей контекст закрити. Тож вивантаження
моделі = завершення воркера: разом із ним зникає і CUDA-контекст, і карта засинає.

Основний процес не імпортує ні faster-whisper, ні CTranslate2 і не чіпає CUDA.
"""

import glob
import multiprocessing
import os
import sys
import threading

CPU = "cpu"
CUDA = "cuda"
AUTO = "auto"

# Тип обчислень під кожен пристрій: на GPU float16 швидший, на CPU — int8.
COMPUTE_TYPES = {CPU: "int8", CUDA: "float16"}


def nvidia_present():
    """Чи встановлено драйвер NVIDIA — без звернення до CUDA (карта не прокидається)."""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.exists(os.path.join(system_root, "System32", "nvcuda.dll"))


# ---------- Код воркера (виконується в дочірньому процесі) ----------
def _add_cuda_dll_dirs():
    """Робить DLL cuBLAS (pip-пакет nvidia-cublas-cu12) видимими для CTranslate2.

    CTranslate2 підвантажує cuBLAS ліниво, через пошук у PATH, тому самого
    os.add_dll_directory недостатньо. Працює і з venv, і з PyInstaller (_MEIPASS).
    """
    roots = list(sys.path)
    if hasattr(sys, "_MEIPASS"):
        roots.insert(0, sys._MEIPASS)
    for root in roots:
        for d in glob.glob(os.path.join(root, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except OSError:
                continue
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _load_model(model_size, device):
    """Повертає (модель, реальний пристрій, помилка GPU або None)."""
    from faster_whisper import WhisperModel

    gpu_error = None
    if device == CUDA:
        _add_cuda_dll_dirs()
        try:
            model = WhisperModel(model_size, device=CUDA, compute_type=COMPUTE_TYPES[CUDA])
            return model, CUDA, None
        except Exception as exc:  # noqa: BLE001
            gpu_error = str(exc)
    model = WhisperModel(model_size, device=CPU, compute_type=COMPUTE_TYPES[CPU])
    return model, CPU, gpu_error


def _worker_main(conn, model_size, device):
    """Цикл воркера: завантажити модель, далі відповідати на запити розпізнавання."""
    try:
        model, active_device, gpu_error = _load_model(model_size, device)
        # Прогрів: перший прохід на свіжому GPU ~1 с повільніший. Робимо його зараз,
        # поки користувач ще говорить, а не тоді, коли він чекає на текст.
        import numpy as np

        list(model.transcribe(np.zeros(16000, np.float32), language="en", vad_filter=False)[0])
    except Exception as exc:  # noqa: BLE001
        conn.send(("error", str(exc)))
        return
    conn.send(("ready", active_device, gpu_error))
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            return  # основний процес завершився
        if msg[0] == "exit":
            return
        _, audio, language = msg
        try:
            segments, _info = model.transcribe(audio, language=language, vad_filter=True)
            conn.send(("text", "".join(segment.text for segment in segments).strip()))
        except Exception as exc:  # noqa: BLE001
            conn.send(("error", str(exc)))


# ---------- Основний процес ----------
class Transcriber:
    """Керує процесом-воркером: запуск (= завантаження моделі), розпізнавання, завершення."""

    def __init__(self, model_size="base", language="en", device=AUTO):
        self.model_size = model_size
        self.language = language
        self.device = device            # що обрав користувач: auto | cuda | cpu
        self.active_device = None       # на чому модель реально працює: cuda | cpu
        self.fallback_error = None      # чому не вдалось запустити на GPU (якщо так)
        self._proc = None
        self._conn = None
        self._lock = threading.RLock()

    def resolve_device(self):
        """Пристрій, на якому модель запуститься (або вже працює)."""
        if self.active_device is not None:
            return self.active_device
        if self.device == CPU:
            return CPU
        return CUDA if nvidia_present() else CPU

    def load(self):
        """Запускає воркер і чекає, доки він завантажить модель.

        Якщо GPU не вдалось ініціалізувати — воркер сам переходить на CPU,
        причину зберігаємо у fallback_error.
        """
        with self._lock:
            self.unload()
            ctx = multiprocessing.get_context("spawn")
            parent_conn, child_conn = ctx.Pipe()
            proc = ctx.Process(
                target=_worker_main,
                args=(child_conn, self.model_size, self.resolve_device()),
                daemon=True,
            )
            proc.start()
            child_conn.close()
            try:
                reply = parent_conn.recv()
            except EOFError:
                reply = ("error", f"процес розпізнавання завершився (код {proc.exitcode})")
            if reply[0] != "ready":
                parent_conn.close()
                proc.join(timeout=1)
                raise RuntimeError(reply[1])
            _, self.active_device, self.fallback_error = reply
            self._proc, self._conn = proc, parent_conn

    def ensure_loaded(self):
        """Запускає воркер, якщо його ще/вже нема. True — якщо саме цей виклик запустив."""
        with self._lock:
            if self.is_loaded:
                return False
            self.load()
            return True

    def unload(self):
        """Завершує воркер: звільняє RAM, VRAM і CUDA-контекст (NVIDIA може заснути)."""
        with self._lock:
            proc, conn = self._proc, self._conn
            self._proc = self._conn = None
            self.active_device = None
            if proc is None:
                return
            try:
                conn.send(("exit",))
            except OSError:
                pass
            proc.join(timeout=3)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1)
            conn.close()

    @property
    def is_loaded(self):
        return self._proc is not None and self._proc.is_alive()

    # Модель або повністю готова (воркер живий), або її нема — проміжного стану немає.
    is_ready = is_loaded

    def reconfigure(self, model_size=None, language=None, device=None):
        """Змінює модель/мову/пристрій. Якщо змінилась модель чи пристрій — вивантажує."""
        if model_size is not None and model_size != self.model_size:
            self.model_size = model_size
            self.unload()
        if device is not None and device != self.device:
            self.device = device
            self.unload()
        if language is not None:
            self.language = language

    def transcribe(self, audio):
        """Повертає розпізнаний текст для float32 numpy-масиву (16 kHz mono)."""
        if audio is None or len(audio) == 0:
            return ""
        language = None if self.language in (None, "auto") else self.language
        # Лок на весь запит: таймер простою не завершить воркер посеред розпізнавання.
        with self._lock:
            self.ensure_loaded()
            try:
                self._conn.send(("transcribe", audio, language))
                reply = self._conn.recv()
            except (EOFError, OSError) as exc:
                self.unload()  # воркер упав — наступний запит запустить новий
                raise RuntimeError(f"процес розпізнавання завершився: {exc}") from exc
        if reply[0] != "text":
            raise RuntimeError(reply[1])
        return reply[1]
