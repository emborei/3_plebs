import numpy as np

import survivors_bot.detector as detector_module
from survivors_bot.detector import OnnxYoloDetector


class FakeInput:
    name = "images"
    shape = [1, 3, 640, 640]


class FakeSession:
    def __init__(self, rows, fail=False):
        self.rows = rows
        self.fail = fail
        self.feed = None

    def get_inputs(self):
        return [FakeInput()]

    def run(self, _outputs, inputs):
        self.feed = inputs["images"]
        if self.fail:
            raise RuntimeError("simulated GPU provider crash")
        return [self.rows]


def _rows():
    # A decoded Nx6 export (boxes, confidence, class index).
    return np.array([[[200, 200, 420, 420, 0.91, 0], [205, 205, 418, 418, 0.75, 0]]], dtype=np.float32)


def _labels(tmp_path):
    path = tmp_path / "labels.txt"
    path.write_text("enemy\nprojectile\nboss\n", encoding="utf-8")
    return path


def test_detector_decodes_boxes_applies_nms_and_preserves_rgb(tmp_path, monkeypatch):
    labels = _labels(tmp_path)
    session = FakeSession(_rows())
    monkeypatch.setattr(detector_module, "create_session", lambda *_args: (session, "CPUExecutionProvider"))
    model = OnnxYoloDetector(tmp_path / "fake.onnx", labels)
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = 255  # red in RGB input
    detections = model.detect(frame)
    assert session.feed[0, 0, 320, 320] == 1.0
    assert session.feed[0, 2, 320, 320] == 0.0
    assert len(detections) == 1
    assert detections[0].label == "enemy"
    assert abs(detections[0].confidence - 0.91) < 1e-5


def test_detector_falls_back_from_accelerator_to_cpu(tmp_path, monkeypatch):
    labels = _labels(tmp_path)
    attempts = []

    def fake_create_session(_path, provider):
        attempts.append(provider)
        if len(attempts) == 1:
            return FakeSession(_rows(), fail=True), "DmlExecutionProvider"
        return FakeSession(_rows()), "CPUExecutionProvider"

    monkeypatch.setattr(detector_module, "create_session", fake_create_session)
    model = OnnxYoloDetector(tmp_path / "fake.onnx", labels, backend="directml")
    detections = model.detect(np.zeros((640, 640, 3), dtype=np.uint8))
    assert detections
    assert model.provider == "CPUExecutionProvider"
    assert attempts == ["directml", "cpu"]
