"""Safe XML parsing utilities for Agent Guru.

This module prevents XML External Entity (XXE) injection (CWE-611) by
using ``defusedxml`` when available, and falling back to a hardened
stdlib ``xml.etree.ElementTree`` configuration that disables external
entity resolution.

Performance Characteristics:
    - Time Complexity: O(n) where n is the size of the XML document
    - Space Complexity: O(n) - the parsed element tree is held in memory

Security Guarantees:
    - External entity declarations are disabled
    - DTD processing is disabled when ``defusedxml`` is available
    - ``ValueError`` is raised for any source that triggers entity resolution

Requirements: 2.18
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from typing import IO

# Attempt to import defusedxml; fall back to stdlib with manual hardening.
try:
    import defusedxml.ElementTree as _defused_ET  # type: ignore[import-untyped]  # noqa: F401

    _DEFUSEDXML_AVAILABLE = True
except ImportError:  # pragma: no cover - defusedxml is optional
    _DEFUSEDXML_AVAILABLE = False


def safe_xml_parse(source: str | Path | IO[bytes] | IO[str]) -> ET.Element:
    """Parse an XML document safely, with external entities disabled.

    Uses ``defusedxml.ElementTree.parse()`` when the library is installed.
    Falls back to stdlib ``xml.etree.ElementTree`` with a custom
    ``XMLParser`` that raises ``ValueError`` if any external entity or DTD
    reference is encountered.

    Args:
        source: The XML source.  May be:
            - A ``str`` containing raw XML markup.
            - A ``pathlib.Path`` pointing to an XML file.
            - A binary or text file-like object.

    Returns:
        The root ``xml.etree.ElementTree.Element`` of the parsed document.

    Raises:
        ValueError: If the source contains an external entity reference or
                    any other construct that ``defusedxml`` considers unsafe.
        ET.ParseError: If the source is not well-formed XML.

    Example::

        from Agent_Guru.security.xml_utils import safe_xml_parse

        root = safe_xml_parse("<config><key>value</key></config>")
        print(root.find("key").text)

    """
    if _DEFUSEDXML_AVAILABLE:
        return _parse_with_defusedxml(source)
    return _parse_with_stdlib(source)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_with_defusedxml(source: str | Path | IO[bytes] | IO[str]) -> ET.Element:
    """Parse using defusedxml (preferred path)."""
    try:
        if isinstance(source, str):
            # defusedxml.fromstring for raw markup strings
            import defusedxml.ElementTree as _def_ET  # type: ignore[import-untyped]

            return _def_ET.fromstring(source)
        if isinstance(source, Path):
            import defusedxml.ElementTree as _def_ET  # type: ignore[import-untyped]

            tree = _def_ET.parse(str(source))
            return tree.getroot()
        # File-like object
        import defusedxml.ElementTree as _def_ET  # type: ignore[import-untyped]

        tree = _def_ET.parse(source)
        return tree.getroot()
    except Exception as exc:
        # defusedxml raises its own exception hierarchy; re-raise as ValueError
        # so callers have a single exception type to handle for XXE attempts.
        if "entity" in str(exc).lower() or "dtd" in str(exc).lower() or "xxe" in str(exc).lower():
            msg = f"Unsafe XML content detected: {exc}"
            raise ValueError(msg) from exc
        raise


def _parse_with_stdlib(source: str | Path | IO[bytes] | IO[str]) -> ET.Element:
    """Parse using a hardened raw expat parser (defusedxml unavailable).

    This used to subclass ``xml.etree.ElementTree.XMLParser`` and reach into
    ``self.parser`` (the underlying expat parser object) to call
    ``UseForeignDTD(False)``, plus override ``handle_entityref``/
    ``handle_charref`` expecting ET to invoke them for entity references.
    Neither worked: since Python 3.8, ``ET.XMLParser`` no longer exposes the
    expat parser as a public ``.parser`` attribute at all (that instantiation
    raised ``AttributeError`` unconditionally), and ``ET.XMLParser`` has
    never called methods named ``handle_entityref``/``handle_charref`` in
    the first place - those names belong to the unrelated, long-removed
    ``xmllib.XMLParser`` API, not to ``ET.XMLParser``'s target-callback
    contract (``start``/``end``/``data``/``comment``/``pi``/``close``). So
    even before the ``AttributeError``, the "hardening" itself could never
    have fired. Net effect: this fallback path - reached only when
    ``defusedxml`` (a hard ``requirements.txt`` dependency) is somehow
    unavailable - crashed on every single call rather than providing any
    protection, turning every XML parse in the whole application into a
    guaranteed failure in that situation instead of a safe one.

    This replacement talks to ``xml.parsers.expat`` directly, which still
    exposes full handler configuration, and rejects any DOCTYPE declaration
    outright via ``StartDoctypeDeclHandler`` before any entities it might
    declare are even parsed. That blocks both external-entity XXE (e.g.
    ``<!ENTITY xxe SYSTEM "file:///etc/passwd">``) and internal-entity
    "billion laughs" expansion DoS at the same point, since a document with
    no entity declarations at all cannot mount either attack.
    ``ExternalEntityRefHandler`` is also rejected as defense in depth in
    case a DOCTYPE construct ever reaches that callback by some other path.
    This is intentionally stricter than ``defusedxml``'s own default
    posture (which permits declaration-free DTDs) - that tradeoff is
    accepted here because this code path exists only as a fallback for an
    already-exceptional situation, and "no DOCTYPE, ever" is far easier to
    verify correct than replicating defusedxml's full entity-handling
    policy by hand.
    """
    import xml.parsers.expat as expat

    parser = expat.ParserCreate()
    builder = ET.TreeBuilder()

    def _reject_doctype(
        doctype_name: str,
        system_id: str | None,
        public_id: str | None,
        has_internal_subset: bool,  # noqa: FBT001
    ) -> None:
        msg = (
            f"DOCTYPE declaration detected (name={doctype_name!r}) - "
            "DTDs are not permitted (XML external entity / entity-expansion "
            "protection)."
        )
        raise ValueError(msg)

    def _reject_external_entity(
        context: str,
        base: str | None,
        system_id: str | None,
        public_id: str | None,
    ) -> None:
        msg = (
            f"External entity reference detected (system_id={system_id!r}) - "
            "XML external entity injection (XXE) is not permitted."
        )
        raise ValueError(msg)

    parser.StartDoctypeDeclHandler = _reject_doctype
    parser.ExternalEntityRefHandler = _reject_external_entity
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data

    if isinstance(source, str):
        data: bytes | str = source
    elif isinstance(source, Path):
        data = source.read_bytes()
    else:
        # File-like object (bytes or str content, either is fine - expat's
        # Parse() accepts both).
        data = source.read()

    try:
        parser.Parse(data, True)  # noqa: FBT003 - expat's own `isfinal` positional arg
    except expat.ExpatError as exc:
        # Malformed (but not DOCTYPE/entity-related) XML - surface the same
        # exception type ET.fromstring()/ET.parse() would have raised, so
        # callers of safe_xml_parse() see a consistent contract regardless
        # of which backend handled the parse.
        raise ET.ParseError(str(exc)) from exc

    return builder.close()
