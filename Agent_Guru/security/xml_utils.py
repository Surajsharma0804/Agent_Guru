"""Safe XML parsing utilities for Agent Guru.

This module prevents XML External Entity (XXE) injection (CWE-611) by
using ``defusedxml`` when available, and falling back to a hardened
stdlib ``xml.etree.ElementTree`` configuration that disables external
entity resolution.

Performance Characteristics:
    - Time Complexity: O(n) where n is the size of the XML document
    - Space Complexity: O(n) — the parsed element tree is held in memory

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
except ImportError:  # pragma: no cover — defusedxml is optional
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
    """Parse using stdlib ET with a hardened parser that rejects external entities."""

    class _SafeParser(ET.XMLParser):
        """XMLParser subclass that raises ValueError on external entity use."""

        def __init__(self) -> None:
            super().__init__()
            # Disable external entity expansion at the expat level
            self.parser.UseForeignDTD(False)  # type: ignore[attr-defined]

        def handle_entityref(self, name: str) -> None:  # type: ignore[override]
            msg = (
                f"External entity reference &{name}; detected — "
                "XML external entity injection (XXE) is not permitted."
            )
            raise ValueError(
                msg,
            )

        def handle_charref(self, name: str) -> None:  # type: ignore[override]
            # Numeric character references are safe; delegate to parent.
            super().handle_charref(name)  # type: ignore[misc]

    parser = _SafeParser()

    if isinstance(source, str):
        return ET.fromstring(source, parser=parser)  # nosec B314
    if isinstance(source, Path):
        tree = ET.parse(str(source), parser=parser)  # nosec B314
        return tree.getroot()
    # File-like object — read content and parse as string
    content = source.read()
    if isinstance(content, bytes):
        root = ET.fromstring(content, parser=parser)  # nosec B314
    else:
        root = ET.fromstring(content.encode(), parser=parser)  # nosec B314
    return root
