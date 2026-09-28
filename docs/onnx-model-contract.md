# Optional vision-model contract

The desktop app can run without a model (screen capture + OCR + movement heuristic). Danger-aware object detection is optional and requires user-provided model files; the repository does **not** ship game-trained weights.

## Inputs

- An ONNX detection model exported for YOLOv5/YOLOv8-style object detection.
- A sidecar `.txt` file with one class name per line, in the exact output-class order.
- RGB frame input, float32, NCHW, square (commonly 640 × 640), letterbox-compatible.
- Common raw YOLO outputs are supported; output must be a single tensor with boxes and per-class scores. More exotic segmentation or end-to-end NMS exports are not supported by this prototype adapter.

Example labels (train and validate these; this is a schema illustration, not a provided model):

```text
enemy
projectile
boss
health_bar
boss_nameplate
telegraph
xp
```

Current tactical mapping recognizes labels containing `enemy`, `monster`, `zombie`, `bat`, `skeleton`, `projectile`, `shot`, `bullet`, `telegraph`, `warning`, `hazard`, `explosion`, `boss`, or `reaper`. The debounced boss state additionally consumes model labels containing `health_bar` and `boss_nameplate`; a boss sprite alone only raises suspicion, and a timer cue can never establish an active fight. Unknown labels are drawn in the preview but do not affect movement.

## GPU behavior

Inference provider order in Auto mode is NVIDIA CUDA, DirectML, then CPU. If an accelerator provider fails during inference, the detector retries on CPU. DirectML is the cross-vendor Windows option for supported DirectX 12 GPUs; actual compatibility depends on GPU driver, model operators, and installed ONNX Runtime package. GPU acceleration is optional; screen capture is vendor-neutral.

## Before enabling danger mode

1. Validate class names and bounding boxes on saved frames from the exact game resolution and content version.
2. Check false positives from attack effects and UI art.
3. Confirm the debug overlay tracks moving threats correctly at several frame rates.
4. Keep the tool paused and use Preview/dry observation until detections look sound.
5. Never enable model-based steering just because a model loads; a compatible output tensor does not imply useful accuracy.
