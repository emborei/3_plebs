# Survivors Buddy

A Windows desktop tool for a supervised, screen-only Vampire Survivors assistant. It reads visible pixels and sends ordinary virtual Xbox-controller input; it does **not** inspect game memory, inject into the game, patch files, modify saves, or use an online service.

## What is included

- A desktop configuration UI with hover-help popups, screen preview, saved preferences, safety confirmation, and a hard session limit.
- Screen capture and OCR-based level-up choice assistance.
- Beginner-safe and balanced-damage choice profiles.
- Optional YOLOv5/v8-style ONNX detector adapter, with CUDA, DirectML, and CPU provider selection/fallback.
- A simple movement policy and tested tactical logic for evasive movement and boss-state debouncing.
- Bounded recovery: failed accelerator inference retries on CPU; recoverable loop failures release controls and retry; three consecutive failures stop; the packaged executable has a bounded crash guardian. Corrupt settings are backed up and reset.

**Important limitation:** no Vampire Survivors-trained ONNX model is included, so danger/boss model-based steering is disabled until you provide a model and matching labels. Without one, this remains a supervised early prototype and uses its basic orbit movement. Model compatibility does not guarantee detection accuracy. Review [the model contract](docs/onnx-model-contract.md) before enabling danger mode. The proposed combination of local stage maps and live visual labels is described in [the navigation data plan](docs/navigation-data-plan.md).

## Supported target

- Windows 10/11, Steam build, English UI recommended.
- The same screen-capture path works with AMD and NVIDIA graphics; capture is not tied to a vendor-specific API.
- Optional ONNX model inference: NVIDIA CUDA, DirectML (supported AMD/NVIDIA/Intel DirectX 12 GPUs), or CPU fallback. Actual acceleration depends on driver, model operators, and the installed provider package.
- Android is not supported by this Windows app.

## Try from source

Install Python 3.11+, ViGEmBus (virtual Xbox controller driver), and Tesseract OCR. Then:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python packaging/install_vgamepad.py
survivors-buddy
```

The vgamepad helper downloads the pinned Python bindings but deliberately does **not** launch the package's interactive ViGEmBus MSI installer. Install the ViGEmBus driver separately before starting a controller session; this avoids surprise administrator prompts.

The default ONNX Runtime install is CPU. For an optional GPU provider, replace that package **rather than installing multiple providers together**:

```powershell
# NVIDIA CUDA (install a CUDA/cuDNN-compatible ONNX Runtime wheel)
pip uninstall -y onnxruntime onnxruntime-directml
pip install onnxruntime-gpu

# OR, for supported DirectX 12 GPUs, including many AMD cards
pip uninstall -y onnxruntime onnxruntime-gpu
pip install onnxruntime-directml
```

If using Tesseract from a non-standard path, set `TESSERACT_CMD` to `tesseract.exe`.

Launch the UI, confirm the correct monitor with **Preview screen**, then press Start and switch to the game within 30 seconds. The first frame is gated on the game being foregrounded. Starting requires a safety confirmation and has a one-hour maximum. Stop with the Stop button or close the app. Focus loss releases the virtual controller until the game is foregrounded again.

## Build a portable Windows package

From a Windows machine with Python 3.11, PowerShell, and the required drivers installed:

```powershell
# CPU-compatible portable build
.\packaging\build_windows.ps1 -Backend CPU -TesseractDir 'C:\Program Files\Tesseract-OCR'

# Or choose a single optional runtime provider
.\packaging\build_windows.ps1 -Backend DirectML -TesseractDir 'C:\Program Files\Tesseract-OCR'
.\packaging\build_windows.ps1 -Backend CUDA -TesseractDir 'C:\Program Files\Tesseract-OCR'
```

The script creates `dist/SurvivorsBuddy-Windows.zip`. Distribute the **whole extracted folder**, not only the `.exe`. Users still need the ViGEmBus virtual-controller driver; without a bundled Tesseract folder they need Tesseract on `PATH`. GPU builds depend on compatible graphics drivers and ONNX Runtime packages. The Windows CI workflow builds a DirectML + CPU-fallback portable package and uploads it as a short-lived Actions artifact; it does not include game-trained model weights.

## Self-repair and safety behavior

- Preferences are written atomically under `%LOCALAPPDATA%\\SurvivorsBuddy`. Invalid JSON is preserved as `settings.corrupt.json` and defaults are loaded.
- GPU provider errors trigger one CPU inference retry.
- The run loop releases inputs on errors/focus loss and retries transient failures up to three consecutive times, then stops safely.
- Packaged Windows launch uses a parent watchdog that can restart a crashed UI process at most twice. App logs rotate locally at `%LOCALAPPDATA%\\SurvivorsBuddy\\app.log`.
- “Self-repair” does **not** reinstall GPU drivers, ViGEmBus, OCR, or repair a bad model. A failing dependency stops safely and should be fixed by the user.
- No unattended infinite runs or anti-cheat bypasses are built in. Use only in your own single-player session and check the game's current terms if concerned.

## CLI and tests

```powershell
survivors-buddy --preview
survivors-buddy --run --duration 600
pytest
```

The pure policy/tactics tests run cross-platform. Full GUI, XInput, OCR, packaging, and GPU-provider testing require Windows and the corresponding installed runtimes.

## Research notes

- A useful external-observation precedent is [luceCoding/poe-bot](https://github.com/luceCoding/poe-bot), which describes image recognition plus simulated keypresses, without game-memory access.
- By “ExiledBot,” the likely reference is the Path of Exile automation bot, rather than the read-only PoE Buddy build viewer. Its archived guide stresses configurable behavior/build setup ([archive](https://communityclassic.exiled-bot.net/topic/24796-how-to-exiledbot-aio-guide-2021/)); historical Exiled Bot material describes process injection, which is outside this project's design ([older thread](https://www.ownedcore.com/forums/mmo/path-of-exile/poe-bots-programs/417095-exiled-bot-public-alpha-v0-3b.html)).
- Relevant Vampire Survivors vision examples include [a YOLOv8-based bot](https://github.com/victorcoelh/vampire-survivors-bot) and [an OpenCV heuristic / optional TorchScript pathfinding bot](https://github.com/lucyfurmoonbananas/lucyfur-vs-vision-bot-v2). This project uses neither repository's model weights or source code.
- Combat is largely movement while weapons attack automatically ([controls overview](https://www.gamepressure.com/newsroom/vampire-survivors-controls-explained/z14ebf)); beginner build references include [Pocket Gamer](https://www.pocketgamer.com/vampire-survivors/best-builds/) and a [Steam discussion](https://steamcommunity.com/app/1794680/discussions/0/3275813284142126339/). Choices are version/unlock-dependent.
