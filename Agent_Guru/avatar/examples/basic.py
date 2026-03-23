"""
Example: Basic avatar display (headless).

Run:
    python -m Agent_Guru.avatar.examples.basic
"""

from __future__ import annotations

from Agent_Guru.avatar import GuruAvatarSystem


def main() -> None:
    system = GuruAvatarSystem(render_backend="headless")
    system.initialize()

    print("Rendering 10 frames with Guru personality...")
    for i in range(10):
        frame = system.render_frame()
        print(f"  Frame {i+1}: shape={frame.shape}")

    system.stop()
    print("Done.")


if __name__ == "__main__":
    main()
