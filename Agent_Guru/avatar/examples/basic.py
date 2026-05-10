"""Example: Basic avatar display (headless).

Run:
    python -m Agent_Guru.avatar.examples.basic
"""

from __future__ import annotations

from Agent_Guru.avatar import GuruAvatarSystem


def main() -> None:
    system = GuruAvatarSystem(render_backend="headless")
    system.initialize()

    for _i in range(10):
        system.render_frame()

    system.stop()


if __name__ == "__main__":
    main()
