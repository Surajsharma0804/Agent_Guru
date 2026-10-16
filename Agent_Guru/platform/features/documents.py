"""Documents the owner gives the assistant to answer from.

The assistant could answer only from the model's own knowledge, what the
owner had said in earlier conversations, and a web search. A rental
agreement, a warranty card or a trip itinerary on the owner's own disk was
out of reach: "how much notice do I have to give my landlord" got a general
answer about notice periods, not the one in the owner's lease.

A document is added with ``python -m Agent_Guru documents add <file>``. Its
text (read by presentation.read_source_text: .txt, .md, .docx, .pdf and
other plain text) is split into passages of a few paragraphs, and each
passage is embedded with the model memory search already uses. On a voice
turn the passages close in meaning to the question are put in the prompt,
named by the document they came from. A document that has not changed since
it was added is not read again; one that has is replaced.

Passages are the owner's files, but their text was written by someone else
(a landlord, a shop, a booking site), so it passes the same injection guard
as web results before it reaches the model.

One SQLite file holds everything, opened and closed per call as
utils.sqlite.open_sqlite explains. The embeddings are read into one numpy
matrix the first time a question is asked and kept until a document is
added or removed, so a question costs one embedding and one matrix product.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from Agent_Guru.utils.secure_file import restrict_file_permissions
from Agent_Guru.utils.sqlite import open_sqlite

logger = logging.getLogger(__name__)

#: A passage holds whole paragraphs up to about this many characters.
#: Measured with scripts/document_recall_eval.py (24 questions, 5
#: documents): at 700 characters a hotel's booking reference shared a
#: passage with the flight times and scored 0.22 against "what is the hotel
#: booking reference", and the best cutoff got 21 questions right; at 300
#: every cutoff from 0.30 to 0.40 got 22 right with none missed. 400 and
#: 500 were worse than both (20 and 19 at best).
PASSAGE_CHARS = 300

#: Lowest similarity between a question and a passage that is put in the
#: prompt, the middle of the 0.30 to 0.40 range above. Below it, unrelated
#: passages came in (6 questions at 0.25); above it, answers were missed
#: (3 questions at 0.45). The two questions still wrong at 0.35 bring a
#: second passage that shares a word in meaning: "room rent" in the health
#: policy also finds the lease's rent clause (0.42).
RELEVANT_PASSAGE = 0.35

#: Larger files are refused rather than read.
MAX_FILE_BYTES = 50 * 1024 * 1024

#: A document that splits into more passages than this is refused: each
#: passage is embedded when the document is added, measured at 162 a second
#: on the development laptop's CPU, so this many take about 31 s.
MAX_PASSAGES = 5000

#: Length of memory_manager's letter-frequency fallback vector. It does not
#: carry meaning (any two English texts score about 0.75), so passages are
#: neither added nor searched with it.
_STUB_DIM = 26

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS documents (
        id        INTEGER PRIMARY KEY,
        path      TEXT NOT NULL UNIQUE,
        name      TEXT NOT NULL,
        sha256    TEXT NOT NULL,
        added_at  REAL NOT NULL,
        passages  INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS passages (
        document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        position    INTEGER NOT NULL,
        text        TEXT NOT NULL,
        embedding   TEXT NOT NULL,
        PRIMARY KEY (document_id, position)
    )""",
)

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class DocumentError(Exception):
    """A document could not be added; the message says why, for the owner."""


@dataclass(slots=True)
class Passage:
    """A passage found for a question, and the document it came from."""

    document: str
    text: str
    score: float


@dataclass(slots=True)
class AddResult:
    """What adding a document did: "added", "updated" or "unchanged"."""

    name: str
    status: str
    passages: int


def split_into_passages(text: str, size: int = PASSAGE_CHARS) -> list[str]:
    """Split *text* into passages of whole paragraphs, each at most about *size* characters.

    A paragraph longer than *size* is split between sentences, and a
    sentence longer than *size* between words, so no passage is cut in the
    middle of a word.
    """
    pieces: list[str] = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        if len(paragraph) <= size:
            pieces.append(paragraph)
            continue
        for sentence in _SENTENCE_END.split(paragraph):
            while len(sentence) > size:
                cut = sentence.rfind(" ", 0, size)
                cut = cut if cut > 0 else size
                pieces.append(sentence[:cut])
                sentence = sentence[cut:].lstrip()
            if sentence:
                pieces.append(sentence)

    passages: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > size:
            passages.append(current)
            current = piece
        else:
            current = f"{current} {piece}" if current else piece
    if current:
        passages.append(current)
    return passages


def _embed(texts: list[str]) -> list[list[float]]:
    # memory_manager's embedder is the model memory search is calibrated
    # on, loaded once per process; a second copy of it would double the
    # 90 MB it holds in memory. Passages are embedded in batches: one at a
    # time ran at 77 passages a second (8.8 s for a 139 KB file).
    from Agent_Guru.memory.memory_manager import _embed_text, _get_real_embedder

    embedder = _get_real_embedder()
    if embedder is not None and len(texts) > 1:
        try:
            return embedder.generate_batch(texts)
        except Exception:
            logger.debug("Batch embedding failed; embedding one at a time", exc_info=True)
    return [_embed_text(text) for text in texts]


class DocumentStore:
    """The owner's documents, split into passages and searchable by meaning."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open_sqlite(self.path) as conn:
            for statement in _SCHEMA:
                conn.execute(statement)
        restrict_file_permissions(self.path)
        self._index: tuple[list[str], list[str], np.ndarray] | None = None
        self._stamp: tuple[object, ...] | None = None

    async def add(self, path: str | Path) -> AddResult:
        """Add or refresh the document at *path*; raises DocumentError with the reason if it cannot."""
        from Agent_Guru.platform.features.presentation import PresentationError, read_source_text

        source = await asyncio.to_thread(lambda: Path(path).expanduser().resolve())
        # A document's passages are read back into prompts and answers; a key
        # or credential file added by mistake would be recited on request.
        from Agent_Guru.security.file_policy import sensitive_reason

        reason = sensitive_reason(source)
        if reason:
            msg = f"{source.name} is not added: it holds {reason}"
            raise DocumentError(msg)
        size = await asyncio.to_thread(lambda: source.stat().st_size if source.is_file() else None)
        if size is None:
            msg = f"There is no file at {source}"
            raise DocumentError(msg)
        if size > MAX_FILE_BYTES:
            msg = f"{source.name} is {size // (1024 * 1024)} MB; documents up to {MAX_FILE_BYTES // (1024 * 1024)} MB are taken"
            raise DocumentError(msg)
        digest = await asyncio.to_thread(lambda: hashlib.sha256(source.read_bytes()).hexdigest())
        with open_sqlite(self.path) as conn:
            row = conn.execute("SELECT sha256, passages FROM documents WHERE path = ?", (str(source),)).fetchone()
        if row and row[0] == digest:
            return AddResult(source.name, "unchanged", row[1])

        try:
            text = await read_source_text(source)
        except PresentationError as exc:
            raise DocumentError(str(exc)) from exc
        passages = split_into_passages(text)
        if not passages:
            msg = f"{source.name} has no text that could be read"
            raise DocumentError(msg)
        if len(passages) > MAX_PASSAGES:
            msg = f"{source.name} is {len(passages)} passages long; documents up to {MAX_PASSAGES} are taken"
            raise DocumentError(msg)
        vectors = await asyncio.to_thread(_embed, passages)
        if len(vectors[0]) == _STUB_DIM:
            msg = "The embedding model is not available (sentence-transformers), so documents cannot be searched"
            raise DocumentError(msg)

        with open_sqlite(self.path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM documents WHERE path = ?", (str(source),))
            cursor = conn.execute(
                "INSERT INTO documents (path, name, sha256, added_at, passages) VALUES (?, ?, ?, ?, ?)",
                (str(source), source.name, digest, time.time(), len(passages)),
            )
            conn.executemany(
                "INSERT INTO passages (document_id, position, text, embedding) VALUES (?, ?, ?, ?)",
                [(cursor.lastrowid, n, p, json.dumps(v)) for n, (p, v) in enumerate(zip(passages, vectors, strict=True))],
            )
        logger.info("Document %s %s: %d passages", source.name, "updated" if row else "added", len(passages))
        return AddResult(source.name, "updated" if row else "added", len(passages))

    def remove(self, path: str | Path) -> bool:
        """Forget the document at *path*; False if it was not added."""
        source = str(Path(path).expanduser().resolve())
        with open_sqlite(self.path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            removed = conn.execute("DELETE FROM documents WHERE path = ?", (source,)).rowcount
        return bool(removed)

    def documents(self) -> list[dict[str, object]]:
        """Every added document: path, name, passages and when it was added, oldest first."""
        with open_sqlite(self.path) as conn:
            rows = conn.execute("SELECT path, name, passages, added_at FROM documents ORDER BY added_at").fetchall()
        return [{"path": r[0], "name": r[1], "passages": r[2], "added_at": r[3]} for r in rows]

    def _load_index(self) -> tuple[list[str], list[str], np.ndarray]:
        # Documents are added from the command line while the assistant
        # runs, in another process, so the cached index is checked against
        # the table on every question (one small query) and reloaded when a
        # document was added, updated or removed since.
        with open_sqlite(self.path) as conn:
            stamp = conn.execute("SELECT count(*), max(added_at), sum(passages) FROM documents").fetchone()
            if self._index is not None and self._stamp == stamp:
                return self._index
            rows = conn.execute(
                "SELECT d.name, p.text, p.embedding FROM passages p JOIN documents d ON d.id = p.document_id "
                "ORDER BY d.id, p.position",
            ).fetchall()
        if rows:
            matrix = np.array([json.loads(r[2]) for r in rows], dtype=np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            matrix = matrix / np.where(norms == 0, 1, norms)
        else:
            matrix = np.zeros((0, 0), dtype=np.float32)
        self._index, self._stamp = ([r[0] for r in rows], [r[1] for r in rows], matrix), stamp
        return self._index

    async def search(self, query: str, limit: int = 3, min_score: float = RELEVANT_PASSAGE) -> list[Passage]:
        """The passages at least *min_score* similar to *query*, best first, at most *limit*."""
        if not query.strip() or limit <= 0:
            return []
        names, texts, matrix = await asyncio.to_thread(self._load_index)
        if not texts:
            return []
        (vector,) = await asyncio.to_thread(_embed, [query])
        if len(vector) != matrix.shape[1]:
            # The real embedder failed to load this run: the query came back
            # as the letter-frequency stub, which cannot be compared.
            return []
        query_vec = np.asarray(vector, dtype=np.float32)
        query_vec /= np.linalg.norm(query_vec) or 1.0
        scores = matrix @ query_vec
        best = np.argsort(-scores)[:limit]
        return [Passage(names[i], texts[i], float(scores[i])) for i in best if scores[i] >= min_score]


def run(argv: list[str], store: DocumentStore | None = None) -> int:
    """``python -m Agent_Guru documents add|remove|list``: manage the owner's documents."""
    import argparse

    parser = argparse.ArgumentParser(prog="agent-guru documents", description="Documents the assistant answers from.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("add", help="add or refresh documents").add_argument("paths", nargs="+")
    commands.add_parser("remove", help="forget documents").add_argument("paths", nargs="+")
    commands.add_parser("list", help="show the documents added")
    args = parser.parse_args(argv)

    if store is None:
        from Agent_Guru.utils.path_utils import app_data_dir

        store = DocumentStore(app_data_dir("documents.db"))
    failed = 0
    if args.command == "add":
        for path in args.paths:
            try:
                result = asyncio.run(store.add(path))
            except DocumentError as exc:
                print(f"Not added: {exc}")  # noqa: T201  the command\'s output
                failed += 1
            else:
                print(f"{result.status.capitalize()}: {result.name} ({result.passages} passages)")  # noqa: T201  the command\'s output
    elif args.command == "remove":
        for path in args.paths:
            if store.remove(path):
                print(f"Removed: {Path(path).name}")  # noqa: T201  the command\'s output
            else:
                print(f"Not added, so nothing to remove: {path}")  # noqa: T201  the command\'s output
                failed += 1
    else:
        documents = store.documents()
        for doc in documents:
            added = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(doc["added_at"])))
            print(f"{doc['name']}  {doc['passages']} passages  added {added}  {doc['path']}")  # noqa: T201  the command\'s output
        if not documents:
            print("No documents added. Add one with: python -m Agent_Guru documents add <file>")  # noqa: T201  the command\'s output
    return 1 if failed else 0
