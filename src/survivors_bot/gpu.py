"""Cross-vendor ONNX Runtime provider selection (CUDA, DirectML, then CPU)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeInfo:
    available: tuple[str, ...]
    selected: str
    note: str


def runtime_info(requested: str = "auto") -> RuntimeInfo:
    """Choose an installed inference provider without making GPU libraries mandatory."""
    try:
        import onnxruntime as ort
        available = tuple(ort.get_available_providers())
    except Exception as exc:
        return RuntimeInfo(("CPU/OpenCV",), "CPU/OpenCV", f"ONNX Runtime unavailable: {exc}")

    preferences = {
        "auto": ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"),
        "nvidia": ("CUDAExecutionProvider", "CPUExecutionProvider"),
        "directml": ("DmlExecutionProvider", "CPUExecutionProvider"),
        "cpu": ("CPUExecutionProvider",),
    }.get(requested.lower(), ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"))
    selected = next((provider for provider in preferences if provider in available), None)
    if selected is None:
        return RuntimeInfo(available, "CPU/OpenCV", "No requested ONNX provider is installed; safe CPU fallback.")
    names = {
        "CUDAExecutionProvider": "NVIDIA CUDA",
        "DmlExecutionProvider": "DirectML (AMD/NVIDIA/Intel GPU)",
        "CPUExecutionProvider": "CPU",
    }
    note = f"Selected {names.get(selected, selected)}. Providers available: {', '.join(available)}"
    return RuntimeInfo(available, names.get(selected, selected), note)


def create_session(model_path: str | Path, requested: str = "auto"):
    """Load an ONNX model; try each provider independently and fall back on failure."""
    import onnxruntime as ort

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Detection model not found: {path}")
    available = set(ort.get_available_providers())
    preferences = {
        "auto": ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"),
        "nvidia": ("CUDAExecutionProvider", "CPUExecutionProvider"),
        "directml": ("DmlExecutionProvider", "CPUExecutionProvider"),
        "cpu": ("CPUExecutionProvider",),
    }.get(requested.lower(), ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"))
    failures = []
    for provider in preferences:
        if provider not in available:
            continue
        try:
            options = [{"device_id": 0}] if provider in {"CUDAExecutionProvider", "DmlExecutionProvider"} else [{}]
            session = ort.InferenceSession(str(path), providers=[(provider, options[0])])
            return session, provider
        except Exception as exc:
            failures.append(f"{provider}: {exc}")
    raise RuntimeError("Could not load ONNX model with available providers. " + " | ".join(failures))
