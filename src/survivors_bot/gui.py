"""Self-guided Windows desktop interface for Survivors Buddy."""
from __future__ import annotations

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from .engine import BotEngine
from .gpu import runtime_info
from .settings import AppSettings, SettingsStore
from .vision import analyze, capture_monitor


STYLE = """
QWidget { background: #10151e; color: #e8edf5; font: 10pt 'Segoe UI'; }
QFrame#card, QGroupBox { background: #192230; border: 1px solid #2b3a4d; border-radius: 12px; }
QGroupBox { margin-top: 12px; padding: 14px 12px 12px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #b7c7dc; }
QLabel#title { font-size: 22pt; font-weight: 700; color: #f3f7ff; }
QLabel#muted { color: #9cacbf; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #0e141d; border: 1px solid #36465c; border-radius: 7px; padding: 8px; selection-background-color: #3768b4; }
QComboBox::drop-down { border: 0; width: 24px; }
QPushButton { background: #26364a; border: 1px solid #3d526e; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #314968; }
QPushButton:disabled { color: #798696; background: #202936; }
QPushButton#primary { background: #3269be; border-color: #467bd0; color: white; }
QPushButton#primary:hover { background: #3c7add; }
QPushButton#danger { background: #8f3440; border-color: #b04b57; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QTextEdit { font-family: 'Consolas'; font-size: 9pt; }
QScrollArea { border: 0; }
"""


class TaskSignals(QThread):
    message = Signal(str)
    preview = Signal(object, object, object)
    failed = Signal(str)

    def __init__(self, mode: str, settings: AppSettings):
        super().__init__()
        self.mode = mode
        self.settings = settings

    def run(self) -> None:
        def report(message: str) -> None:
            logging.getLogger("survivors_buddy").info(message)
            self.message.emit(message)
        try:
            if self.mode == "preview":
                frame = capture_monitor(self.settings.monitor)
                observation = analyze(frame)
                self.preview.emit(frame, observation, [])
                report(f"Screen read complete. Upgrade menu: {observation.level_up_menu}; recognized {len(observation.choices)} item(s).")
                return
            BotEngine().run(
                monitor=self.settings.monitor,
                duration_seconds=self.settings.duration_minutes * 60,
                interval=self.settings.scan_interval,
                stop_requested=self.isInterruptionRequested,
                log=report,
                model_path=self.settings.model_path,
                labels_path=self.settings.labels_path,
                backend=self.settings.backend,
                danger_mode=self.settings.danger_mode,
                profile=self.settings.profile,
                frame_ready=self.preview.emit,
            )
        except Exception as exc:
            logging.getLogger("survivors_buddy").exception("Worker stopped with an error")
            self.failed.emit(str(exc))
            report(f"Stopped safely: {exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Survivors Buddy")
        self.setMinimumSize(960, 760)
        self.store = SettingsStore()
        self.settings = self.store.load()
        self.task: TaskSignals | None = None
        self._close_when_stopped = False
        self._build_ui()
        self._load_settings()
        self.refresh_runtime_status()

    def _build_ui(self) -> None:
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel("Survivors Buddy")
        title.setObjectName("title")
        subtitle = QLabel("External screen vision · local single-player assistant")
        subtitle.setObjectName("muted")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch(1)
        self.gpu_badge = QLabel("Checking graphics…")
        self.gpu_badge.setToolTip("Inference backend selected for an optional ONNX detection model. Screen capture works on NVIDIA and AMD cards.")
        header.addWidget(self.gpu_badge)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(13)

        setup = QGroupBox("1 · Quick setup")
        grid = QGridLayout(setup)
        self.monitor = QComboBox()
        self._populate_monitors()
        self.monitor.setToolTip("Choose the display containing the game. Preview lets you verify the correct screen before enabling inputs.")
        self.profile = QComboBox()
        self.profile.addItems(["Beginner safe", "Balanced damage"])
        self.profile.setToolTip("Beginner safe favors sustain and forgiving area coverage. Balanced damage gives more weight to scaling damage and cooldown upgrades. The build remains limited to items actually offered in your run.")
        self.duration = QSpinBox()
        self.duration.setRange(1, 60)
        self.duration.setSuffix(" minutes")
        self.duration.setToolTip("Hard session limit. The controller is released when time expires. The default is ten minutes; start supervised.")
        self.preview_button = QPushButton("Preview screen")
        self.preview_button.setToolTip("Capture one frame and read visible upgrade text. Does not send controller inputs.")
        self.preview_button.clicked.connect(self.start_preview)
        grid.addWidget(QLabel("Game display"), 0, 0)
        grid.addWidget(self.monitor, 0, 1)
        grid.addWidget(QLabel("Play profile"), 0, 2)
        grid.addWidget(self.profile, 0, 3)
        grid.addWidget(QLabel("Session limit"), 1, 0)
        grid.addWidget(self.duration, 1, 1)
        grid.addWidget(self.preview_button, 1, 2, 1, 2)
        body_layout.addWidget(setup)

        vision_box = QGroupBox("2 · Vision and graphics")
        vision_grid = QGridLayout(vision_box)
        self.backend = QComboBox()
        self.backend.addItem("Auto (recommended)", "auto")
        self.backend.addItem("NVIDIA CUDA", "nvidia")
        self.backend.addItem("DirectML (AMD / NVIDIA / Intel)", "directml")
        self.backend.addItem("CPU (maximum compatibility)", "cpu")
        self.backend.setToolTip("DirectML runs ONNX models on supported DirectX 12 GPUs, including many AMD and NVIDIA cards. CUDA is usually fastest on NVIDIA. Auto tries CUDA, DirectML, then CPU. Screen capture itself is vendor-neutral.")
        self.model_path = QLineEdit()
        self.model_path.setPlaceholderText("Optional trained .onnx object-detection model")
        self.model_path.setToolTip("Optional ONNX model trained for Vampire Survivors. No model is bundled; OCR and basic play work without one. Scene-based danger awareness needs a compatible trained model.")
        self.model_browse = QPushButton("Browse…")
        self.model_browse.clicked.connect(self.browse_model)
        self.labels_path = QLineEdit()
        self.labels_path.setPlaceholderText("Model class labels (.txt)")
        self.labels_path.setToolTip("One class label per line, matching the model output order (for example: enemy, projectile, boss, telegraph).")
        self.labels_browse = QPushButton("Browse…")
        self.labels_browse.clicked.connect(self.browse_labels)
        self.danger = QCheckBox("Enable model-based danger dodging")
        self.danger.setToolTip("Use detected enemies, projectiles, bosses, and telegraphs to choose evasive movement. Requires a compatible ONNX model and labels; with no model the app will not pretend it can see threats.")
        self.danger.toggled.connect(self._danger_toggled)
        vision_grid.addWidget(QLabel("Inference backend"), 0, 0)
        vision_grid.addWidget(self.backend, 0, 1, 1, 2)
        vision_grid.addWidget(self.model_path, 1, 0, 1, 2)
        vision_grid.addWidget(self.model_browse, 1, 2)
        vision_grid.addWidget(self.labels_path, 2, 0, 1, 2)
        vision_grid.addWidget(self.labels_browse, 2, 2)
        vision_grid.addWidget(self.danger, 3, 0, 1, 3)
        self.runtime_status = QLabel()
        self.runtime_status.setObjectName("muted")
        self.runtime_status.setWordWrap(True)
        vision_grid.addWidget(self.runtime_status, 4, 0, 1, 3)
        self.model_path.textChanged.connect(self.refresh_runtime_status)
        self.backend.currentIndexChanged.connect(self.refresh_runtime_status)
        body_layout.addWidget(vision_box)

        self.image_label = QLabel("Use Preview screen to inspect the capture.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(190)
        self.image_label.setMaximumHeight(280)
        self.image_label.setStyleSheet("background:#0b1017; border:1px dashed #3d526e; border-radius:10px; color:#91a3b9;")
        self.image_label.setToolTip("A visual confirmation of the display the bot reads. The preview is not sent anywhere.")
        body_layout.addWidget(self.image_label)

        safety = QGroupBox("3 · Safety and run controls")
        safety_row = QHBoxLayout(safety)
        self.consent = QCheckBox("I have the game focused and understand Start sends virtual-controller inputs.")
        self.consent.setToolTip("Required before starting. The tool only sends inputs while Vampire Survivors is foregrounded and releases controls on stop, focus loss, or recoverable errors.")
        self.start_button = QPushButton("Start supervised run")
        self.start_button.setObjectName("primary")
        self.start_button.setEnabled(False)
        self.start_button.setToolTip("Start a time-limited run. Stay nearby. Focus loss pauses movement; repeated errors stop the run and release the controller.")
        self.start_button.clicked.connect(self.toggle_run)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_run)
        self.consent.toggled.connect(self.start_button.setEnabled)
        safety_row.addWidget(self.consent, 1)
        safety_row.addWidget(self.start_button)
        safety_row.addWidget(self.stop_button)
        body_layout.addWidget(safety)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.setPlaceholderText("Setup messages and run health appear here.")
        self.log.setToolTip("Diagnostics are stored locally in this window. No telemetry or account login is used.")
        body_layout.addWidget(self.log)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.setCentralWidget(outer)

    def _populate_monitors(self) -> None:
        self.monitor.clear()
        self.monitor.addItem("Primary display", 1)
        try:
            import mss
            with mss.mss() as sct:
                for index in range(2, len(sct.monitors)):
                    self.monitor.addItem(f"Display {index - 1}", index)
        except Exception:
            pass

    def _load_settings(self) -> None:
        for i in range(self.monitor.count()):
            if self.monitor.itemData(i) == self.settings.monitor:
                self.monitor.setCurrentIndex(i)
                break
        idx = self.backend.findData(self.settings.backend)
        self.backend.setCurrentIndex(max(0, idx))
        self.profile.setCurrentText(self.settings.profile)
        self.duration.setValue(self.settings.duration_minutes)
        self.model_path.setText(self.settings.model_path)
        self.labels_path.setText(self.settings.labels_path)
        self.danger.setChecked(self.settings.danger_mode)

    def collect_settings(self) -> AppSettings:
        return AppSettings(
            monitor=int(self.monitor.currentData() or 1),
            backend=str(self.backend.currentData() or "auto"),
            model_path=self.model_path.text().strip(),
            labels_path=self.labels_path.text().strip(),
            duration_minutes=self.duration.value(),
            scan_interval=0.8,
            profile=self.profile.currentText(),
            danger_mode=self.danger.isChecked(),
        )

    def refresh_runtime_status(self) -> None:
        info = runtime_info(self.backend.currentData() or "auto")
        self.gpu_badge.setText(info.selected)
        bundled_ocr = Path(sys.executable).parent / "resources" / "tesseract" / "tesseract.exe"
        ocr_ok = bool(os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or bundled_ocr.exists())
        model_ok = bool(self.model_path.text().strip() and Path(self.model_path.text().strip()).is_file())
        detector = f"Detection model: {'ready to load' if model_ok else 'not selected (danger mode unavailable)'}"
        ocr = "Tesseract OCR: found" if ocr_ok else "Tesseract OCR: not found on PATH (preview/level-choice OCR needs it)"
        self.runtime_status.setText(info.note + "\n" + detector + " · " + ocr + "\nController requires the separate ViGEmBus driver. CPU remains available if a GPU provider fails.")

    def browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ONNX detection model", "", "ONNX models (*.onnx)")
        if path:
            self.model_path.setText(path)
            if not self.labels_path.text():
                sidecar = str(Path(path).with_suffix(".txt"))
                if Path(sidecar).exists():
                    self.labels_path.setText(sidecar)

    def browse_labels(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select class labels", "", "Text files (*.txt)")
        if path:
            self.labels_path.setText(path)

    def _danger_toggled(self, enabled: bool) -> None:
        if enabled and not self._model_files_ready():
            self.log.append("Danger mode needs an existing trained ONNX model and matching .txt labels.")

    def _model_files_ready(self) -> bool:
        return Path(self.model_path.text().strip()).is_file() and Path(self.labels_path.text().strip()).is_file()

    def start_preview(self) -> None:
        if self.task and self.task.isRunning():
            return
        self._save_settings()
        self.task = TaskSignals("preview", self.settings)
        self.task.preview.connect(self.show_preview)
        self.task.message.connect(self.log.append)
        self.task.failed.connect(self.show_error)
        self.task.finished.connect(self._after_task)
        self.task.start()
        self.preview_button.setEnabled(False)

    def show_preview(self, frame, observation, detections) -> None:
        import cv2
        canvas = frame.copy()
        for item in detections:
            cv2.rectangle(canvas, (item.x1, item.y1), (item.x2, item.y2), (70, 230, 150), 2)
            cv2.putText(canvas, f"{item.label} {item.confidence:.0%}", (item.x1, max(18, item.y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (70, 230, 150), 2)
        height, width = canvas.shape[:2]
        qimage = QImage(canvas.data, width, height, canvas.strides[0], QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage).scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        self.log.append(f"OCR: {observation.text[:240] or '(none)'}")
        if observation.choices:
            self.log.append("Choices: " + ", ".join(c.label for c in observation.choices))

    def toggle_run(self) -> None:
        if self.task and self.task.isRunning():
            self.stop_run()
            return
        if not self.consent.isChecked():
            return
        if self.danger.isChecked() and not self._model_files_ready():
            QMessageBox.warning(self, "Model required", "Choose an ONNX detection model and matching labels, or turn off model-based danger dodging.")
            return
        answer = QMessageBox.question(self, "Start supervised run?", "The game must be focused. This will send virtual-controller inputs for the configured time limit. Start now?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._save_settings()
        self.task = TaskSignals("run", self.settings)
        self.task.preview.connect(self.show_preview)
        self.task.message.connect(self.log.append)
        self.task.failed.connect(self.show_error)
        self.task.finished.connect(self.run_finished)
        self.task.finished.connect(self._after_task)
        self.task.start()
        self.start_button.setText("Running…")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.preview_button.setEnabled(False)

    def stop_run(self) -> None:
        if self.task and self.task.isRunning():
            self.task.requestInterruption()
            self.log.append("Stop requested; releasing input…")
            self.stop_button.setEnabled(False)

    def run_finished(self) -> None:
        self.start_button.setText("Start supervised run")
        self.start_button.setEnabled(self.consent.isChecked())
        self.stop_button.setEnabled(False)
        self.preview_button.setEnabled(True)

    def _after_task(self) -> None:
        if self.task and self.task.mode == "preview":
            self.preview_button.setEnabled(True)
        if self._close_when_stopped:
            QTimer.singleShot(0, self.close)

    def show_error(self, message: str) -> None:
        self.log.append("ERROR: " + message)
        QMessageBox.warning(self, "Could not continue safely", message)

    def _save_settings(self) -> None:
        self.settings = self.collect_settings()
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self.log.append(f"Could not save preferences: {exc}")

    def closeEvent(self, event) -> None:
        if self.task and self.task.isRunning():
            self.task.requestInterruption()
            if not self.task.wait(2500):
                self._close_when_stopped = True
                self.log.append("Waiting for the worker to release controller inputs before closing…")
                event.ignore()
                return
        self._save_settings()
        event.accept()


def launch() -> int:
    log_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "SurvivorsBuddy"
    log_root.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_root / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    sys.excepthook = lambda kind, value, trace: logging.getLogger("survivors_buddy").critical("Unhandled application exception", exc_info=(kind, value, trace))
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
