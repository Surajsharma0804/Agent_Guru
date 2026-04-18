"""
Example: Real-time face recognition from a webcam.

Usage:
    python -m Agent_Guru.vision.examples.recognize_webcam \\
        [--config path/to/config.yaml] \\
        [--camera 0]

Press 'q' to quit.

Requirements: 19.1, 31.2
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-time webcam face recognition")
    parser.add_argument("--config", default=None, help="Optional YAML/JSON config file")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0)")
    args = parser.parse_args()

    try:
        import cv2  # type: ignore[import]
    except ImportError as e:
        print("ERROR: opencv-python is required. Install with: pip install opencv-python", file=sys.stderr)
        return 1

    from Agent_Guru.vision.engine import GuruVisionEngine

    engine = GuruVisionEngine(config_path=args.config)

    def on_ready(data: dict) -> None:
        print("GuruVision engine ready.")

    engine.register_callback("system_ready", on_ready)
    engine.initialize()
    engine.setup_signal_handlers()

    cap = engine.open_video_source(args.camera)

    print("Press 'q' to quit.")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            result = engine.process_frame(frame)

            for face in result.faces:
                x, y, w, h = (int(v) for v in face.bbox)
                label = f"{face.identity} ({face.confidence:.2f})"
                color = (0, 255, 0) if face.identity != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, label, (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                if face.emotion:
                    cv2.putText(
                        frame, face.emotion, (x, y + h + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1,
                    )

            cv2.imshow("GuruVision", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        engine.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
