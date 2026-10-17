"""A local model's second opinion on whether outside text tries to steer the assistant.

The rules in llm/security.py catch the phrasings they were written for. On
texts written after the last rule change they blocked 7 of 20 attacks, and
every attempt to widen them further started dropping ordinary pages. This
module runs a fine-tuned classifier over the same text, on the CPU, with no
network: protectai/deberta-v3-base-prompt-injection-v2 (Apache-2.0), as
ONNX, pinned to one revision and checked against the upstream hashes.

It is a detector only. guard_external_text() asks it after the rules and
may withhold text it flags; nothing here can make text more trusted, allow
a tool, or answer a confirmation. A model that is missing, broken, slow or
fails gives UNKNOWN, and then the rules' decision stands exactly as it was.

Nothing is downloaded during a conversation. install() is run on purpose
(python -m Agent_Guru injection-model install), writes each file to a .part
name, verifies its size and hash, and only then gives it its real name, so
an interrupted or tampered download never looks like a model.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_ID = "protectai/deberta-v3-base-prompt-injection-v2"
MODEL_REVISION = "90c9989b1a342275dd0d1a95aad283c04e075671"
MODEL_LICENSE = "Apache-2.0"
MODEL_SOURCE = f"https://huggingface.co/{MODEL_ID}/tree/{MODEL_REVISION}"

#: Upstream path -> (hash kind, digest, size in bytes), from the Hugging Face
#: API at MODEL_REVISION. "sha256" is the LFS object hash; "git-sha1" is the
#: git blob id of a small file. training_args.bin (a pickle) and the
#: safetensors copy are never fetched.
MODEL_FILES: dict[str, tuple[str, str, int]] = {
    "onnx/model.onnx": ("sha256", "f0ea7f239f765aedbde7c9e163a7cb38a79c5b8853d3f76db5152172047b228c", 738563188),
    "onnx/tokenizer.json": ("git-sha1", "00c50710453478105265c838bfb3bad69b410891", 8648886),
    "onnx/config.json": ("git-sha1", "3366690a064655366dd7dd57f9b3cf1e8ba8e78f", 1014),
}

ENABLE_ENV = "AGENT_GURU_INJECTION_CLASSIFIER"
DIR_ENV = "AGENT_GURU_INJECTION_MODEL_DIR"
TIMEOUT_ENV = "AGENT_GURU_INJECTION_TIMEOUT_S"

#: Text beyond this is not classified; the rules still see all of it.
MAX_CHARS = 20_000
#: Tokens per window, less the two special tokens, and the overlap between
#: windows so a sentence across a window edge is seen whole. 512-token
#: windows took 2.0 s for a 4,000-character page on four CPU threads and
#: caught fewer buried attacks (11 of 24 on the development pages) than
#: 256-token windows over the candidate sentences below (16 of 24, 40 ms).
WINDOW_TOKENS = 254
WINDOW_OVERLAP = 32
#: Most windows classified per text; more are skipped and the result says so.
MAX_WINDOWS = 8


#: A sentence worth the model's time in a longer text: addressed to "you" or
#: to an AI, or about instructions, rules, secrets or doing something. The
#: model reads a page sentence by sentence through these; an attack in a
#: page of ordinary prose is then most of a window instead of a sliver.
_CUE = re.compile(
    r"\b(?:you|your|you're|yourself|ai|assistant|model|llm|bot|chatbot|agent|gpt|ignore|disregard|forget"
    r"|overlook|instructions?|prompts?|system|rules?|guidelines?|policy|override|pretend|act|roleplay|send|email"
    r"|forward|upload|post|share|reveal|print|output|repeat|leak|delete|run|execute|open|visit|click|install"
    r"|fetch|passwords?|secrets?|key|token|confidential|hidden|jailbreak|mode)\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

#: English function words. The model is English-only (its card says so), and
#: on Spanish, German and Italian text it scored ordinary sentences 1.0; such
#: text gets UNKNOWN, and the rules, which have multilingual patterns, decide.
_ENGLISH_WORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been being it this that these "
    "those you your i me my we our they them their he she his her not no do does did have has had will would "
    "can could should may might must if then than so as about into over after before all any every some what "
    "which who when where how there here up out".split(),
)
DEFAULT_TIMEOUT_S = 2.0

#: Thresholds on the model's injection score, chosen on the development sets
#: only (see docs/architecture/INJECTION_CLASSIFIER.md). The score is the
#: model's softmax output, not a calibrated probability.
INJECTION_THRESHOLD = 0.98
SUSPICIOUS_THRESHOLD = 0.50

#: Decoded forms of a text classified beside it, at most. They come from the
#: rules' own bounded decoder (llm/security.py _disguised_forms): zero-width
#: characters removed, spaced or separated letters joined, leetspeak undone,
#: printable base64 decoded. Nothing is executed or fetched. On the
#: development half of set 5, attacks written as leetspeak went from 0 of 4
#: caught to 4 of 4 and base64 ones from 0 of 4 to 4 of 4; 2 more of 22
#: ordinary texts were marked (an encoded settings blob, a security article).
MAX_DECODED_FORMS = 4

#: Changes to how text is prepared invalidate cached results.
PREPROCESSING_VERSION = "3"
_CACHE_SIZE = 512
_DOWNLOAD_TIMEOUT_S = 60.0


class Verdict(str, Enum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    INJECTION = "injection"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifierResult:
    """What the model said about one text, and how far that can be relied on."""

    verdict: Verdict
    score: float | None = None
    seconds: float = 0.0
    windows: int = 0
    truncated: bool = False
    reason: str = ""
    model: str = MODEL_ID
    revision: str = MODEL_REVISION[:12]
    window_scores: tuple[float, ...] = field(default=(), repr=False)
    #: True when the deciding score came from a decoded form of the text
    #: (leetspeak undone, base64 decoded), not from the text as written.
    decoded: bool = False


class ClassifierUnavailable(RuntimeError):
    """The model cannot be used; the reason is in the message."""


def enabled() -> bool:
    """Off unless switched on (AGENT_GURU_INJECTION_CLASSIFIER=1).

    Off by default because the evidence does not yet support more: it holds
    about 0.9 GB of memory on a machine shared with the local LLM, a long page
    takes 0.7 to 2.9 s on a 12-thread laptop CPU, it marks 17% of ordinary
    texts, and it has not been run on macOS. See INJECTION_CLASSIFIER.md.
    """
    return os.environ.get(ENABLE_ENV, "0").strip().lower() in {"1", "true", "yes", "on"}


def model_dir() -> Path:
    configured = os.environ.get(DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache" / "agent_guru" / "prompt-injection" / MODEL_REVISION[:12]


def timeout_s() -> float:
    try:
        value = float(os.environ.get(TIMEOUT_ENV, "") or DEFAULT_TIMEOUT_S)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else DEFAULT_TIMEOUT_S


# ---------------------------------------------------------------------------
# Installation and verification
# ---------------------------------------------------------------------------


def _local_name(upstream: str) -> str:
    return upstream.rsplit("/", 1)[-1]


def _pins() -> list[Any]:
    """MODEL_FILES as the shared verifier's pins (read each time, so tests can replace MODEL_FILES)."""
    from Agent_Guru.utils.verified_files import PinnedFile

    return [PinnedFile(_local_name(u), size, digest, kind) for u, (kind, digest, size) in MODEL_FILES.items()]


_STAMP_EXTRA = {"model": MODEL_ID, "revision": MODEL_REVISION}


def verify(directory: Path | None = None) -> list[str]:
    """Every problem with the installed files, empty when all match the pinned hashes."""
    from Agent_Guru.utils.verified_files import verify as verify_files

    return verify_files(directory or model_dir(), _pins())


def _write_stamp(directory: Path) -> None:
    from Agent_Guru.utils.verified_files import write_stamp

    write_stamp(directory, _pins(), _STAMP_EXTRA)


def _stamp_matches(directory: Path) -> bool:
    """True if the files are the ones last verified (same size, modification time and pin)."""
    from Agent_Guru.utils.verified_files import stamp_matches

    return stamp_matches(directory, _pins(), _STAMP_EXTRA)


def install(directory: Path | None = None, source: Path | None = None, progress: Any = None) -> Path:
    """Put the pinned model files in *directory*, verified; from *source* (a folder) or Hugging Face.

    Files already present and matching are kept. A file that does not match
    is replaced; one that fails verification after download is deleted and
    the install fails, so a half-installed model never passes verify().
    """
    from Agent_Guru.utils.verified_files import STAMP_NAME, VerificationError, copy_in, download, problems

    directory = directory or model_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / STAMP_NAME).unlink(missing_ok=True)
    for upstream, pin in zip(MODEL_FILES, _pins(), strict=True):
        dest = directory / pin.name
        if not problems(dest, pin):
            continue
        try:
            if source is not None:
                candidate = next((c for c in (source / upstream, source / pin.name) if c.is_file()), None)
                if candidate is None:
                    msg = f"{pin.name} is not in {source}"
                    raise ClassifierUnavailable(msg)
                copy_in(candidate, dest, pin)
            else:
                url = f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{upstream}"
                download(url, dest, pin, timeout=_DOWNLOAD_TIMEOUT_S, progress=progress)
        except VerificationError as exc:
            raise ClassifierUnavailable(str(exc)) from exc
    found = verify(directory)
    if found:
        raise ClassifierUnavailable("; ".join(found))
    _write_stamp(directory)
    return directory


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def _english(text: str) -> bool:
    """False for text that is plainly not English: mostly non-Latin letters, or Latin without English words."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    if sum(c.isascii() for c in letters) / len(letters) < 0.7:
        return False
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < 6:
        return True
    return sum(w in _ENGLISH_WORDS for w in words) / len(words) >= 0.12


class InjectionClassifier:
    """The loaded model; thread-safe. Use shared() rather than building one per call."""

    def __init__(self, directory: Path | None = None, threads: int | None = None) -> None:
        self._directory = directory or model_dir()
        self._threads = threads or max(1, min(4, (os.cpu_count() or 2) // 2))
        self._lock = threading.Lock()
        self._session: Any = None
        self._tokenizer: Any = None
        self._injection_index = 1
        self._failure = ""
        self._cache: OrderedDict[str, ClassifierResult] = OrderedDict()
        self._cache_lock = threading.Lock()

    @property
    def failure(self) -> str:
        return self._failure

    def status(self) -> str:
        if self._session is not None:
            return "ready"
        if self._failure:
            return f"unavailable: {self._failure}"
        return "not loaded"

    def load(self) -> None:
        """Load the model once; raises ClassifierUnavailable with the reason."""
        with self._lock:
            if self._session is not None:
                return
            if self._failure:
                raise ClassifierUnavailable(self._failure)
            try:
                self._load()
            except ClassifierUnavailable as exc:
                self._failure = str(exc)
                raise
            except Exception as exc:  # a broken runtime or file must not escape as a crash
                self._failure = f"{type(exc).__name__}: {str(exc)[:200]}"
                raise ClassifierUnavailable(self._failure) from exc

    def _load(self) -> None:
        directory = self._directory
        if not (directory / "model.onnx").is_file():
            msg = f"not installed in {directory} (python -m Agent_Guru injection-model install)"
            raise ClassifierUnavailable(msg)
        if not _stamp_matches(directory):
            # Changed since it was last verified, or never verified here:
            # check the hashes again before loading anything.
            problems = verify(directory)
            if problems:
                msg = "model files failed verification: " + "; ".join(problems)
                raise ClassifierUnavailable(msg)
            _write_stamp(directory)
        import onnxruntime as ort
        from tokenizers import Tokenizer

        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        labels = {int(k): str(v).upper() for k, v in (config.get("id2label") or {}).items()}
        index = next((i for i, name in labels.items() if "INJECTION" in name), None)
        if index is None or len(labels) != 2:
            msg = f"unexpected labels in config.json: {labels}"
            raise ClassifierUnavailable(msg)
        tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = self._threads
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Without the memory arena the process holds about 105 MB less after
        # inference (800 MB instead of 905 MB on Windows) for 9% more time
        # per window; the assistant shares the machine with a local LLM.
        options.enable_cpu_mem_arena = False
        # CPU only, named explicitly: the default provider list on Windows
        # and Linux also contains AzureExecutionProvider, which can send
        # inputs to a remote endpoint.
        session = ort.InferenceSession(str(directory / "model.onnx"), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        names = {i.name for i in session.get_inputs()}
        if not {"input_ids", "attention_mask"} <= names:
            msg = f"unexpected model inputs: {sorted(names)}"
            raise ClassifierUnavailable(msg)
        self._input_names = names
        self._tokenizer, self._injection_index, self._session = tokenizer, index, session

    def _windows(self, text: str) -> tuple[list[list[int]], bool]:
        sentences = [s for s in _SENTENCE_BREAK.split(text) if s.strip()]
        if len(sentences) > 1:
            text = " ".join(s for s in sentences if _CUE.search(s))
            if not text:
                return [], False
        ids = self._tokenizer.encode(text, add_special_tokens=False).ids
        cls_id = self._tokenizer.token_to_id("[CLS]")
        sep_id = self._tokenizer.token_to_id("[SEP]")
        step = WINDOW_TOKENS - WINDOW_OVERLAP
        windows, start = [], 0
        while True:
            windows.append([cls_id, *ids[start:start + WINDOW_TOKENS], sep_id])
            if start + WINDOW_TOKENS >= len(ids):
                return windows, False
            start += step
            if len(windows) == MAX_WINDOWS:
                return windows, True

    def _scores(self, windows: list[list[int]]) -> list[float]:
        import numpy as np

        width = max(len(w) for w in windows)
        ids = np.zeros((len(windows), width), dtype=np.int64)
        mask = np.zeros((len(windows), width), dtype=np.int64)
        for row, window in enumerate(windows):
            ids[row, :len(window)] = window
            mask[row, :len(window)] = 1
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        logits = self._session.run(None, feed)[0].astype(np.float64)
        if logits.ndim != 2 or logits.shape[1] != 2 or not np.isfinite(logits).all():
            msg = f"unexpected model output shape {logits.shape}"
            raise ClassifierUnavailable(msg)
        shifted = logits - logits.max(axis=1, keepdims=True)
        probs = np.exp(shifted) / np.exp(shifted).sum(axis=1, keepdims=True)
        return [float(p) for p in probs[:, self._injection_index]]

    def classify(self, text: str) -> ClassifierResult:
        """The model's verdict on *text*; never raises, UNKNOWN when it cannot say."""
        started = time.perf_counter()
        if not isinstance(text, str) or not text.strip():
            return ClassifierResult(Verdict.BENIGN, 0.0, reason="empty")
        clipped = text[:MAX_CHARS]
        if not _english(clipped):
            return ClassifierResult(Verdict.UNKNOWN, reason="not English: the model reads English only")
        key = self._cache_key(clipped)
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
        try:
            self.load()
            windows, skipped = self._windows(clipped)
            scores = self._scores(windows) if windows else [0.0]
        except ClassifierUnavailable as exc:
            return ClassifierResult(Verdict.UNKNOWN, reason=str(exc)[:200], seconds=time.perf_counter() - started)
        except Exception as exc:
            return ClassifierResult(Verdict.UNKNOWN, reason=f"{type(exc).__name__}: {str(exc)[:160]}",
                                    seconds=time.perf_counter() - started)
        score = max(scores)
        if score >= INJECTION_THRESHOLD:
            verdict = Verdict.INJECTION
        elif score >= SUSPICIOUS_THRESHOLD:
            verdict = Verdict.SUSPICIOUS
        else:
            verdict = Verdict.BENIGN
        truncated = skipped or len(text) > MAX_CHARS
        result = ClassifierResult(verdict, score, time.perf_counter() - started, len(windows), truncated,
                                  window_scores=tuple(scores))
        with self._cache_lock:
            self._cache[key] = result
            while len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)
        return result

    def _cache_key(self, text: str, kind: str = "one") -> str:
        return hashlib.sha256(
            f"{kind}|{MODEL_REVISION}|{PREPROCESSING_VERSION}|{INJECTION_THRESHOLD}|{SUSPICIOUS_THRESHOLD}|".encode()
            + text[:MAX_CHARS].encode("utf-8", "surrogatepass"),
        ).hexdigest()

    def classify_all(self, text: str) -> ClassifierResult:
        """The verdict on *text* and on its decoded forms: the highest score decides; never raises.

        The text as written and each decoded form are classified separately;
        a decoded form only ever adds evidence, and the text that reaches
        the model is never the decoded one.
        """
        if not isinstance(text, str) or not text.strip():
            return self.classify(text)
        key = self._cache_key(text, "all")
        with self._cache_lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached
        from Agent_Guru.llm.security import _disguised_forms

        main = self.classify(text)
        results = [main]
        for form in _disguised_forms(text[:MAX_CHARS])[:MAX_DECODED_FORMS]:
            if form.strip():
                results.append(self.classify(form))
        scored = [r for r in results if r.score is not None]
        if not scored:
            best = main
        else:
            top = max(scored, key=lambda r: r.score or 0.0)
            best = dataclasses.replace(top, seconds=sum(r.seconds for r in results), decoded=top is not main,
                                       truncated=any(r.truncated for r in results))
        if best.verdict is not Verdict.UNKNOWN or best is not main:
            with self._cache_lock:
                self._cache[key] = best
                while len(self._cache) > _CACHE_SIZE:
                    self._cache.popitem(last=False)
        return best

    def cached_or_queue(self, text: str) -> ClassifierResult | None:
        """A verdict already worked out for *text*, or None after queueing one; never runs the model here.

        For callers on the event loop that cannot wait: the first model load
        took 4.3 s and a page about 40 ms, and both would have stalled every
        other task, voice included.
        """
        if not isinstance(text, str) or not text.strip():
            return None
        with self._cache_lock:
            cached = self._cache.get(self._cache_key(text, "all"))
        if cached is not None:
            return cached
        if self._failure:
            return None
        _submit(self.classify_all, text)
        return None

    async def classify_async(self, text: str, timeout: float) -> ClassifierResult:
        """classify_all() on the classifier's worker thread; UNKNOWN if it takes longer than *timeout*."""
        import asyncio

        started = time.perf_counter()
        future = _submit(self.classify_all, text)
        if future is None:
            return ClassifierResult(Verdict.UNKNOWN, reason="classifier queue full")
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout)
        except TimeoutError:
            # The run itself cannot be interrupted; it finishes in the
            # background and fills the cache, but this text goes on with
            # the rules' decision alone.
            return ClassifierResult(Verdict.UNKNOWN, reason=f"no verdict within {timeout:g} s",
                                    seconds=time.perf_counter() - started)

    def close(self) -> None:
        with self._lock:
            self._session, self._tokenizer = None, None
        with self._cache_lock:
            self._cache.clear()


#: One worker thread for every classification, so the model's CPU use is
#: bounded and calls never run in parallel inside one session; at most
#: _QUEUE_LIMIT texts wait, the rest go on with the rules alone.
_QUEUE_LIMIT = 64
_executor: Any = None
_executor_lock = threading.Lock()
_queued = threading.BoundedSemaphore(_QUEUE_LIMIT)


def _submit(fn: Any, text: str) -> Any:
    from concurrent.futures import ThreadPoolExecutor

    global _executor
    if not _queued.acquire(blocking=False):
        return None
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="injection-classifier")
    future = _executor.submit(fn, text)
    future.add_done_callback(lambda _f: _queued.release())
    return future


_shared: InjectionClassifier | None = None
_shared_lock = threading.Lock()


def shared() -> InjectionClassifier:
    """The process-wide classifier, created on first use (the model loads on its first classify)."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = InjectionClassifier()
        return _shared


def reset_shared() -> None:
    """Drop the shared classifier (tests, or after installing the model)."""
    global _shared
    with _shared_lock:
        if _shared is not None:
            with contextlib.suppress(Exception):
                _shared.close()
        _shared = None


# ---------------------------------------------------------------------------
# Command line: python -m Agent_Guru injection-model ...
# ---------------------------------------------------------------------------


def run(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m Agent_Guru injection-model",
        description=f"The local prompt-injection classifier ({MODEL_ID}, {MODEL_LICENSE}).",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    inst = sub.add_parser("install", help="download the pinned model files, or copy them from a folder, verified")
    inst.add_argument("--from", dest="source", type=Path, help="a folder that already holds the files (offline install)")
    sub.add_parser("verify", help="check the installed files against the pinned hashes")
    sub.add_parser("status", help="where the model is, whether it is switched on, and whether it loads")
    check = sub.add_parser("check", help="classify a text and print the verdict")
    check.add_argument("text")
    args = parser.parse_args(argv)
    directory = model_dir()
    if args.action == "install":
        def progress(name: str, done: int, size: int) -> None:
            if done == size or done % (50 << 20) < (1 << 20):
                print(f"  {name}: {done * 100 // size}%", flush=True)  # noqa: T201  the command's output

        try:
            install(directory, source=args.source, progress=progress)
        except (ClassifierUnavailable, OSError) as exc:
            print(f"Install failed: {exc}")  # noqa: T201
            return 1
        print(f"Installed and verified {MODEL_ID}@{MODEL_REVISION[:12]} in {directory}")  # noqa: T201
        if not enabled():
            print(f"It is switched off: set {ENABLE_ENV}=1 (or add it to settings.toml) to use it.")  # noqa: T201
        return 0
    if args.action == "verify":
        problems = verify(directory)
        print("\n".join(problems) or f"All {len(MODEL_FILES)} files match their pinned hashes.")  # noqa: T201
        return 1 if problems else 0
    if args.action == "status":
        print(f"model: {MODEL_ID}@{MODEL_REVISION[:12]} ({MODEL_LICENSE}), source {MODEL_SOURCE}")  # noqa: T201
        print(f"folder: {directory}")  # noqa: T201
        print(f"switched on: {enabled()} ({ENABLE_ENV})")  # noqa: T201
        classifier = InjectionClassifier(directory)
        t = time.perf_counter()
        try:
            classifier.load()
            print(f"loads: yes, in {time.perf_counter() - t:.1f} s")  # noqa: T201
        except ClassifierUnavailable as exc:
            print(f"loads: no ({exc})")  # noqa: T201
            return 1
        return 0
    result = InjectionClassifier(directory).classify_all(args.text)
    print(f"{result.verdict.value} score={result.score} windows={result.windows} decoded={result.decoded} "  # noqa: T201
          f"{result.seconds * 1000:.0f} ms {result.reason}")
    return 0
