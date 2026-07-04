# WhisperDictation — голосове диктування для Windows

Резидентний застосунок: живе в **системному треї**, за **глобальним хоткеєм** записує
мовлення з мікрофона, локальною моделлю [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
розпізнає його й **авто-вставляє текст у активне поле**. Усе офлайн.

## Встановлення (з нуля)

Потрібен **Python 3.12** (під нього зібрано збірку). Створюємо віртуальне середовище
й ставимо залежності:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Запуск

```powershell
venv\Scripts\python.exe app_qt.py
```

У треї зʼявиться іконка-еквалайзер (синя — спокій, червона — під час запису).
Подвійний клік — вікно налаштувань.

## Як користуватись

1. Постав курсор у будь-яке текстове поле (Notepad, браузер, чат…).
2. Натисни хоткей (за замовч. **Ctrl+Alt+Z**) — внизу екрана зʼявиться оверлей
   із анімованою хвилею, що реагує на твій голос.
3. Скажи фразу → натисни хоткей ще раз (або зелену **«✓»** в оверлеї) — завершити.
   Щоб **скасувати** без вставки — натисни **Esc** або сіру **«✕»** в оверлеї.
4. Текст розпізнається і **автоматично вставляється** туди, де курсор (+ копія в буфер).

Оверлей показує анімовану хвилю (реагує на гучність), мову та тривалість запису.
На старт/стоп/скасування лунає короткий звуковий сигнал (можна вимкнути в налаштуваннях).

## Налаштування (вкладка в вікні)

- **Модель:** tiny / base / small / medium (більша = точніше, повільніше).
- **Мова:** `en`, `uk`, `auto`.
- **Хоткей:** напр. `ctrl+alt+z`, `ctrl+shift+d` тощо.
- **Авто-вставка:** увімк./вимк. (Ctrl+V у активне поле).
- **Історія буфера Windows (Win+V):** за замовч. **вимкнено** — текст кладеться в буфер для
  вставки, але не засмічує історію Win+V. Увімкни, щоб кожна фраза лишалась у Win+V.
- **Звуковий сигнал:** увімк./вимк. (біп на старт/стоп/скасування).
- **Вивантаження моделі після простою:** звільняє RAM (~1.5 ГБ для medium) після N хв
  без використання; наступне диктування підвантажить модель знову (на пару секунд довше).

Налаштування зберігаються в `%APPDATA%\WhisperDictation\settings.json`.

### Англійська / Українська
Для **української** обери модель `small` або `medium` і мову `uk` — якість суттєво краща,
ніж у tiny/base. На CPU це трохи повільніше, але прийнятно.

## Кеш моделей

Ваги моделей лежать у `C:\Users\<user>\.cache\huggingface\hub`
(medium ≈1.46 ГБ, small ≈464 МБ, base ≈141 МБ, tiny ≈75 МБ). Можна видаляти вручну —
завантажаться знову при потребі. У RAM завантажена `medium` займає ≈1.4–1.6 ГБ.

## Чому CPU, а не GPU

`faster-whisper` (рушій CTranslate2) на Windows прискорюється лише на **NVIDIA CUDA**.
Твоя AMD-відеокарта (ROCm) не підтримується → працюємо на **CPU (int8)**. Для `medium`
відгук ~1–2 с, тож GPU тут не критичний.

## Збірка `.exe` (PyInstaller)

```powershell
venv\Scripts\python.exe -m pip install pyinstaller
venv\Scripts\pyinstaller.exe --noconfirm --noconsole --name WhisperDictation ^
  --add-data "ui/style.qss;ui" ^
  --collect-all faster_whisper --collect-all ctranslate2 ^
  --collect-all onnxruntime --collect-all av --collect-all sounddevice ^
  --collect-submodules keyboard ^
  app_qt.py
```
Готовий застосунок буде в `dist\WhisperDictation\WhisperDictation.exe` (папка ~331 МБ).
Запуск — подвійний клік. Сама модель не вшита — завантажується при першому диктуванні
в кеш HuggingFace (див. розділ «Кеш моделей»); 331 МБ — це рантайм-бібліотеки (Qt,
ffmpeg, CTranslate2, ONNX Runtime), без моделі.

> Готовий рецепт збірки збережено у `WhisperDictation.spec` — можна перезбирати коротше:
> `venv\Scripts\pyinstaller.exe --noconfirm WhisperDictation.spec`

## Інсталятор для Windows (Inno Setup)

Щоб отримати справжній інсталятор (`.exe`), який ставить програму в систему, створює
ярлик у меню Пуск, реєструє її в «Установка та видалення програм» і пропонує
**автозапуск при вході в Windows** — використовується [Inno Setup](https://jrsoftware.org/isdl.php).

1. Встанови Inno Setup (напр. `winget install JRSoftware.InnoSetup`).
2. Спершу зроби PyInstaller-збірку (крок вище) — інсталятор пакує вміст `dist\WhisperDictation`.
3. Скомпілюй сценарій:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Або відкрий `installer.iss` в Inno Setup Compiler і натисни **Build (F9)**.
Результат — `Output\WhisperDictationSetup.exe` (~88 МБ, per-user установка, без прав адміна).

> Сценарій інсталятора — `installer.iss`. При випуску нової версії піднімай `MyAppVersion`
> у ньому, але **не** чіпай `AppId` — по ньому Windows розпізнає оновлення тієї ж програми.

## Структура

```
app_qt.py            точка входу (трей, звʼязування)
settings.py          налаштування (JSON у %APPDATA%)
core/recorder.py     запис з мікрофона + рівень гучності
core/transcriber.py  faster-whisper (load/unload)
core/controller.py   стан-машина, хоткей, авто-вставка, звук, idle-unload
core/clipboard.py    буфер обміну Windows з контролем історії (Win+V)
ui/overlay.py        оверлей запису з анімацією
ui/tray.py           іконка та меню в треї
ui/main_window.py    вікно налаштувань
ui/icons.py          намальовані іконки
ui/style.qss         тема оформлення
WhisperDictation.spec  рецепт PyInstaller (збірка .exe)
installer.iss          сценарій Inno Setup (збірка інсталятора)
requirements.txt       Python-залежності
```
