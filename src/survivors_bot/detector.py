"""Small YOLOv8/v5-style ONNX detector adapter with provider fallback.

No model weights are bundled: a game-specific, labeled model must be selected by the
user. The adapter accepts common exported raw YOLO outputs and keeps inference external.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .gpu import create_session


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class OnnxYoloDetector:
    def __init__(self, model_path: str | Path, labels_path: str | Path, backend: str = "auto", input_size: int = 640, threshold: float = 0.35) -> None:
        import cv2  # fail at setup, before any inputs are sent
        self.cv2 = cv2
        self.model_path = str(model_path)
        self.backend = backend
        self.session, self.provider = create_session(model_path, backend)
        self.input = self.session.get_inputs()[0]
        self.input_name = self.input.name
        shape = self.input.shape
        self.input_size = int(shape[-1]) if isinstance(shape[-1], int) else input_size
        self.threshold = threshold
        self.labels = [line.strip() for line in Path(labels_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not self.labels:
            raise ValueError("Label file is empty")

    def detect(self, rgb_image) -> list[Detection]:
        import numpy as np

        cv2 = self.cv2
        height, width = rgb_image.shape[:2]
        scale = min(self.input_size / width, self.input_size / height)
        resized_w, resized_h = round(width * scale), round(height * scale)
        resized = cv2.resize(rgb_image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        pad_x, pad_y = (self.input_size - resized_w) // 2, (self.input_size - resized_h) // 2
        canvas[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized
        # MSS/capture gives RGB; standard Ultralytics YOLO exports expect RGB channel order.
        blob = canvas.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        try:
            outputs = self.session.run(None, {self.input_name: blob})
        except Exception:
            # Driver/provider faults fall back to CPU once; the next inference is retried
            # through the replacement session rather than restarting the whole app.
            if self.provider == "CPUExecutionProvider":
                raise
            self.session, self.provider = create_session(self.model_path, "cpu")
            self.input = self.session.get_inputs()[0]
            self.input_name = self.input.name
            outputs = self.session.run(None, {self.input_name: blob})
        if not outputs:
            return []
        rows = np.asarray(outputs[0])
        while rows.ndim > 2:
            rows = rows[0]
        # YOLOv8 raw output is commonly [channels, anchors]; YOLO exports vary.
        if rows.shape[1] > 100 and rows.shape[0] <= len(self.labels) + 5:
            rows = rows.T

        boxes: list[list[float]] = []
        scores: list[float] = []
        class_ids: list[int] = []
        for row in rows:
            if len(row) < 5:
                continue
            if len(row) == 6 and len(self.labels) >= 3:  # decoded Nx6; raw YOLO with 1-2 classes is ambiguous
                x1, y1, x2, y2, score, cls = row[:6]
                class_id = int(cls)
                coords_are_corners = True
            else:
                xywh = row[:4]
                values = row[4:]
                # YOLOv5 raw exports include objectness; v8 exports do not.
                if len(values) == len(self.labels) + 1:
                    objectness, class_scores = values[0], values[1:]
                    class_scores = class_scores * objectness
                else:
                    class_scores = values
                class_id = int(np.argmax(class_scores))
                score = float(class_scores[class_id])
                cx, cy, bw, bh = xywh
                x1, y1, x2, y2 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
                coords_are_corners = False
            if class_id < 0 or class_id >= len(self.labels) or float(score) < self.threshold:
                continue
            if coords_are_corners:
                bx1, by1, bx2, by2 = float(x1), float(y1), float(x2), float(y2)
            else:
                bx1, by1, bx2, by2 = float(x1), float(y1), float(x2), float(y2)
            bx1 = max(0, min(width, round((bx1 - pad_x) / scale)))
            bx2 = max(0, min(width, round((bx2 - pad_x) / scale)))
            by1 = max(0, min(height, round((by1 - pad_y) / scale)))
            by2 = max(0, min(height, round((by2 - pad_y) / scale)))
            if bx2 > bx1 and by2 > by1:
                boxes.append([bx1, by1, bx2 - bx1, by2 - by1])
                scores.append(float(score))
                class_ids.append(class_id)

        detections: list[Detection] = []
        for class_id in sorted(set(class_ids)):
            indices = [i for i, cid in enumerate(class_ids) if cid == class_id]
            keep = cv2.dnn.NMSBoxes([boxes[i] for i in indices], [scores[i] for i in indices], self.threshold, 0.45)
            for local_index in keep.flatten().tolist() if len(keep) else []:
                i = indices[local_index]
                x, y, w, h = boxes[i]
                detections.append(Detection(self.labels[class_id], scores[i], x, y, x + w, y + h))
        return detections
