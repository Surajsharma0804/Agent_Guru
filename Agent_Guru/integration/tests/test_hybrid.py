"""A long document is read locally passage by passage; the planner sees only the question and findings."""

from __future__ import annotations


import pytest

from Agent_Guru.integration import hybrid
from Agent_Guru.integration.hybrid import LongDocumentTools, answer, passages

CONTRACT = "\n\n".join(
    [f"Clause {i}. The parties agree to ordinary matter number {i}, " + "as set out in the schedule. " * 4 for i in range(1, 30)]
    + ["Clause 30. Either party may end this agreement with ninety days written notice."]
    + [f"Clause {i}. Further ordinary matter {i}." for i in range(31, 60)]
)


class Recorder:
    def __init__(self, reply):
        self.prompts, self.reply = [], reply

    async def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.reply(prompt)


def _local(prompt):
    return "1: ninety days written notice" if "ninety days" in prompt else "1: NONE"


def _planner(prompt):
    if "JSON list" in prompt:
        return 'Here: ["How long is the notice period?"]'
    return "Ninety days written notice [P3]."


def test_passages_keep_paragraphs_and_their_size():
    pieces = passages(CONTRACT, size=1000)
    assert all(len(p) <= 1000 for p in pieces) and "".join(pieces).count("Clause") == 59  # nosec B101
    assert passages("x" * 2500, size=1000) == ["x" * 1000, "x" * 1000, "x" * 500]  # nosec B101


async def test_the_planner_never_sees_the_documents_text():
    local, planner = Recorder(_local), Recorder(_planner)
    result = await answer("What is the notice period?", CONTRACT, local=local, planner=planner, planner_name="cloud")
    assert result.answer.startswith("Ninety days") and result.questions == ["How long is the notice period?"]  # nosec B101
    assert len(local.prompts) == result.passages > 1  # nosec B101  every passage read locally
    assert not any("ordinary matter" in p for p in planner.prompts)  # nosec B101
    assert [i for i, _ in result.findings] == [i for i, p in enumerate(passages(CONTRACT), 1) if "ninety" in p]  # nosec B101


async def test_nothing_found_says_so_without_asking_the_planner_to_guess():
    planner = Recorder(_planner)
    result = await answer("Who is the CEO?", CONTRACT, local=Recorder(lambda p: "1: NONE"), planner=planner)
    assert result.answer == "The document does not say." and len(planner.prompts) == 1  # nosec B101


async def test_an_unreadable_plan_falls_back_to_the_question_itself():
    result = await answer("Notice?", "short text", local=Recorder(lambda p: "1: NONE"), planner=Recorder(lambda p: "no json"))
    assert result.questions == ["Notice?"]  # nosec B101


async def test_the_tool_reads_only_the_owners_files(monkeypatch, tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "contract.txt").write_text(CONTRACT, encoding="utf-8")
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("FILES_ROOTS", str(docs))
    tools = LongDocumentTools(local=Recorder(_local), planner=(Recorder(_planner), "test-cloud"))
    text, is_error, _ = await tools.call("read_long_document", {"path": str(docs / "contract.txt"), "question": "notice?"})
    assert not is_error and "Ninety days" in text and "the text stayed on this machine" in text  # nosec B101
    _, is_error, _ = await tools.call("read_long_document", {"path": str(tmp_path / "secret.txt"), "question": "x"})
    assert is_error  # nosec B101


def test_the_cloud_plans_only_when_allowed(monkeypatch):
    monkeypatch.setenv("AGENT_GURU_CLOUD_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("AGENT_GURU_ALLOW_CLOUD", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert hybrid.cloud_planner() == (None, "local")  # nosec B101
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    planner, name = hybrid.cloud_planner()
    assert planner is not None and name == "gpt-4o-mini"  # nosec B101


@pytest.mark.live_llm
async def test_with_the_real_local_model():
    result = await answer("How much notice is needed to end the agreement?", CONTRACT, local=hybrid.ollama_model)
    assert "ninety" in result.answer.lower() or "90" in result.answer  # nosec B101


@pytest.fixture
def ollama_bodies(monkeypatch):
    """Stands in for Ollama's /api/chat and keeps every request body."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    bodies: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            data = json.dumps({"message": {"role": "assistant", "content": "1: NONE"}, "done": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.delenv("AGENT_GURU_NUM_CTX", raising=False)
    monkeypatch.delenv("AGENT_GURU_NUM_GPU", raising=False)
    yield bodies
    server.shutdown()
    server.server_close()


async def test_the_local_reader_loads_the_model_as_every_other_client(ollama_bodies, monkeypatch):
    # It sent only a temperature, so Ollama loaded the model at its own context (4096, measured)
    # instead of the 6144 every other client asks for, and reloaded it on each switch.
    from Agent_Guru.reasoning.llm.generation import ollama_options

    monkeypatch.setenv("OLLAMA_MODEL", "gemma3:1b")
    await hybrid.ollama_model("Does clause 30 mention notice?")
    (body,) = ollama_bodies
    expected = ollama_options(num_predict=None)
    assert body["model"] == "gemma3:1b" and body["think"] is False  # nosec B101
    assert {k: body["options"][k] for k in ("num_ctx", "num_gpu")} == {  # nosec B101
        k: expected[k] for k in ("num_ctx", "num_gpu")
    }


async def test_the_local_reader_uses_the_configured_default_model(ollama_bodies, monkeypatch):
    from Agent_Guru.reasoning.llm.generation import DEFAULT_OLLAMA_MODEL

    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    await hybrid.ollama_model("Does clause 30 mention notice?")
    assert ollama_bodies[0]["model"] == DEFAULT_OLLAMA_MODEL  # nosec B101  was "gemma4"
