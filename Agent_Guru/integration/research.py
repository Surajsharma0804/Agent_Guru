"""Research with sources: the assistant's own search tools, and checking what an answer cites.

The tools are served inside this process through MCPToolbox (a ServerConfig
with local=ResearchTools(...)), so they are listed, allowed, checked,
guarded and audited by the same path as a tool on an MCP server, and the
tool loop (integration/tool_loop.py) uses them like any other. All four
only read:

    web_research(query)        search the web and read the top pages
    read_page(source)          read more of a page a search returned
    weather(place)             the weather now and three days ahead, from Open-Meteo
    search_documents(query)    the owner's documents (platform/features/documents.py)
    search_memory(query)       what the owner said in earlier conversations

Every source a tool returns is entered in the turn's register under an id
(S1 for the web, D1 for a document, M1 for a memory), with its title, URL,
the passage the model was shown, the provider, when it was retrieved, and
how much of it was read: "snippet" (only the search engine's summary) or
"page" (the page itself). Only ids in the register can be cited.

web_research reads the top pages itself, in the same call: gemma4 did not
chain a search into a second lookup in any of six evaluation runs, so
asking it to search and then call read_page would mostly have stopped at
the snippets.

check_answer() is run on the model's answer before anyone sees it. A
citation to an id the turn never returned is removed, and so is any URL
that is not a returned source's URL; a cited sentence holding a number the
cited sources do not contain is reported as not matched; and the sources
actually cited are listed under the answer, each with how much of it was
read. A spoken answer is said without the ids and URLs.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Server name the research tools are listed under; the policy actions are
#: external:mcp:guru:<tool>, so they pass the same policy check as any tool.
SERVER_NAME = "guru"
#: Characters of each source's passage shown to the model.
PASSAGE_CHARS = 900
#: Pages web_research reads itself, of the results it finds.
PAGES_READ = 2


@dataclass(slots=True)
class Source:
    """One source a research tool returned in this turn."""

    id: str
    kind: str  # "web", "document" or "memory"
    title: str
    passage: str
    retrieved_at: float
    url: str | None = None
    provider: str = ""
    #: "snippet", "page", "page_truncated", "document" or "memory".
    read: str = "snippet"
    updated: str | None = None


@dataclass(slots=True)
class SourceRegister:
    """The sources one turn's tools returned, by id."""

    sources: dict[str, Source] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, **fields: Any) -> Source:
        if kind == "web" and fields.get("url"):
            for existing in self.sources.values():
                if existing.url == fields["url"]:
                    return existing
        prefix = {"web": "S", "document": "D", "memory": "M"}[kind]
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        source = Source(id=f"{prefix}{self._counts[prefix]}", kind=kind, retrieved_at=time.time(), **fields)
        self.sources[source.id] = source
        return source


_REGISTER: contextvars.ContextVar[SourceRegister | None] = contextvars.ContextVar("agent_guru_sources", default=None)


def begin_turn() -> tuple[SourceRegister, contextvars.Token[SourceRegister | None]]:
    """A fresh register for the turn running in this task; reset it with the token afterwards."""
    register = SourceRegister()
    return register, _REGISTER.set(register)


def end_turn(token: contextvars.Token[SourceRegister | None]) -> None:
    _REGISTER.reset(token)


def _register() -> SourceRegister:
    register = _REGISTER.get()
    if register is None:
        # A call outside a turn (the `mcp call` command): the sources are
        # still numbered, they are just not checked against an answer.
        register = SourceRegister()
        _REGISTER.set(register)
    return register


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _terms_lower(text: str) -> set[str]:
    """Every word of *text*, lower-cased: a name may be written in lower case in a source."""
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def best_passage(text: str, query: str, limit: int = PASSAGE_CHARS) -> str:
    """The page's opening and the paragraph sharing most words with *query*, within *limit*.

    The paragraph most like the question alone was often the wrong one:
    for "who is the current prime minister of India" it was the one
    defining the office ("the head of government is the prime minister"),
    while the name was in the article's opening.
    """
    terms = _terms(query)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(p.strip()) > 40] or [text.strip()]
    ranked = sorted(paragraphs[1:], key=lambda p: (-len(terms & _terms(p)), paragraphs.index(p)))[:2]
    opening = paragraphs[0][: limit // 4]
    room = limit - len(opening)
    # Room goes to the best match first: given in page order, a long
    # paragraph before it used all of it, and the paragraph naming the
    # current prime minister (the best match) was cut away.
    chosen: dict[str, str] = {}
    for paragraph in ranked:
        if room <= 40:
            break
        chosen[paragraph] = paragraph[: room - 5]
        room -= len(chosen[paragraph]) + 5
    return "\n...\n".join([opening, *(chosen[p] for p in sorted(chosen, key=paragraphs.index))])


async def _guarded(text: str, source: str) -> str | None:
    from Agent_Guru.llm.security import guard_external_text_async

    return await guard_external_text_async(text, source) or None


def _format(source: Source) -> str:
    read = {"snippet": "search snippet only", "page": "page read", "page_truncated": "page read in part",
            "document": "owner's document", "memory": "owner said this earlier; not checked"}[source.read]
    head = f"[{source.id}] {source.title}"
    if source.url:
        head += f" <{source.url}>"
    extra = f"; updated {source.updated}" if source.updated else ""
    return f"{head} ({read}{extra})\n{source.passage}"


#: Ends each research tool's output: how to refer to the sources, so the
#: answer can be held to them. Without it gemma4 wrote "according to what I
#: found" and cited nothing, leaving nothing to check.
_CITE = ("Answer from these sources only, and put the id of the source each fact comes from right after it, "
         "like [S1]. If they do not answer the question, or look out of date, say so.")

_QUERY = {"type": "object", "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 300}},
          "required": ["query"], "additionalProperties": False}


class ResearchTools:
    """The four research tools, served in-process (see the module docstring)."""

    def __init__(self, *, documents: Any = None, memory: Any = None) -> None:
        self._documents = documents
        self._memory = memory

    def tool_list(self) -> list[dict[str, Any]]:
        tools = [
            {"name": "web_research", "description": (
                "Search the web for a question and read the top pages. Returns numbered sources [S1], [S2] with "
                "passages; cite them by id. Use for facts you do not know or that change over time. Not for the "
                "weather: use weather."),
             "annotations": {"readOnlyHint": True, "openWorldHint": True}, "inputSchema": _QUERY},
            {"name": "weather", "description": (
                "The weather now and for the next three days in a named place, from the Open-Meteo weather "
                "service: temperature, conditions, rain chance. Use this for every weather question, not "
                "web_research. Returns one source [S1]; say the place it names, which may differ from the "
                "name asked about."),
             "annotations": {"readOnlyHint": True, "openWorldHint": True},
             "inputSchema": {"type": "object", "properties": {"place": {"type": "string", "minLength": 2, "maxLength": 100}},
                             "required": ["place"], "additionalProperties": False}},
            {"name": "read_page", "description": (
                "Read more of a web source an earlier web_research returned, by its id (for example S2)."),
             "annotations": {"readOnlyHint": True, "openWorldHint": True},
             "inputSchema": {"type": "object", "properties": {
                 "source": {"type": "string", "minLength": 2, "maxLength": 6},
                 "focus": {"type": "string", "maxLength": 200}},
                 "required": ["source"], "additionalProperties": False}},
        ]
        if self._documents is not None:
            tools.append({"name": "search_documents", "description": (
                "Search the documents the owner added (leases, warranties, itineraries). Returns sources [D1]..."),
                "annotations": {"readOnlyHint": True}, "inputSchema": _QUERY})
        if self._memory is not None:
            tools.append({"name": "search_memory", "description": (
                "Search what the owner said in earlier conversations. Returns sources [M1]...; these are the "
                "owner's own words, not checked facts."),
                "annotations": {"readOnlyHint": True}, "inputSchema": _QUERY})
        return tools

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        handler = {
            "web_research": self._web_research, "read_page": self._read_page, "weather": self._weather,
            "search_documents": self._search_documents, "search_memory": self._search_memory,
        }.get(name)
        if handler is None:
            return f"no tool named {name}", True
        return await handler(**arguments)

    async def _web_research(self, query: str) -> tuple[str, bool]:
        from Agent_Guru.platform.features.web_fetch import fetch_page
        from Agent_Guru.platform.features.web_search import search_sources

        outcome = await search_sources(query, limit=4)
        if outcome.status == "failed":
            return "The search failed: " + "; ".join(f"{k}: {v}" for k, v in outcome.errors.items()), True
        if not outcome.results:
            return "The search found nothing for this question.", False
        pages = await asyncio.gather(*(fetch_page(r.url) for r in outcome.results[:PAGES_READ]))
        register, lines, withheld = _register(), [], 0
        for n, result in enumerate(outcome.results):
            page = pages[n] if n < len(pages) else None
            if page is not None and page.status in {"complete", "truncated"} and page.text:
                text, read = best_passage(page.text, query), "page" if page.status == "complete" else "page_truncated"
                url = page.final_url or result.url
            else:
                text, read, url = result.snippet, "snippet", result.url
            passage = await _guarded(text, f"web source {url}")
            if passage is None:
                withheld += 1
                continue
            source = register.add("web", title=result.title, passage=passage, url=url,
                                  provider=result.provider, read=read, updated=result.updated)
            lines.append(_format(source))
        notes = []
        if outcome.status == "partial":
            notes.append("Some search providers failed (" + "; ".join(f"{k}: {v}" for k, v in outcome.errors.items())
                         + "); these results may be incomplete.")
        if withheld:
            notes.append(f"{withheld} result(s) withheld because they tried to give instructions.")
        if not lines:
            return " ".join(notes) or "No usable results.", False
        return "\n\n".join([*notes, *lines, _CITE]), False

    async def _weather(self, place: str) -> tuple[str, bool]:
        """Open-Meteo's report for *place*, as one numbered web source.

        Weather was answered from web_research, whose pages were about the
        climate or a year old: "what's the weather in Delhi" came back with
        no forecast. The report is a source like any web page, so the answer
        cites it and its numbers are held to it, and the place names it
        carries pass the same injection guard as page text.
        """
        from Agent_Guru.platform.features.weather import WeatherError, get_weather

        try:
            report = await get_weather(place)
        except WeatherError as exc:
            return str(exc), True
        passage = await _guarded(report.summary(), f"weather service {report.url}")
        if passage is None:
            return "The weather service's answer was withheld because it tried to give instructions.", True
        source = _register().add("web", title=f"Open-Meteo forecast for {report.place}", passage=passage,
                                 url=report.url, provider="open-meteo", read="page", updated=report.observed_at)
        note = ("Say which place this is: it is the place the service resolved, which may not be the one meant."
                if report.matches > 1 else "")
        return "\n\n".join(part for part in (_format(source), note, _CITE) if part), False

    async def _read_page(self, source: str, focus: str = "") -> tuple[str, bool]:
        from Agent_Guru.platform.features.web_fetch import fetch_page

        register = _register()
        known = register.sources.get(source.strip().upper())
        if known is None or known.kind != "web" or not known.url:
            return f"{source} is not a web source returned in this conversation turn.", True
        page = await fetch_page(known.url)
        if page.status not in {"complete", "truncated"} or not page.text:
            return f"Could not read {known.id}: {page.status} ({page.error})", True
        passage = await _guarded(best_passage(page.text, focus or known.title, limit=PASSAGE_CHARS * 2),
                                 f"web source {known.url}")
        if passage is None:
            return f"{known.id} was withheld because it tried to give instructions.", False
        known.passage, known.read = passage, "page" if page.status == "complete" else "page_truncated"
        return f"{_format(known)}\n\n{_CITE}", False

    async def _search_documents(self, query: str) -> tuple[str, bool]:
        passages = await self._documents.search(query)
        register, lines = _register(), []
        for p in passages:
            passage = await _guarded(p.text, f"document {p.document}")
            if passage:
                lines.append(_format(register.add("document", title=p.document, passage=passage[:PASSAGE_CHARS],
                                                  provider="documents", read="document")))
        return ("\n\n".join([*lines, _CITE]) if lines else "Nothing in the owner's documents matches."), False

    async def _search_memory(self, query: str) -> tuple[str, bool]:
        found = await self._memory.search(query, limit=3)
        register, lines = _register(), []
        for item in found or []:
            said = str(item.get("user_message", "")).strip()
            if said:
                lines.append(_format(register.add("memory", title="earlier conversation", passage=said[:PASSAGE_CHARS],
                                                  provider="memory", read="memory")))
        return ("\n\n".join([*lines, _CITE]) if lines else "Nothing the owner said before matches."), False


# ---------------------------------------------------------------------------
# Checking an answer against the sources
# ---------------------------------------------------------------------------

_CITATION = re.compile(r"\[((?:[SDM]\d{1,3})(?:\s*[,;]\s*[SDM]\d{1,3})*)\]")
#: A URL never ends in punctuation: "see https://x.org/a." ends the sentence
#: with its full stop, which used to be taken as part of the URL.
_URL = re.compile(r"<?https?://[^\s<>()\]]*[^\s<>()\].,;:!?'\"]>?")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(slots=True)
class CheckedAnswer:
    """The answer as written and as spoken, and what the check found."""

    text: str
    spoken: str
    cited: list[Source] = field(default_factory=list)
    unknown_ids: list[str] = field(default_factory=list)
    removed_urls: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text)}


#: Capitalised words that start sentences or are common, not names.
_NOT_NAMES = frozenset({
    "the", "a", "an", "i", "it", "he", "she", "they", "we", "you", "this", "that", "these", "those", "and", "but",
    "or", "so", "yes", "no", "hey", "yo", "oh", "okay", "ok", "well", "also", "honestly", "according", "based",
    "as", "in", "on", "at", "for", "from", "by", "with", "about", "after", "before", "since", "there", "here",
    "what", "who", "when", "where", "which", "why", "how", "if", "then", "dude", "bro", "man", "sources", "source",
})


def _names(text: str) -> set[str]:
    """Capitalised words in *text* that are not common sentence words: the names it states."""
    return {w.lower() for w in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text) if w.lower() not in _NOT_NAMES}


def check_answer(answer: str, register: SourceRegister) -> CheckedAnswer:
    """Hold *answer* to the sources in *register* (see the module docstring)."""
    known_urls = {s.url for s in register.sources.values() if s.url}
    unknown: list[str] = []
    cited_ids: list[str] = []

    def keep(match: re.Match[str]) -> str:
        ids = [i.strip().upper() for i in re.split(r"[,;]", match.group(1))]
        good = [i for i in ids if i in register.sources]
        unknown.extend(i for i in ids if i not in register.sources)
        cited_ids.extend(i for i in good if i not in cited_ids)
        return "[" + ", ".join(good) + "]" if good else ""

    text = _CITATION.sub(keep, answer)
    removed: list[str] = []

    def url(match: re.Match[str]) -> str:
        found = match.group(0).strip("<>").rstrip(".,;")
        if found in known_urls:
            return match.group(0)
        removed.append(found)
        return ""

    text = _URL.sub(url, text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    unmatched = []
    for sentence in _SENTENCE.split(text):
        ids = [i.strip() for m in _CITATION.finditer(sentence) for i in re.split(r"[,;]", m.group(1))]
        if not ids:
            continue
        # The numbers and names a cited sentence states must be in what it
        # cites. gemma4 named the current prime minister and cited a search
        # snippet that never named him, the model having supplied the name
        # itself.
        bare = _CITATION.sub("", sentence)
        passages = " ".join(register.sources[i].passage + " " + register.sources[i].title
                            for i in ids if i in register.sources)
        if (_numbers(bare) - _numbers(passages)) or (_names(bare) - _names(passages) - _terms_lower(passages)):
            unmatched.append(sentence.strip())

    cited = [register.sources[i] for i in cited_ids]
    spoken = re.sub(r"\s{2,}", " ", _URL.sub("", _CITATION.sub("", text))).strip()
    spoken = re.sub(r"\s+([.,;!?])", r"\1", spoken)
    note = " I couldn't match every detail of that to my sources." if unmatched else ""
    if cited:
        lines = []
        for source in cited:
            read = {"snippet": "search snippet only", "page": "page read", "page_truncated": "page read in part",
                    "document": "your document", "memory": "something you said earlier"}[source.read]
            where = f" - {source.url}" if source.url else ""
            lines.append(f"[{source.id}] {source.title}{where} ({read})")
        text = f"{text}{note}\n\nSources:\n" + "\n".join(lines)
    else:
        text += note
    return CheckedAnswer(text=text, spoken=spoken + note, cited=cited, unknown_ids=unknown,
                         removed_urls=removed, unmatched=unmatched)


def strip_citations(sentence: str) -> str:
    """A sentence as it is spoken: without source ids and URLs."""
    spoken = re.sub(r"\s{2,}", " ", _URL.sub("", _CITATION.sub("", sentence)))
    return re.sub(r"\s+([.,;!?])", r"\1", spoken)


def research_server() -> Any:
    """The ServerConfig for the research tools; local is filled in by the caller."""
    from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

    rules = {name: ToolRule(allow=True, risk=ToolRisk.READ_ONLY)
             for name in ("web_research", "read_page", "weather", "search_documents", "search_memory")}
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=25.0, tools=rules)
