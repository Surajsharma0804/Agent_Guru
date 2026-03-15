"""
Example: Switching between Guru and Maya personalities.

Run:
    python -m Agent_Guru.avatar.examples.dual_personality
"""

from __future__ import annotations

from Agent_Guru.avatar import GuruAvatarSystem, PersonalityType


def main() -> None:
    system = GuruAvatarSystem(render_backend="headless")
    system.initialize()

    for personality in (PersonalityType.GURU, PersonalityType.MAYA, PersonalityType.GURU):
        system.set_personality(personality)
        state = system.get_current_state()
        frame = system.render_frame()
        print(
            f"Personality: {personality.value:4s} | "
            f"Formality: {state.personality.formality:.2f} | "
            f"Frame: {frame.shape}"
        )

    system.stop()


if __name__ == "__main__":
    main()
