from __future__ import annotations

import argparse
import sys

from .policy import choose_best


def _do_preview(monitor: int) -> None:
    from .vision import analyze, capture_monitor

    image = capture_monitor(monitor)
    observation = analyze(image)
    print(f"Captured {observation.width}x{observation.height}")
    print(f"Visible OCR: {observation.text or '(no text recognized)'}")
    print(f"Level-up menu: {observation.level_up_menu}")
    for choice in observation.choices:
        print(f"  {choice.label:20} at ({choice.x}, {choice.y}), OCR confidence {choice.confidence:.2f}")
    best = choose_best(list(observation.choices))
    print(f"Recommended: {best.label if best else '(none)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Survivors Buddy: external screen vision and supervised controller tool")
    parser.add_argument("--gui", action="store_true", help="open the desktop configuration tool (default)")
    parser.add_argument("--preview", action="store_true", help="capture/OCR once; do not send input")
    parser.add_argument("--run", action="store_true", help="start a supervised command-line run")
    parser.add_argument("--monitor", type=int, default=1, help="monitor number (1 is primary)")
    parser.add_argument("--duration", type=int, default=600, help="hard session limit in seconds")
    parser.add_argument("--interval", type=float, default=0.8, help="seconds between screen scans")
    parser.add_argument("--model", default="", help="optional game-specific ONNX model")
    parser.add_argument("--labels", default="", help="optional model class-label .txt")
    parser.add_argument("--backend", choices=("auto", "nvidia", "directml", "cpu"), default="auto")
    parser.add_argument("--danger-mode", action="store_true", help="use model detections for evasive movement")
    args = parser.parse_args()
    if args.duration <= 0 or args.interval < 0.25:
        parser.error("duration must be positive and interval must be at least 0.25 seconds")
    if args.gui or not (args.preview or args.run):
        try:
            from .gui import launch
            raise SystemExit(launch())
        except ImportError as exc:
            parser.exit(2, f"Desktop UI dependencies unavailable. Install the app dependencies. ({exc})\n")
    try:
        if args.preview:
            _do_preview(args.monitor)
        elif args.run:
            from .engine import BotEngine
            import threading
            BotEngine().run(
                monitor=args.monitor,
                duration_seconds=args.duration,
                interval=args.interval,
                stop_requested=lambda: False,
                model_path=args.model,
                labels_path=args.labels,
                backend=args.backend,
                danger_mode=args.danger_mode,
            )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
