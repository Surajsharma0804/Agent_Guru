"""Every rich-content dispatch key must be an intent the system can produce.

RichContentGenerator.INTENT_CONTENT_MAP dispatches on the *string value* of
Intent.intent_type. Intent.intent_type is typed IntentType, so pydantic
rejects any value outside that enum before the generator is ever reached --
which means a map key with no matching enum member is unreachable code that
silently does nothing.

That is exactly what had happened: eight of the map's keys ("show_photos",
"take_photo", "show_stats", "show_report", "show_calendar", "show_results",
"show_directions", "weather_forecast") matched no IntentType member and
appeared nowhere else in the codebase, so the gallery, chart, map, table and
carousel content types they select could never be produced. The generator side
was written and tested; only the vocabulary was missing.

This test is the guard that keeps the two halves from drifting apart again.
"""

from Agent_Guru.reasoning.models.intent import IntentType
from Agent_Guru.reasoning.response.rich_content_generator import RichContentGenerator


def test_every_content_map_key_is_a_real_intent_type() -> None:
    """A key no Intent can carry is a dispatch branch that never runs."""
    known = {member.value for member in IntentType}
    unreachable = sorted(k for k in RichContentGenerator.INTENT_CONTENT_MAP if k not in known)

    assert not unreachable, (  # nosec B101
        "These INTENT_CONTENT_MAP keys are not IntentType values, so no valid "
        f"Intent can ever select them: {unreachable}. Either add the member to "
        "IntentType or drop the mapping -- do not leave a dead branch."
    )


def test_content_map_is_not_empty() -> None:
    """Guard against the previous test passing because the map was gutted."""
    assert len(RichContentGenerator.INTENT_CONTENT_MAP) >= 20  # nosec B101


def test_every_content_type_is_reachable() -> None:
    """A ContentType no mapping selects is a generator branch nothing can call.

    BUTTON_GROUP, QUICK_REPLY and FORM were in exactly that state: each had a
    complete _generate_*() implementation and direct unit tests, but no entry
    in INTENT_CONTENT_MAP, so generate() could never produce them.
    """
    from Agent_Guru.reasoning.response.rich_content_generator import ContentType

    selectable = set(RichContentGenerator.INTENT_CONTENT_MAP.values())
    unreachable = sorted(c.value for c in ContentType if c not in selectable)

    assert not unreachable, (  # nosec B101
        f"No intent selects these content types: {unreachable}. Their "
        "_generate_*() implementations cannot be reached through generate()."
    )


def test_every_template_declares_its_own_placeholders() -> None:
    """A placeholder missing from `variables` used to crash response generation.

    _format_template() falls back to substituting empty strings when a
    variable is absent from the result data, but it used to fill only the
    names listed in ResponseTemplate.variables. The play_music template
    declared variables=["song"] while its text was
    "Now playing {song} by {artist}", so a result with no artist raised
    KeyError, entered the fallback, and raised KeyError('artist') again from
    inside it. The fallback now reads placeholders from the template string,
    and this test keeps the declarations honest as well.
    """
    import string

    from Agent_Guru.reasoning.response.template_generator import TemplateGenerator

    generator = TemplateGenerator()
    gaps = {}
    for key, template in generator._templates.items():
        for text in (template.text_template, template.voice_template):
            placeholders = {
                field.split(".")[0].split("[")[0]
                for _, field, _, _ in string.Formatter().parse(text)
                if field
            }
            missing = sorted(placeholders - set(template.variables))
            if missing:
                gaps[key] = missing

    assert not gaps, (  # nosec B101
        f"These templates use placeholders they do not declare: {gaps}"
    )
